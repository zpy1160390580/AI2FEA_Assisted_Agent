# CLAUDE.md

本文件为 Claude Code (claude.ai/code) 在此仓库中工作时提供指导。

## 项目概述

**AI2FEA_Assisted_Agent** 是一个基于 AI 的有限元分析辅助系统，通过 LlamaIndex 和 OpenAI 模型自动化 Abaqus 仿真工作流。该项目实现了从模型生成、作业执行到应力提取的全流程自动化，并集成了 Phoenix 可观测性平台用于追踪和评估智能体的决策质量。

### 核心功能
- **智能体驱动的仿真自动化**：使用 ReAct (Reasoning + Acting) 架构的 AI 智能体自动规划和执行 Abaqus 仿真任务
- **参数化研究**：自动执行多次仿真以找到满足应力阈值的最优位移参数
- **实时评估**：通过 Phoenix 追踪工具调用、单位正确性和幻觉检测
- **交互式界面**：Streamlit Web 应用提供用户友好的查询和结果展示

---

## 项目结构

```
AI2FEA_Assisted_Agent/
├── app.py                          # Streamlit 主应用程序
├── demo.ipynb                      # 演示 Jupyter Notebook
├── requirements.txt                # Python 依赖
├── src/
│   ├── tools.py                    # 核心工具函数（生成输入文件、运行作业、提取应力）
│   ├── prompt_temp.py              # ReAct 系统提示词和评估模板
│   ├── eval_utils.py               # 评估工具函数
│   └── utils/
│       ├── create_inp_file.py      # Abaqus Python 脚本：生成 .inp 文件
│       └── retrieve_vm_stress.py   # Abaqus Python 脚本：从 ODB 提取应力
└── artifacts/                      # 存储图像和其他资源
```

---

## 技术架构

### 核心技术栈
- **LlamaIndex**：智能体框架，提供 ReActAgent 和工具集成
- **OpenAI API**：驱动智能体推理和评估判断（支持 gpt-4o、gpt-4.1 等模型）
- **Streamlit**：Web 应用框架
- **Phoenix (Arize)**：可观测性平台，用于追踪和评估
- **Abaqus**：有限元分析软件（需要本地安装）

### 智能体架构
项目使用 **ReAct (Reasoning + Acting)** 模式：
1. **Thought**：智能体分析当前状态并决定下一步行动
2. **Action**：选择并调用工具（如生成输入文件、运行作业）
3. **Observation**：接收工具返回的结果
4. 重复上述循环直到任务完成

### 三个核心工具
1. **Abaqus_input_file_generator**
   - 功能：生成参数化的 Abaqus 输入文件
   - 参数：`applied_displacement` (单位：米，不超过 0.2m)
   - 实现：调用 `src/utils/create_inp_file.py` 通过 Abaqus CAE 生成 `.inp` 文件

2. **Abaqus_job_executor**
   - 功能：执行 Abaqus 仿真作业
   - 实现：运行 `abaqus job=cantilever_beam` 命令并收集输出文件

3. **Von_Mises_stress_extractor**
   - 功能：从 ODB 文件提取最大 Von-Mises 应力
   - 返回：应力值（单位：MPa）
   - 实现：调用 `src/utils/retrieve_vm_stress.py` 解析 ODB 数据库

---

## 评估系统

项目集成了三层评估机制：

### 1. 工具调用正确性评估 (Tool Utilization)
- 评估智能体是否选择了正确的工具来回答用户问题
- 检查工具调用的参数格式是否符合工具签名
- 使用高推理能力模型（如 gpt-4.1）作为评判者

### 2. 单位正确性评估 (Unit Check)
- 验证工具调用时参数的物理单位是否正确
- 例如：位移参数应为米 (m)，应力输出应为 MPa
- 防止单位不一致导致的计算错误

### 3. 幻觉检测 (Hallucination Eval)
- 检查最终答案是否引入了推理步骤中未支持的信息
- 确保智能体的结论基于实际的工具输出而非臆测

### 4. 实时应力阈值监控
- 在每次提取应力后，自动记录是否超过 `STRESS_THRESHOLD`
- 通过 Phoenix 的 span evaluations 实时追踪

---

## 开发指南

### 环境要求
- **Python 3.8+**
- **Abaqus**（需要本地安装并配置环境变量）
- **OpenAI API Key**（需要在 `.env` 文件中配置）

### 安装步骤
```bash
# 克隆仓库
git clone <repository_url>
cd AI2FEA_Assisted_Agent

# 安装依赖
pip install -r requirements.txt

# 配置环境变量
# 创建 .env 文件并添加：
# OPENAI_API_KEY=your_api_key_here
# STRESS_THRESHOLD=360.0  # 可选，默认 360 MPa
# OTEL_EXPORTER_OTLP_ENDPOINT=your_phoenix_endpoint  # 可选
```

### 运行应用
```bash
streamlit run app.py
```

### 典型使用场景
用户查询示例：
```
对于悬臂梁，当管道向下位移 0.02 m 时，获取最大 von Mises 应力。
然后逐步增加位移，直到 von Mises 应力达到约 360 MPa，同时最小化仿真次数。
```

智能体执行流程：
1. 生成位移为 0.02m 的输入文件
2. 运行 Abaqus 作业
3. 提取应力（假设为 150 MPa）
4. 推理：需要更大位移，尝试 0.05m
5. 重复步骤 1-3
6. 当应力接近 360 MPa 时停止并报告结果

---

## 代码约定

### Abaqus 脚本调用
- 所有 Abaqus 命令通过 `subprocess.run()` 执行
- 使用 `shell=True` 以支持 Windows 环境
- 输入文件和输出文件统一存储在 `src/abaqus_files/` 目录

### 工具函数设计原则
- 每个工具函数必须有清晰的 docstring 说明单位
- 返回值应为字符串格式，便于智能体解析
- 错误处理：捕获 `subprocess.CalledProcessError` 并打印详细错误信息

### 提示词工程
- ReAct 系统提示词在 `src/prompt_temp.py` 中定义
- 关键约束：
  - 必须使用正确的工具
  - 单位必须一致（需要时进行转换）
  - 参数化研究必须串行执行（不能并行运行多个作业）
  - 最终答案必须包含推理步骤的要点

### 评估模板
- 所有评估提示词使用单词回答（"correct"/"incorrect"、"hallucinated"/"not"）
- 评估结果通过 Phoenix 的 `SpanEvaluations` API 记录

---

## 扩展建议

### 添加新工具
1. 在 `src/tools.py` 中定义新函数
2. 使用 `FunctionTool.from_defaults()` 包装为 LlamaIndex 工具
3. 在 `app.py` 的 `tools` 列表中注册
4. 更新 ReAct 系统提示词以包含新工具的使用说明

### 支持新的 FEA 模型
1. 在 `src/utils/` 中创建新的 Abaqus Python 脚本
2. 修改 `create_inp_file.py` 以支持新的几何参数
3. 更新工具函数的参数和文档字符串

### 集成其他 FEA 软件
- 项目架构支持替换 Abaqus 为其他求解器（如 ANSYS、LS-DYNA）
- 需要修改 `tools.py` 中的命令调用和文件解析逻辑
- 保持工具接口不变，智能体无需修改

---

## 注意事项

### Abaqus 环境配置
- 确保 `abaqus` 命令在系统 PATH 中可用
- Windows 用户可能需要配置 Visual Studio 和 Intel Fortran 编译器（如果使用子程序）
- 本项目不使用用户子程序，仅需要 Abaqus/CAE 和 Abaqus/Standard

### 文件管理
- 每次运行会覆盖 `src/abaqus_files/` 中的文件
- 如需保留历史结果，建议在智能体完成后手动备份
- ODB 文件较大，建议定期清理

### 性能优化
- 参数化研究可能需要多次仿真，耗时较长
- 可通过调整智能体的推理策略减少仿真次数（如二分搜索）
- Phoenix 追踪会增加少量开销，生产环境可选择性禁用

### API 成本
- 每次查询会调用多次 OpenAI API（智能体推理 + 评估）
- 建议使用 gpt-4o-mini 或 gpt-4.1-nano 作为评估模型以降低成本
- 可通过 Phoenix 查看详细的 token 使用情况

---

## 相关资源

- **LlamaIndex 文档**：https://docs.llamaindex.ai/
- **Phoenix 文档**：https://docs.arize.com/phoenix
- **Abaqus Scripting Reference**：Abaqus 安装目录下的文档
- **ReAct 论文**：Yao et al., "ReAct: Synergizing Reasoning and Acting in Language Models"

---

## 开发注意事项

- 代码注释和文档字符串使用英文，便于国际协作
- 用户界面文本可使用中文以提高可读性
- 提交代码前确保通过所有评估测试
- 修改提示词后需要重新测试智能体行为
