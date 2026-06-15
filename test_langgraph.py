"""
LangGraph 实现测试脚本
=====================

测试新的 LangGraph 状态图实现是否正常工作

运行方式：
    python test_langgraph.py
"""

import os
import sys
from dotenv import load_dotenv

# 加载环境变量
load_dotenv()

# 导入配置
from config_files import config

# 导入 LangGraph 组件
from langchain_openai import ChatOpenAI
from graph_agent import create_graph, run_agent

def test_llm_connection():
    """测试 LLM 连接"""
    print("\n" + "="*60)
    print("测试 1: LLM 连接")
    print("="*60)

    try:
        llm = ChatOpenAI(
            model=config.MODEL_NAME,
            api_key=config.SILICONFLOW_API_KEY,
            base_url=config.SILICONFLOW_BASE_URL,
            temperature=config.TEMPERATURE,
            max_tokens=1000
        )

        response = llm.invoke("你好，请回复'连接成功'")
        print(f"✅ LLM 连接成功！")
        print(f"响应: {response.content}")
        return True
    except Exception as e:
        print(f"❌ LLM 连接失败: {e}")
        return False


def test_graph_creation():
    """测试状态图创建"""
    print("\n" + "="*60)
    print("测试 2: 状态图创建")
    print("="*60)

    try:
        llm = ChatOpenAI(
            model=config.MODEL_NAME,
            api_key=config.SILICONFLOW_API_KEY,
            base_url=config.SILICONFLOW_BASE_URL,
            temperature=config.TEMPERATURE,
            max_tokens=config.MAX_TOKENS
        )

        from FEA_tools.prompt_temp import react_system_prompt
        llm = llm.bind(system=react_system_prompt())

        app = create_graph(
            llm=llm,
            stress_threshold=config.STRESS_THRESHOLD,
            max_iterations=config.MAX_ITERATIONS
        )

        print(f"✅ 状态图创建成功！")
        print(f"节点数: {len(app.get_graph().nodes)}")
        print(f"边数: {len(app.get_graph().edges)}")

        # 打印图结构
        print("\n图结构:")
        for node_name in app.get_graph().nodes.keys():
            print(f"  - {node_name}")

        return True, app
    except Exception as e:
        print(f"❌ 状态图创建失败: {e}")
        import traceback
        traceback.print_exc()
        return False, None


def test_simple_query():
    """测试简单查询（不实际运行 Abaqus）"""
    print("\n" + "="*60)
    print("测试 3: 简单查询测试")
    print("="*60)

    try:
        llm = ChatOpenAI(
            model=config.MODEL_NAME,
            api_key=config.SILICONFLOW_API_KEY,
            base_url=config.SILICONFLOW_BASE_URL,
            temperature=config.TEMPERATURE,
            max_tokens=config.MAX_TOKENS
        )

        from FEA_tools.prompt_temp import react_system_prompt
        llm = llm.bind(system=react_system_prompt())

        app = create_graph(
            llm=llm,
            stress_threshold=config.STRESS_THRESHOLD,
            max_iterations=5  # 限制迭代次数
        )

        # 简单的测试查询
        test_query = "请说明你有哪些可用的工具？"

        print(f"查询: {test_query}")
        print("\n执行中...")

        final_state = run_agent(
            app=app,
            query=test_query,
            stress_threshold=config.STRESS_THRESHOLD,
            max_iterations=5
        )

        print(f"\n✅ 查询执行成功！")
        print(f"迭代次数: {final_state['iterations']}")

        # 打印最后一条 AI 消息
        from langchain_core.messages import AIMessage
        for msg in reversed(final_state['messages']):
            if isinstance(msg, AIMessage) and msg.content:
                print(f"\nAI 回复:\n{msg.content}")
                break

        return True
    except Exception as e:
        print(f"❌ 查询执行失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_tool_binding():
    """测试工具绑定"""
    print("\n" + "="*60)
    print("测试 4: 工具绑定")
    print("="*60)

    try:
        from graph_agent import tools

        print(f"工具数量: {len(tools)}")
        for tool in tools:
            print(f"  - {tool.name}: {tool.description}")

        # 测试 LLM 是否能正确绑定工具
        llm = ChatOpenAI(
            model=config.MODEL_NAME,
            api_key=config.SILICONFLOW_API_KEY,
            base_url=config.SILICONFLOW_BASE_URL,
            temperature=0,
            max_tokens=1000
        )

        llm_with_tools = llm.bind_tools(tools)

        response = llm_with_tools.invoke("请列出你可以调用的工具")

        print(f"\n✅ 工具绑定成功！")
        print(f"LLM 响应: {response.content[:200]}...")

        return True
    except Exception as e:
        print(f"❌ 工具绑定失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """运行所有测试"""
    print("\n" + "="*60)
    print("LangGraph 实现测试套件")
    print("="*60)

    # 检查配置
    if not config.SILICONFLOW_API_KEY:
        print("❌ 错误: 未配置 SILICONFLOW_API_KEY")
        print("请在 config_files/.env 文件中配置您的 API Key")
        sys.exit(1)

    print(f"\n配置信息:")
    print(f"  模型: {config.MODEL_NAME}")
    print(f"  API URL: {config.SILICONFLOW_BASE_URL}")
    print(f"  应力阈值: {config.STRESS_THRESHOLD} MPa")
    print(f"  最大迭代次数: {config.MAX_ITERATIONS}")

    # 运行测试
    results = []

    # 测试 1: LLM 连接
    results.append(("LLM 连接", test_llm_connection()))

    # 测试 2: 状态图创建
    success, app = test_graph_creation()
    results.append(("状态图创建", success))

    # 测试 3: 工具绑定
    results.append(("工具绑定", test_tool_binding()))

    # 测试 4: 简单查询
    if success:
        results.append(("简单查询", test_simple_query()))
    else:
        results.append(("简单查询", False))

    # 汇总结果
    print("\n" + "="*60)
    print("测试结果汇总")
    print("="*60)

    for test_name, result in results:
        status = "✅ 通过" if result else "❌ 失败"
        print(f"{test_name}: {status}")

    passed = sum(1 for _, result in results if result)
    total = len(results)

    print(f"\n总计: {passed}/{total} 测试通过")

    if passed == total:
        print("\n🎉 所有测试通过！LangGraph 实现正常工作。")
        print("\n下一步：运行 'streamlit run main.py' 启动完整应用")
    else:
        print("\n⚠️ 部分测试失败，请检查错误信息")

    return passed == total


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
