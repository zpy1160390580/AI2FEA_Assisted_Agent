"""
AI2FEA 辅助智能体 - 配置文件

本文件包含所有可配置参数，方便快速开始和自定义设置。
所有参数都有详细注释说明其用途和推荐值。
"""

import os
from dotenv import load_dotenv

# 加载环境变量（从 .env 文件）
load_dotenv(override=True)

# ============================================================================
# API 配置
# ============================================================================

# 硅基流动平台 API Key
# 获取方式：访问 https://cloud.siliconflow.cn/account/ak 创建 API Key
# 必填项，没有此 Key 无法运行
SILICONFLOW_API_KEY = os.getenv("SILICONFLOW_API_KEY")

# 硅基流动平台 API 基础 URL
# 默认值：https://api.siliconflow.cn/v1
# 一般无需修改，除非使用自定义端点
SILICONFLOW_BASE_URL = os.getenv(
    "SILICONFLOW_BASE_URL",
    "https://api.siliconflow.cn/v1"
)

# ============================================================================
# 模型配置
# ============================================================================

# 主模型名称（用于智能体推理）
# 推荐选项：
#   - "deepseek-ai/DeepSeek-V3"：通用任务，性能强、成本低（推荐）
#   - "deepseek-ai/DeepSeek-R1"：复杂推理任务，推理能力更强
#   - "Qwen/Qwen2.5-72B-Instruct"：阿里通义千问，中文友好
MODEL_NAME = os.getenv("MODEL_NAME", "deepseek-ai/DeepSeek-V3")

# 评估模型名称（用于工具调用和单位正确性评估）
# 推荐：与主模型保持一致，或选择成本更低的模型
EVAL_MODEL_NAME = os.getenv("EVAL_MODEL_NAME", "deepseek-ai/DeepSeek-V3")

# 高推理评估模型（用于复杂评估任务，如工具调用正确性）
# 推荐：使用 DeepSeek-V3 或 DeepSeek-R1
EVAL_MODEL_HIGH_REASONING = os.getenv(
    "EVAL_MODEL_HIGH_REASONING",
    "deepseek-ai/DeepSeek-V3.2"
)

# 温度参数（控制输出的随机性）
# 范围：0.0 - 1.0
# - 0.0：完全确定性，适合需要精确结果的任务
# - 0.7：平衡创造性和准确性（推荐）
# - 1.0：最大随机性，适合创意任务
TEMPERATURE = 0.7

# 最大输出 tokens 数
# 范围：1 - 模型上下文窗口大小
# DeepSeek-V3 支持最大 64K tokens，但建议设置为 4096 以控制成本
MAX_TOKENS = 4096

# ============================================================================
# 仿真配置
# ============================================================================

# 应力阈值（单位：MPa）
# 用于参数化研究中判断是否达到目标应力
# 默认值：360.0 MPa
# 可根据具体材料和设计要求调整
STRESS_THRESHOLD = float(os.getenv("STRESS_THRESHOLD", 360.0))

# 智能体最大迭代次数
# 防止智能体陷入无限循环
# 推荐值：50-100
# 如果任务复杂，可适当增加
MAX_ITERATIONS = 100

# ============================================================================
# Abaqus 配置
# ============================================================================

# Abaqus 输入文件名称
# 默认：cantilever_beam.inp（悬臂梁模型）
# 如需使用其他模型，修改此参数和对应的 Abaqus 脚本
ABAQUS_INPUT_FILE = "cantilever_beam.inp"

# Abaqus 作业名称
# 默认：cantilever_beam
# 应与输入文件名称保持一致（不含 .inp 扩展名）
ABAQUS_JOB_NAME = "cantilever_beam"

# Abaqus 文件存储目录
# 所有生成的 .inp、.odb、.dat 等文件都存储在此目录
# 默认：FEA_Results
ABAQUS_FILES_DIR = "FEA_Results"

# 最大位移限制（单位：米）
# 防止智能体尝试过大的位移导致仿真失败
# 默认：0.2 m
MAX_DISPLACEMENT = 0.2

# ============================================================================
# Phoenix 可观测性配置（可选）
# ============================================================================

# Phoenix OTEL 导出端点
# 如果您部署了 Phoenix 服务器，填入其地址
# 默认：None（不使用 Phoenix）
# 示例：http://localhost:6006
OTEL_EXPORTER_OTLP_ENDPOINT = os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT", None)

# 是否启用 Phoenix 追踪
# True：启用追踪和评估功能
# False：禁用追踪（可减少开销）
ENABLE_PHOENIX_TRACING = OTEL_EXPORTER_OTLP_ENDPOINT is not None

# ============================================================================
# Streamlit UI 配置
# ============================================================================

# 页面标题
PAGE_TITLE = "AI2FEA 有限元分析辅助智能体"

# 页面图标（emoji 或图片路径）
PAGE_ICON = "🤖"

# 侧边栏默认展开状态
# "auto"：自动
# "expanded"：展开
# "collapsed"：折叠
SIDEBAR_STATE = "auto"

# 默认查询文本
# 用户首次打开应用时显示的示例查询
DEFAULT_QUERY = (
    f"对于悬臂梁，当管道向下位移 0.02 m 时，获取最大 von Mises 应力。"
    f"然后逐步增加位移，直到 von Mises 应力达到约 {STRESS_THRESHOLD} MPa，"
    f"同时最小化仿真次数。"
)

# ============================================================================
# 日志配置
# ============================================================================

# 日志级别
# "DEBUG"：详细调试信息
# "INFO"：一般信息（推荐）
# "WARNING"：警告信息
# "ERROR"：错误信息
LOG_LEVEL = "INFO"

# 是否在控制台显示详细日志
VERBOSE = True

# ============================================================================
# 高级配置（一般无需修改）
# ============================================================================

# ReAct 智能体提示词语言
# "zh"：中文
# "en"：英文
PROMPT_LANGUAGE = "zh"

# 工具调用超时时间（秒）
# Abaqus 仿真可能需要较长时间，建议设置较大值
TOOL_TIMEOUT = 600  # 10 分钟

# 评估重试次数
# 如果评估失败，自动重试的次数
EVAL_RETRIES = 2

# 是否在评估中提供解释
# True：评估结果包含详细解释
# False：仅返回评分
EVAL_PROVIDE_EXPLANATION = True

# ============================================================================
# 验证配置
# ============================================================================

def validate_config():
    """
    验证配置是否正确
    如果配置有误，抛出异常并提示用户
    """
    errors = []

    # 检查必填项
    if not SILICONFLOW_API_KEY:
        errors.append(
            "❌ 缺少 SILICONFLOW_API_KEY！\n"
            "   请在 .env 文件中配置您的 API Key。\n"
            "   获取方式：https://cloud.siliconflow.cn/account/ak"
        )

    # 检查温度参数范围
    if not 0.0 <= TEMPERATURE <= 1.0:
        errors.append(
            f"❌ TEMPERATURE 参数超出范围！\n"
            f"   当前值：{TEMPERATURE}，有效范围：0.0 - 1.0"
        )

    # 检查应力阈值
    if STRESS_THRESHOLD <= 0:
        errors.append(
            f"❌ STRESS_THRESHOLD 必须为正数！\n"
            f"   当前值：{STRESS_THRESHOLD}"
        )

    # 检查最大位移
    if MAX_DISPLACEMENT <= 0:
        errors.append(
            f"❌ MAX_DISPLACEMENT 必须为正数！\n"
            f"   当前值：{MAX_DISPLACEMENT}"
        )

    # 如果有错误，打印并抛出异常
    if errors:
        error_message = "\n\n".join(errors)
        print("\n" + "="*60)
        print("配置验证失败！")
        print("="*60)
        print(error_message)
        print("="*60 + "\n")
        raise ValueError("配置验证失败，请检查上述错误信息。")

    # 验证通过，打印配置摘要
    if VERBOSE:
        print("\n" + "="*60)
        print("✅ 配置验证通过！")
        print("="*60)
        print(f"主模型：{MODEL_NAME}")
        print(f"评估模型：{EVAL_MODEL_NAME}")
        print(f"应力阈值：{STRESS_THRESHOLD} MPa")
        print(f"最大迭代次数：{MAX_ITERATIONS}")
        print(f"Phoenix 追踪：{'启用' if ENABLE_PHOENIX_TRACING else '禁用'}")
        print("="*60 + "\n")

# 自动验证配置（导入时执行）
if __name__ != "__main__":
    try:
        validate_config()
    except ValueError as e:
        # 配置错误时不阻止导入，但会在运行时报错
        pass

# ============================================================================
# 使用示例
# ============================================================================

if __name__ == "__main__":
    """
    直接运行此文件可查看当前配置
    """
    print("\n" + "="*60)
    print("AI2FEA 辅助智能体 - 当前配置")
    print("="*60)

    print("\n【API 配置】")
    print(f"  API Key: {'已配置' if SILICONFLOW_API_KEY else '未配置'}")
    print(f"  API URL: {SILICONFLOW_BASE_URL}")

    print("\n【模型配置】")
    print(f"  主模型: {MODEL_NAME}")
    print(f"  评估模型: {EVAL_MODEL_NAME}")
    print(f"  高推理模型: {EVAL_MODEL_HIGH_REASONING}")
    print(f"  温度: {TEMPERATURE}")
    print(f"  最大 Tokens: {MAX_TOKENS}")

    print("\n【仿真配置】")
    print(f"  应力阈值: {STRESS_THRESHOLD} MPa")
    print(f"  最大迭代次数: {MAX_ITERATIONS}")
    print(f"  输入文件: {ABAQUS_INPUT_FILE}")
    print(f"  作业名称: {ABAQUS_JOB_NAME}")
    print(f"  文件目录: {ABAQUS_FILES_DIR}")
    print(f"  最大位移: {MAX_DISPLACEMENT} m")

    print("\n【可观测性配置】")
    print(f"  Phoenix 追踪: {'启用' if ENABLE_PHOENIX_TRACING else '禁用'}")
    if ENABLE_PHOENIX_TRACING:
        print(f"  OTEL 端点: {OTEL_EXPORTER_OTLP_ENDPOINT}")

    print("\n【UI 配置】")
    print(f"  页面标题: {PAGE_TITLE}")
    print(f"  页面图标: {PAGE_ICON}")
    print(f"  侧边栏状态: {SIDEBAR_STATE}")

    print("\n" + "="*60)

    # 运行验证
    try:
        validate_config()
        print("\n✅ 所有配置验证通过！可以正常运行应用。\n")
    except ValueError as e:
        print(f"\n❌ 配置验证失败：{e}\n")
