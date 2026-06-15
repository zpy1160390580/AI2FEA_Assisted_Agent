"""
AI2FEA 辅助智能体 - LangGraph 状态图定义
==========================================

基于 LangGraph 的状态图实现，用于自动化 Abaqus 仿真工作流。

状态图结构：
    START → 推理节点 → 决策节点 → [工具节点] → 检查节点 → [继续 OR 结束]

节点说明：
- reasoning_node: 使用 LLM 分析当前状态并决定下一步行动
- tool_nodes: 执行具体工具（生成输入、运行仿真、提取应力）
- should_continue: 判断是否继续迭代
- check_stress: 检查应力是否达标

作者：AI2FEA Team
"""

import operator
from typing import Annotated, TypedDict, Literal
import json

from langchain_openai import ChatOpenAI
from langchain_core.messages import BaseMessage, HumanMessage, AIMessage, ToolMessage
from langgraph.graph import StateGraph, END
from langgraph.prebuilt import ToolNode

# 导入自定义工具
from FEA_tools.tools import (
    generate_input_file,
    run_abaqus,
    extract_von_mises_stress_from_ODB,
)
from FEA_tools.prompt_temp import react_system_prompt

# ============================================================================
# 状态定义
# ============================================================================

class AgentState(TypedDict):
    """
    智能体的状态定义

    Attributes:
        messages: 对话历史（包括用户消息、AI 消息、工具调用结果）
        iterations: 当前迭代次数
        max_stress: 当前最大应力值（MPa）
        current_displacement: 当前位移值（m）
        stress_threshold: 应力阈值（MPa）
        max_iterations: 最大迭代次数
        final_answer: 最终答案
    """
    messages: Annotated[list[BaseMessage], operator.add]
    iterations: int
    max_stress: float
    current_displacement: float
    stress_threshold: float
    max_iterations: int
    final_answer: str


# ============================================================================
# 工具定义（转换为 LangChain 工具格式）
# ============================================================================

from langchain_core.tools import tool

@tool
def abaqus_input_file_generator(applied_displacement: float) -> str:
    """
    生成带有指定位移的 Abaqus 输入文件。

    Args:
        applied_displacement: 应用的位移（单位：米，不应超过 0.2 米）

    Returns:
        操作结果的字符串描述
    """
    return generate_input_file(applied_displacement)


@tool
def abaqus_job_executor() -> str:
    """
    运行 Abaqus 仿真作业（使用 cantilever_beam.inp）并收集输出文件。

    Returns:
        作业执行结果的字符串描述
    """
    return run_abaqus()


@tool
def von_mises_stress_extractor() -> str:
    """
    从 ODB 文件中提取最大 Von-Mises 应力。

    Returns:
        最大应力值（单位：MPa）的字符串
    """
    return extract_von_mises_stress_from_ODB()


# 工具列表
tools = [
    abaqus_input_file_generator,
    abaqus_job_executor,
    von_mises_stress_extractor,
]


# ============================================================================
# 节点函数
# ============================================================================

def reasoning_node(state: AgentState, llm: ChatOpenAI) -> dict:
    """
    推理节点：使用 LLM 分析当前状态并决定下一步行动

    Args:
        state: 当前状态
        llm: 语言模型实例

    Returns:
        更新后的状态字典
    """
    # 检查迭代次数
    if state["iterations"] >= state["max_iterations"]:
        return {
            "final_answer": f"达到最大迭代次数 {state['max_iterations']}，停止执行。",
            "iterations": state["iterations"] + 1,
        }

    # 绑定工具到 LLM
    llm_with_tools = llm.bind_tools(tools)

    # 调用 LLM
    response = llm_with_tools.invoke(state["messages"])

    return {
        "messages": [response],
        "iterations": state["iterations"] + 1,
    }


def should_continue(state: AgentState) -> Literal["tools", "check_stress", "end"]:
    """
    决策节点：判断下一步应该做什么

    Args:
        state: 当前状态

    Returns:
        下一个节点的名称
    """
    messages = state["messages"]
    last_message = messages[-1]

    # 如果达到最大迭代次数，结束
    if state["iterations"] >= state["max_iterations"]:
        return "end"

    # 如果 LLM 调用了工具，执行工具
    if hasattr(last_message, "tool_calls") and last_message.tool_calls:
        tool_name = last_message.tool_calls[0]["name"]
        # 如果是提取应力的工具，执行后需要检查应力
        if tool_name == "von_mises_stress_extractor":
            return "tools"
        return "tools"

    # 否则结束（LLM 给出了最终答案）
    return "end"


def check_stress_node(state: AgentState) -> dict:
    """
    检查应力节点：在提取应力后检查是否达到阈值

    Args:
        state: 当前状态

    Returns:
        更新后的状态字典
    """
    messages = state["messages"]

    # 查找最后一个工具调用结果
    for msg in reversed(messages):
        if isinstance(msg, ToolMessage):
            # 尝试从消息中提取应力值
            content = msg.content
            try:
                # 假设返回格式类似 "最大 Von-Mises 应力: 123.45 MPa"
                if "MPa" in content:
                    stress_str = content.split(":")[-1].strip().replace("MPa", "").strip()
                    stress_value = float(stress_str)

                    # 更新状态
                    new_state = {
                        "max_stress": stress_value,
                    }

                    # 检查是否达到阈值
                    if abs(stress_value - state["stress_threshold"]) <= 10:  # 允许 ±10 MPa 误差
                        new_state["final_answer"] = (
                            f"成功找到满足条件的位移参数！\n"
                            f"位移：{state['current_displacement']} m\n"
                            f"应力：{stress_value} MPa\n"
                            f"目标应力：{state['stress_threshold']} MPa\n"
                            f"总迭代次数：{state['iterations']}"
                        )

                    return new_state
            except (ValueError, IndexError):
                pass
            break

    return {}


def should_continue_after_check(state: AgentState) -> Literal["reasoning", "end"]:
    """
    检查后的决策节点：判断是否继续迭代

    Args:
        state: 当前状态

    Returns:
        下一个节点的名称
    """
    # 如果已经有最终答案，结束
    if state.get("final_answer"):
        return "end"

    # 如果达到最大迭代次数，结束
    if state["iterations"] >= state["max_iterations"]:
        return "end"

    # 否则继续推理
    return "reasoning"


# ============================================================================
# 构建状态图
# ============================================================================

def create_graph(
    llm: ChatOpenAI,
    stress_threshold: float = 360.0,
    max_iterations: int = 100,
) -> StateGraph:
    """
    创建 LangGraph 状态图

    Args:
        llm: 语言模型实例
        stress_threshold: 应力阈值（MPa）
        max_iterations: 最大迭代次数

    Returns:
        编译后的状态图
    """
    # 初始化状态图
    workflow = StateGraph(AgentState)

    # 添加节点
    workflow.add_node("reasoning", lambda state: reasoning_node(state, llm))
    workflow.add_node("tools", ToolNode(tools))
    workflow.add_node("check_stress", check_stress_node)

    # 设置入口点
    workflow.set_entry_point("reasoning")

    # 添加条件边
    workflow.add_conditional_edges(
        "reasoning",
        should_continue,
        {
            "tools": "tools",
            "check_stress": "check_stress",
            "end": END,
        }
    )

    # 工具执行后回到推理节点
    workflow.add_edge("tools", "reasoning")

    # 检查应力后的条件边
    workflow.add_conditional_edges(
        "check_stress",
        should_continue_after_check,
        {
            "reasoning": "reasoning",
            "end": END,
        }
    )

    # 编译图
    app = workflow.compile()

    return app


# ============================================================================
# 辅助函数
# ============================================================================

def run_agent(
    app: StateGraph,
    query: str,
    stress_threshold: float = 360.0,
    max_iterations: int = 100,
) -> dict:
    """
    运行智能体

    Args:
        app: 编译后的状态图
        query: 用户查询
        stress_threshold: 应力阈值（MPa）
        max_iterations: 最大迭代次数

    Returns:
        最终状态
    """
    # 初始化状态
    initial_state = {
        "messages": [HumanMessage(content=query)],
        "iterations": 0,
        "max_stress": 0.0,
        "current_displacement": 0.0,
        "stress_threshold": stress_threshold,
        "max_iterations": max_iterations,
        "final_answer": "",
    }

    # 运行图
    final_state = app.invoke(initial_state)

    return final_state


def get_agent_steps(
    app: StateGraph,
    query: str,
    stress_threshold: float = 360.0,
    max_iterations: int = 100,
):
    """
    逐步运行智能体（用于 Streamlit 实时显示）

    Args:
        app: 编译后的状态图
        query: 用户查询
        stress_threshold: 应力阈值（MPa）
        max_iterations: 最大迭代次数

    Yields:
        每一步的状态
    """
    # 初始化状态
    initial_state = {
        "messages": [HumanMessage(content=query)],
        "iterations": 0,
        "max_stress": 0.0,
        "current_displacement": 0.0,
        "stress_threshold": stress_threshold,
        "max_iterations": max_iterations,
        "final_answer": "",
    }

    # 逐步执行
    for step_state in app.stream(initial_state):
        yield step_state
