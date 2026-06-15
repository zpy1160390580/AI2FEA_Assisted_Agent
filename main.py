"""
AI2FEA 辅助智能体 - 主程序（LangGraph 版本）
==============================================

这是一个基于 Streamlit 的 Web 应用，使用 LangGraph 状态图自动化 Abaqus 有限元分析工作流。

主要功能：
1. 通过自然语言查询控制 Abaqus 仿真
2. 自动生成输入文件、运行作业、提取应力数据
3. 参数化研究：自动迭代找到满足应力阈值的最优参数
4. 实时评估：追踪工具调用正确性、单位正确性和幻觉检测

技术栈：
- Streamlit: Web 界面
- LangGraph: 状态图编排框架
- 硅基流动平台 + DeepSeek-V3: 大语言模型
- Phoenix: 可观测性平台（可选）
- Abaqus: 有限元分析软件

运行方式：
    streamlit run main.py

作者：AI2FEA Team
"""

# ============================================================================
# 导入依赖库
# ============================================================================

import os
import json
import re
import streamlit as st
from dotenv import load_dotenv
import pandas as pd

# Phoenix 可观测性平台
from phoenix.otel import register
from phoenix.trace import suppress_tracing, SpanEvaluations
from openinference.instrumentation.langchain import LangChainInstrumentor
from phoenix.trace.dsl import SpanQuery
import phoenix as px

# LangGraph 状态图框架
from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, AIMessage, ToolMessage

# Phoenix 评估工具
from phoenix.evals import OpenAIModel

# 导入自定义模块
from graph_agent import create_graph, get_agent_steps, tools
from FEA_tools.prompt_temp import (
    react_system_prompt as RA_SYSTEM_PROMPT,
    TOOL_CALLING_PROMPT_TEMPLATE,
    TOOL_UNIT_PROMPT_TEMPLATE,
    FINAL_HALLUCINATION_PROMPT_TEMPLATE,
)
from FEA_tools.eval_utils import (
    run_eval,
    log_stress_eval_real_time,
)
from FEA_tools.tools import extract_action

# 导入配置文件
from config_files import config

# ============================================================================
# 配置参数
# ============================================================================

# 从配置文件加载参数
stress_threshold = config.STRESS_THRESHOLD
SILICONFLOW_API_KEY = config.SILICONFLOW_API_KEY
SILICONFLOW_BASE_URL = config.SILICONFLOW_BASE_URL
DEFAULT_MODEL = config.MODEL_NAME
DEFAULT_EVAL_MODEL = config.EVAL_MODEL_NAME
DEFAULT_EVAL_MODEL_HIGH = config.EVAL_MODEL_HIGH_REASONING

# ============================================================================
# Phoenix 可观测性初始化（可选）
# ============================================================================

@st.cache_resource(show_spinner=False)
def init_observability():
    """
    初始化 Phoenix 可观测性平台

    如果在 config.py 中启用了 Phoenix 追踪，则注册 OTEL 导出器
    并启动 Phoenix 应用。Phoenix 用于追踪智能体的执行过程和评估结果。

    Returns:
        Phoenix 会话对象，如果未启用则返回 None
    """
    if config.ENABLE_PHOENIX_TRACING:
        # 注册 OpenTelemetry 导出器
        tp = register(
            endpoint=config.OTEL_EXPORTER_OTLP_ENDPOINT,
            batch=True,
            set_global_tracer_provider=False,
        )
        # 为 LangChain 添加追踪
        LangChainInstrumentor().instrument(tracer_provider=tp)
        return px.launch_app()
    return None

# 初始化 Phoenix 会话
session = init_observability()

# ============================================================================
# 侧边栏：模型选择
# ============================================================================

# 主模型选择（用于智能体推理）
llm_type = st.sidebar.selectbox(
    "选择主模型",
    ["deepseek-ai/DeepSeek-V3", "deepseek-ai/DeepSeek-R1", "Qwen/Qwen2.5-72B-Instruct"],
    index=0,
    help="用于智能体推理和工具调用的主模型"
)

# 评估模型选择（用于一般评估任务）
llm_type_eval = st.sidebar.selectbox(
    "选择评估模型",
    ["deepseek-ai/DeepSeek-V3", "deepseek-ai/DeepSeek-R1", "Qwen/Qwen2.5-72B-Instruct"],
    index=0,
    help="用于单位正确性和幻觉检测的评估模型"
)

# 高推理评估模型选择（用于复杂评估任务）
llm_type_eval_high = st.sidebar.selectbox(
    "选择高推理评估模型",
    ["deepseek-ai/DeepSeek-V3", "deepseek-ai/DeepSeek-R1"],
    index=0,
    help="用于工具调用正确性评估的高推理模型"
)

# ============================================================================
# LangGraph 状态图初始化
# ============================================================================

@st.cache_resource(show_spinner=False)
def init_agent(_llm_type, _stress_threshold):
    """
    初始化 LangGraph 状态图

    Args:
        _llm_type: 模型类型
        _stress_threshold: 应力阈值

    Returns:
        编译后的状态图
    """
    # 初始化大语言模型
    llm = ChatOpenAI(
        model=_llm_type,
        api_key=SILICONFLOW_API_KEY,
        base_url=SILICONFLOW_BASE_URL,
        temperature=config.TEMPERATURE,
        max_tokens=config.MAX_TOKENS
    )

    # 添加系统提示词
    llm = llm.bind(system=RA_SYSTEM_PROMPT())

    # 创建状态图
    app = create_graph(
        llm=llm,
        stress_threshold=_stress_threshold,
        max_iterations=config.MAX_ITERATIONS
    )

    return app

# 获取智能体实例
agent_graph = init_agent(llm_type, stress_threshold)

# ============================================================================
# 用户界面
# ============================================================================

# 页面标题
st.title(config.PAGE_TITLE)

# 项目介绍
st.markdown("""
这个 AI 智能体与 Abaqus 无缝集成，使用 **LangGraph 状态图**自动化仿真工作流，包括模型生成、作业运行和应力数据提取。

### LangGraph 架构优势
- **清晰的状态管理**: 每个步骤的状态都被显式跟踪
- **条件分支控制**: 可以根据应力值动态调整策略
- **可视化工作流**: 图结构更易于理解和调试
- **人机协作**: 支持在关键节点添加人工审核

### 工作流程
1. **模型输入生成**: 使用 `generate_input_file` 函数，智能体根据指定参数（如位移）创建 Abaqus 输入文件（`.inp`）
2. **作业执行**: `run_abaqus` 函数使用准备好的输入文件启动 Abaqus 仿真
3. **应力提取**: 利用 `extract_von_mises_stress_from_ODB` 函数，智能体从仿真输出数据库（ODB）中提取 Von-Mises 应力数据

当前演示展示了智能体在悬臂梁仿真工作流自动化方面的能力，重点是应力提取，如下图所示。
""")

# 显示悬臂梁示意图（如果存在）
logo_file_path = "artifacts/cantilever_beam_schematic.png"
if os.path.exists(logo_file_path):
    st.image(logo_file_path, width=500)

# 用户查询输入框
query = st.text_area(
    "输入您的查询：",
    config.DEFAULT_QUERY,
    height=150,
    help="描述您想要执行的仿真任务，例如：找到使应力达到 360 MPa 的位移"
)

# 提交按钮
if st.button("提交", type="primary"):
    with st.spinner("处理中..."):
        # 创建进度显示容器
        progress_container = st.expander("显示进度", expanded=True)

        # 用于存储所有步骤
        all_steps = []
        final_answer = ""

        # 逐步执行智能体
        try:
            with progress_container:
                for step_state in get_agent_steps(
                    agent_graph,
                    query,
                    stress_threshold=stress_threshold,
                    max_iterations=config.MAX_ITERATIONS
                ):
                    all_steps.append(step_state)

                    # 显示当前步骤
                    for node_name, node_state in step_state.items():
                        st.markdown(f"**节点: {node_name}**")

                        # 显示消息
                        if "messages" in node_state:
                            messages = node_state["messages"]
                            for msg in messages:
                                if isinstance(msg, AIMessage):
                                    if msg.content:
                                        st.markdown(f"🤖 **AI**: {msg.content}")
                                    if hasattr(msg, "tool_calls") and msg.tool_calls:
                                        for tool_call in msg.tool_calls:
                                            st.markdown(
                                                f"🔧 **工具调用**: {tool_call['name']}({tool_call['args']})"
                                            )
                                elif isinstance(msg, ToolMessage):
                                    st.markdown(f"⚙️ **工具结果**: {msg.content}")

                        # 显示迭代信息
                        if "iterations" in node_state:
                            st.markdown(f"*迭代次数: {node_state['iterations']}*")

                        # 显示应力信息
                        if "max_stress" in node_state and node_state["max_stress"] > 0:
                            st.markdown(
                                f"📊 **当前最大应力**: {node_state['max_stress']} MPa "
                                f"(目标: {stress_threshold} MPa)"
                            )

                        # 检查是否有最终答案
                        if "final_answer" in node_state and node_state["final_answer"]:
                            final_answer = node_state["final_answer"]

                        st.markdown("----")

                # 实时记录应力评估
                if config.ENABLE_PHOENIX_TRACING:
                    client = px.Client()
                    log_stress_eval_real_time(client)

        except Exception as e:
            st.error(f"执行出错: {str(e)}")
            import traceback
            st.code(traceback.format_exc())

        # 显示最终答案
        if final_answer:
            st.subheader("最终答案：")
            st.success(final_answer)
        else:
            # 从最后一个状态中提取答案
            if all_steps:
                last_step = all_steps[-1]
                for node_state in last_step.values():
                    if "messages" in node_state:
                        for msg in reversed(node_state["messages"]):
                            if isinstance(msg, AIMessage) and msg.content:
                                st.subheader("最终答案：")
                                st.markdown(msg.content)
                                break

# ============================================================================
# 评估函数
# ============================================================================

def tool_utilization_eval():
    """
    工具利用评估：评估智能体是否选择了正确的工具

    检查项：
    - 工具选择是否正确
    - 工具参数格式是否符合签名
    - 工具调用是否符合逻辑顺序

    Returns:
        评估结果 DataFrame
    """
    judge = OpenAIModel(
        model=llm_type_eval_high,
        api_key=SILICONFLOW_API_KEY,
        api_base=SILICONFLOW_BASE_URL,
        temperature=0
    )

    rails = ["correct", "incorrect"]

    return run_eval(
        span_kind="LLM",
        select=dict(
            start_time="start_time",
            question="input.value",
            output_messages="llm.output_messages",
        ),
        template=TOOL_CALLING_PROMPT_TEMPLATE,
        rails=rails,
        judge=judge,
        eval_name="Tool Utilization",
        post_process=lambda df: pd.DataFrame(
            {
                "question": df["question"],
                "tool_call": df.apply(
                    lambda r: (
                        lambda tool, args: f"{tool}({args})"
                    )(*extract_action(r.output_messages)),
                    axis=1,
                ),
                "tool_definitions": [tools] * len(df),
            },
            index=df.index,
        ),
        retries=2,
    )


def unit_eval():
    """
    单位正确性评估：验证工具调用时参数的物理单位是否正确

    检查项：
    - 位移参数是否使用米（m）
    - 应力输出是否为 MPa
    - 单位转换是否正确

    Returns:
        评估结果 DataFrame
    """
    judge = OpenAIModel(
        model=llm_type_eval,
        api_key=SILICONFLOW_API_KEY,
        api_base=SILICONFLOW_BASE_URL,
        temperature=0
    )

    rails = ["correct", "incorrect"]

    # 构建工具定义查找表
    tool_lookup = {
        tool.name: tool.description
        for tool in tools
    }

    return run_eval(
        span_kind="TOOL",
        select=dict(
            start_time="start_time",
            tool_name="tool.name",
            tool_call="input.value",
            tool_output="output.value",
        ),
        template=TOOL_UNIT_PROMPT_TEMPLATE,
        rails=rails,
        judge=judge,
        eval_name="Unit Check",
        post_process=lambda df: pd.DataFrame(
            {
                "tool_call": df["tool_call"].astype(str),
                "tool_output": df["tool_output"].astype(str),
                "tool_definition": df["tool_name"].map(tool_lookup),
            },
            index=df.index,
        ).dropna(subset=["tool_definition"]),
        retries=2,
    )


def hallucination_eval():
    """
    幻觉检测评估：检查最终答案是否引入了推理步骤中未支持的信息

    检查项：
    - 最终答案是否基于实际的工具输出
    - 是否编造了不存在的数据
    - 是否正确总结了推理过程

    Returns:
        评估结果 DataFrame
    """
    judge = OpenAIModel(
        model=llm_type_eval,
        api_key=SILICONFLOW_API_KEY,
        api_base=SILICONFLOW_BASE_URL,
        temperature=0
    )

    return run_eval(
        span_kind="AGENT",
        select=dict(
            start_time="start_time",
            memory="input.value",
            answer="output.value",
        ),
        template=FINAL_HALLUCINATION_PROMPT_TEMPLATE,
        rails=["hallucinated", "not"],
        judge=judge,
        eval_name="Hallucination",
        post_process=lambda df: df.tail(1),
        num_steps=1,
        retries=2,
    )

# ============================================================================
# 离线评估按钮
# ============================================================================

st.subheader("离线评估")

# 幻觉评估按钮
if st.button("规划正确性：幻觉评估", help="检查最终答案是否基于实际推理步骤"):
    graded = hallucination_eval()
    if graded.empty:
        st.info("在最新追踪中未找到智能体 span。")
    else:
        if graded["score"].iloc[0] == 0:
            st.success("✅ 最终答案标记为正确")
        else:
            st.error("❌ 最终答案标记为不正确")

# 工具映射评估按钮
if st.button("工具利用：工具映射", help="检查智能体是否选择了正确的工具"):
    graded = tool_utilization_eval()
    if graded.empty:
        st.info("在最新追踪中未找到工具调用 LLM span。")
    else:
        correct_count = int(graded['score'].sum())
        total_count = len(graded)
        st.success(f"✅ {correct_count}/{total_count} 次调用标记为正确")

# 单位正确性评估按钮
if st.button("工具利用：单位正确性", help="检查工具调用的参数单位是否正确"):
    graded = unit_eval()
    if graded.empty:
        st.info("在最新追踪中未找到 TOOL span。")
    else:
        correct_count = int(graded['score'].sum())
        total_count = len(graded)
        st.success(f"✅ {correct_count}/{total_count} 次工具调用单位正确")
