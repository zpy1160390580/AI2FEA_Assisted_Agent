"""
AI2FEA 辅助智能体 - 主程序
=========================

这是一个基于 Streamlit 的 Web 应用，使用 AI 智能体自动化 Abaqus 有限元分析工作流。

主要功能：
1. 通过自然语言查询控制 Abaqus 仿真
2. 自动生成输入文件、运行作业、提取应力数据
3. 参数化研究：自动迭代找到满足应力阈值的最优参数
4. 实时评估：追踪工具调用正确性、单位正确性和幻觉检测

技术栈：
- Streamlit: Web 界面
- LlamaIndex: 智能体框架
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
from openinference.instrumentation.llama_index import LlamaIndexInstrumentor
from phoenix.trace.dsl import SpanQuery
import phoenix as px

# LlamaIndex 智能体框架
from llama_index.llms.openai import OpenAI as llma_OpenAI
from llama_index.core.tools import FunctionTool
from llama_index.core.agent import ReActAgent

# Phoenix 评估工具
from phoenix.evals import OpenAIModel

# 导入自定义模块
from FEA_tools.tools import (
    generate_input_file,              # 生成 Abaqus 输入文件
    run_abaqus,                        # 运行 Abaqus 作业
    extract_von_mises_stress_from_ODB, # 从 ODB 提取应力
    extract_action,                    # 解析智能体的工具调用
)
from FEA_tools.prompt_temp import (
    react_system_prompt as RA_SYSTEM_PROMPT,           # ReAct 系统提示词
    TOOL_CALLING_PROMPT_TEMPLATE,                      # 工具调用评估模板
    TOOL_UNIT_PROMPT_TEMPLATE,                         # 单位正确性评估模板
    FINAL_HALLUCINATION_PROMPT_TEMPLATE,               # 幻觉检测评估模板
)
from FEA_tools.eval_utils import (
    run_eval,                          # 运行评估
    log_stress_eval_real_time,         # 实时记录应力评估
)

# 导入配置文件（所有参数都在这里）
from config_files import config

# ============================================================================
# 配置参数
# ============================================================================

# 从配置文件加载参数
stress_threshold = config.STRESS_THRESHOLD              # 应力阈值（MPa）
SILICONFLOW_API_KEY = config.SILICONFLOW_API_KEY       # 硅基流动 API Key
SILICONFLOW_BASE_URL = config.SILICONFLOW_BASE_URL     # API 基础 URL
DEFAULT_MODEL = config.MODEL_NAME                       # 主模型名称
DEFAULT_EVAL_MODEL = config.EVAL_MODEL_NAME            # 评估模型名称
DEFAULT_EVAL_MODEL_HIGH = config.EVAL_MODEL_HIGH_REASONING  # 高推理评估模型

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
        # 为 LlamaIndex 添加追踪
        LlamaIndexInstrumentor().instrument(skip_dep_check=True, tracer_provider=tp)
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
# 工具定义
# ============================================================================

# 工具 1: Abaqus 输入文件生成器
abaqus_input_file_tool = FunctionTool.from_defaults(
    fn=generate_input_file,
    name="Abaqus_input_file_generator",
    description=(
        "生成带有指定位移的 Abaqus 输入文件（单位：米）。"
        "位移不应超过 0.2 米。"
    ),
)

# 工具 2: Abaqus 作业执行器
abaqus_job_execution_tool = FunctionTool.from_defaults(
    fn=run_abaqus,
    name="Abaqus_job_executor",
    description="运行 Abaqus 作业（使用 cantilever_beam.inp）并收集输出文件。",
)

# 工具 3: Von-Mises 应力提取器
von_mises_stress_extraction_tool = FunctionTool.from_defaults(
    fn=extract_von_mises_stress_from_ODB,
    name="Von_Mises_stress_extractor",
    description="从 ODB 文件中提取最大 Von-Mises 应力（返回单位：MPa）。",
)

# 工具列表（智能体可用的所有工具）
tools = [
    abaqus_input_file_tool,
    abaqus_job_execution_tool,
    von_mises_stress_extraction_tool,
]

# ============================================================================
# 智能体初始化
# ============================================================================

if "agent" not in st.session_state:
    """
    初始化 ReAct 智能体（仅在首次运行时执行）

    ReAct (Reasoning + Acting) 架构：
    1. Thought: 智能体分析当前状态并决定下一步行动
    2. Action: 选择并调用工具
    3. Observation: 接收工具返回的结果
    4. 重复上述循环直到任务完成
    """

    # 初始化大语言模型（使用硅基流动平台）
    llm = llma_OpenAI(
        model=llm_type,                      # 模型名称
        api_key=SILICONFLOW_API_KEY,         # API Key
        api_base=SILICONFLOW_BASE_URL,       # API 基础 URL
        temperature=config.TEMPERATURE,       # 温度参数（控制随机性）
        max_tokens=config.MAX_TOKENS          # 最大输出 tokens
    )

    # 创建 ReAct 智能体
    st.session_state.agent = ReActAgent.from_tools(
        tools,                                # 可用工具列表
        llm=llm,                              # 大语言模型
        verbose=config.VERBOSE,               # 是否显示详细日志
        max_iterations=config.MAX_ITERATIONS  # 最大迭代次数
    )

    # 更新智能体的系统提示词
    with suppress_tracing():
        st.session_state.agent.update_prompts({
            "agent_worker:system_prompt": RA_SYSTEM_PROMPT()
        })

# 获取智能体实例
agent = st.session_state.agent

# ============================================================================
# 用户界面
# ============================================================================

# 页面标题
st.title(config.PAGE_TITLE)

# 项目介绍
st.markdown("""
这个 AI 智能体与 Abaqus 无缝集成，自动化仿真工作流，包括模型生成、作业运行和应力数据提取。它简化了以下关键步骤：

1. **模型输入生成：** 使用 `generate_input_file` 函数，智能体根据指定参数（如位移）创建 Abaqus 输入文件（`.inp`）。生成的文件被移动到指定目录以供作业执行。

2. **作业执行：** `run_abaqus` 函数使用准备好的输入文件启动 Abaqus 仿真。完成后，所有相关输出文件被重新定位到特定目录以便组织和后续分析。

3. **应力提取：** 利用 `extract_von_mises_stress_from_ODB` 函数，智能体从仿真输出数据库（ODB）中提取 Von-Mises 应力数据。此信息保存在文件（`max_vm_stress.txt`）中，并存储在同一目录中以便访问。

凭借其模块化设计和对 `os`、`subprocess` 和 `shutil` 等工具的依赖，智能体确保高效处理文件和仿真过程，实现强大的自动化应力分析。

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
        # 创建智能体任务
        task = agent.create_task(query)

        # 显示进度（可展开）
        with st.expander("显示进度", expanded=True):
            client = px.Client()

            # 执行第一步
            step_output = agent.run_step(task.task_id)
            st.markdown(step_output.dict()["output"]["response"])
            log_stress_eval_real_time(client)

            # 循环执行直到任务完成
            while not step_output.is_last:
                step_output = agent.run_step(task.task_id)
                st.markdown(step_output.dict()["output"]["response"])
                log_stress_eval_real_time(client)

        # 获取最终答案
        final_answer = step_output.dict()["output"]["response"]

        # 显示最终答案
        st.subheader("最终答案：")
        st.markdown(final_answer)

        # 显示中间推理步骤（可展开）
        st.subheader("中间推理和执行步骤：")
        with st.expander("显示步骤"):
            with suppress_tracing():
                completed = agent.get_completed_tasks()[-1]

            # 遍历所有推理步骤
            for step in completed.extra_state["current_reasoning"]:
                for k, v in step.dict().items():
                    # 过滤掉不需要显示的字段
                    if k not in ("return_direct", "action_input", "is_streaming"):
                        st.markdown(
                            f"<span style='color:darkblue;font-weight:bold;'>{k}</span>: {v}",
                            unsafe_allow_html=True,
                        )
                st.markdown("----")

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
    # 使用高推理模型作为评判者
    judge = OpenAIModel(
        model=llm_type_eval_high,
        api_key=SILICONFLOW_API_KEY,
        api_base=SILICONFLOW_BASE_URL,
        temperature=0  # 评估时使用确定性输出
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
        (getattr(t.metadata, "name", None) if hasattr(t, "metadata") else getattr(t, "name", None)): (
            t.metadata.description if hasattr(t, "metadata") else ""
        )
        for t in tools
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
        post_process=lambda df: df.tail(1),  # 只评估最后一个答案
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
