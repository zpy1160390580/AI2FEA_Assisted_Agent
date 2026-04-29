# AI2FEA 辅助智能体
本项目最初起源于：https://github.com/Farhad-Davaripour/FEA_Assisted_Agent

基于 AI 的 Abaqus 有限元分析自动化系统，通过 LlamaIndex 和硅基流动平台的 DeepSeek 模型实现仿真工作流的全流程自动化。

![License](https://img.shields.io/badge/license-MIT-blue.svg)
![Python](https://img.shields.io/badge/python-3.8+-green.svg)
![DeepSeek](https://img.shields.io/badge/model-DeepSeek--V3-orange.svg)

---

## ✨ 核心特性

- 🤖 **智能体驱动**：使用 ReAct (Reasoning + Acting) 架构自动规划和执行 Abaqus 仿真任务
- 📊 **参数化研究**：自动执行多次仿真以找到满足应力阈值的最优参数
- 🔍 **实时评估**：通过 Phoenix 追踪工具调用、单位正确性和幻觉检测
- 💻 **交互式界面**：Streamlit Web 应用提供用户友好的查询和结果展示
- 💰 **成本优化**：使用国产 DeepSeek-V3 模型，成本降低 90% 以上

---

## 🚀 快速开始

### 1. 环境要求

- **Python 3.8+**
- **Abaqus**（需要本地安装并配置环境变量）
- **硅基流动平台 API Key**

### 2. 安装依赖

```bash
# 克隆仓库
git clone <repository_url>
cd AI2FEA_Assisted_Agent

# 安装 Python 依赖
pip install -r requirements.txt
```

### 3. 配置 API Key

#### 获取硅基流动 API Key
1. 访问 [硅基流动平台](https://cloud.siliconflow.cn/)
2. 注册并登录（支持手机号注册）
3. 进入 [API Key 管理](https://cloud.siliconflow.cn/account/ak)
4. 点击"创建新令牌"，复制生成的 API Key

#### 配置环境变量
```bash
# 进入配置文件夹
cd config_files

# 复制模板文件
cp .env.example .env

# 编辑 .env 文件，填入您的 API Key
# SILICONFLOW_API_KEY=your_api_key_here
```

**为什么使用 `.env.example`？**
- `.env.example` 是模板文件，可以提交到 Git，供团队成员参考
- `.env` 包含真实的 API Key（敏感信息），不应提交到 Git
- 这是业界标准做法，保护敏感信息的同时提供配置模板

### 4. 运行应用

```bash
streamlit run main.py
```

应用将在浏览器中自动打开（默认地址：http://localhost:8501）

---

## 📖 使用示例

### 典型查询

在 Web 界面中输入：
```
对于悬臂梁，当管道向下位移 0.02 m 时，获取最大 von Mises 应力。
然后逐步增加位移，直到 von Mises 应力达到约 360 MPa，同时最小化仿真次数。
```

### 智能体执行流程

1. **生成输入文件**：创建位移为 0.02m 的 Abaqus 输入文件
2. **运行仿真**：执行 Abaqus 作业
3. **提取应力**：从 ODB 文件读取 Von-Mises 应力（假设为 150 MPa）
4. **智能推理**：判断需要更大位移，尝试 0.05m
5. **迭代优化**：重复步骤 1-3，直到应力接近 360 MPa
6. **返回结果**：报告最优位移和对应的应力值

---

## 🛠️ 功能详解

### 三个核心工具

| 工具 | 功能 | 参数 | 输出 |
|------|------|------|------|
| **Abaqus_input_file_generator** | 生成参数化输入文件 | `applied_displacement` (m) | `.inp` 文件 |
| **Abaqus_job_executor** | 执行仿真作业 | 无 | 输出文件（.odb, .dat 等） |
| **Von_Mises_stress_extractor** | 提取最大应力 | 无 | 应力值（MPa） |

### 评估系统

- ✅ **工具调用正确性**：评估智能体是否选择了正确的工具
- ✅ **单位正确性**：验证参数的物理单位是否正确
- ✅ **幻觉检测**：检查最终答案是否基于实际工具输出
- ✅ **应力阈值监控**：实时追踪应力是否超过配置阈值

---

## ⚙️ 配置说明

### 配置文件说明

项目采用**分离式配置**，将配置文件集中在 `config_files/` 文件夹中：

#### 配置文件夹结构
```
config_files/
├── README.md        # 配置文件夹说明文档
├── config.py        # 主配置文件（所有参数，详细注释）
├── .env.example     # 环境变量模板（可提交到 Git）
└── .env             # 实际环境变量（不提交，用户创建）
```

#### 配置文件职责

1. **`config.py`**：所有非敏感配置参数
   - 模型选择、温度参数、应力阈值等
   - 包含详细的中文注释
   - 可以提交到 Git，方便团队协作

2. **`.env.example`**：环境变量模板
   - 仅包含 API Key 配置示例
   - 可以提交到 Git
   - 供新用户参考配置格式

3. **`.env`**：实际环境变量（用户创建）
   - 包含真实的 API Key
   - 不应提交到 Git（已在 `.gitignore` 中）
   - 从 `.env.example` 复制并填入真实值

#### 为什么这样设计？

✅ **安全性**：敏感信息（API Key）不会意外提交到 Git  
✅ **清晰性**：配置文件集中管理，结构清晰  
✅ **协作性**：团队成员可以共享配置模板  
✅ **灵活性**：每个人可以有自己的 API Key

### 主要配置项

所有配置参数都在 `config_files/config.py` 文件中，包含详细注释。主要配置项：

### API 配置
```python
SILICONFLOW_API_KEY = "your_api_key_here"  # 硅基流动 API Key
SILICONFLOW_BASE_URL = "https://api.siliconflow.cn/v1"  # API 基础 URL
```

### 模型配置
```python
MODEL_NAME = "deepseek-ai/DeepSeek-V3"  # 主模型
EVAL_MODEL_NAME = "deepseek-ai/DeepSeek-V3"  # 评估模型
TEMPERATURE = 0.7  # 温度参数（0-1，越高越随机）
MAX_TOKENS = 4096  # 最大输出 tokens
```

### 仿真配置
```python
STRESS_THRESHOLD = 360.0  # 应力阈值（MPa）
MAX_ITERATIONS = 100  # 智能体最大迭代次数
```

详细配置说明请查看 [config_files/config.py](config_files/config.py) 文件。

---

## 📁 项目结构

```
AI2FEA_Assisted_Agent/
├── README.md                       # 完整的项目文档（中文）
├── CLAUDE.md                       # Claude Code 指导文档
├── main.py                         # Streamlit 主应用（带详细注释）
├── requirements.txt                # Python 依赖
├── .gitignore                      # Git 忽略文件
├── config_files/                   # 配置文件夹
│   ├── README.md                   # 配置文件夹说明
│   ├── config.py                   # 主配置文件（所有参数）
│   ├── .env.example                # 环境变量模板（可提交）
│   └── .env                        # 实际环境变量（不提交，用户创建）
├── FEA_tools/                      # FEA 工具模块
│   ├── tools.py                    # 核心工具函数（中文注释）
│   ├── prompt_temp.py              # ReAct 提示词模板
│   └── eval_utils.py               # 评估工具
├── FEA_scripts/                    # Abaqus Python 脚本
│   ├── create_inp_file.py          # 生成输入文件
│   └── retrieve_vm_stress.py       # 提取应力
├── FEA_Results/                    # 仿真文件存储（所有生成文件）
└── artifacts/                      # 图像资源
```

---

## 💡 支持的模型

项目通过硅基流动平台支持以下模型：

| 模型 | 适用场景 | 优势 | 成本（输入/输出） |
|------|---------|------|------------------|
| **deepseek-ai/DeepSeek-V3** | 通用任务、参数化研究 | 性能强、成本低、速度快 | ¥0.002 / ¥0.008 per 1K tokens |
| **deepseek-ai/DeepSeek-R1** | 复杂推理、数学计算 | 推理能力更强 | ¥0.0014 / ¥0.0028 per 1K tokens |
| **Qwen/Qwen2.5-72B-Instruct** | 备选方案 | 阿里通义千问，中文友好 | ¥0.0035 / ¥0.0035 per 1K tokens |

可在 Web 界面的侧边栏中切换模型。

---

## 💰 成本对比

### 单次查询成本（参数化研究，4 轮迭代）

| 平台 | 成本 | 相比 OpenAI |
|------|------|------------|
| OpenAI GPT-4o | $0.062 | - |
| DeepSeek-V3 | ¥0.03 ($0.004) | **节省 93.5%** |

### 月度成本（每天 10 次查询）

| 平台 | 月度成本 | 年度成本 |
|------|---------|---------|
| OpenAI GPT-4o | $18.60 | $223.20 |
| DeepSeek-V3 | ¥9.00 ($1.20) | ¥108 ($14.40) |

---

## 🔧 技术架构

### 核心技术栈
- **LlamaIndex**：智能体框架，提供 ReActAgent 和工具集成
- **硅基流动平台 + DeepSeek-V3**：国产大模型，支持 OpenAI 兼容接口
- **Streamlit**：Web 应用框架
- **Phoenix (Arize)**：可观测性平台，用于追踪和评估
- **Abaqus**：有限元分析软件

### ReAct 智能体架构
```
用户查询 → Thought（思考） → Action（选择工具） → Observation（观察结果） → 循环直到完成
```

---

## 🌟 为什么选择硅基流动平台？

| 特性 | OpenAI API | 硅基流动平台 |
|------|-----------|------------|
| **成本** | 高（GPT-4: $0.03/1K tokens） | 低（DeepSeek-V3: ¥0.002/1K tokens，降低 90%） |
| **访问速度** | 国内需科学上网，延迟高 | 国内直连，延迟低 |
| **模型性能** | GPT-4 系列 | DeepSeek-V3（671B 参数，接近 GPT-4） |
| **API 兼容性** | OpenAI 标准 | 完全兼容 OpenAI API 格式 |
| **支付方式** | 需国际信用卡 | 支持支付宝、微信支付 |

### DeepSeek-V3 性能亮点
- **参数规模**：671B 参数（MoE 架构，实际激活 37B）
- **基准测试**：在 MMLU、HumanEval、MATH 等测试中接近或超越 GPT-4
- **推理能力**：DeepSeek-R1 版本在数学和逻辑推理任务中表现优异
- **成本效益**：性能接近 GPT-4，但成本仅为其 1/10

---

## 🐛 常见问题

### Q1: 如何切换到其他模型？
**A**: 在 Web 界面的侧边栏中选择模型，或修改 `config.py` 中的 `MODEL_NAME`。

### Q2: Abaqus 命令找不到怎么办？
**A**: 确保 Abaqus 已安装并添加到系统 PATH 环境变量中。Windows 用户可在命令行中运行 `abaqus` 测试。

### Q3: API 调用失败怎么办？
**A**: 
1. 检查 `.env` 文件中的 `SILICONFLOW_API_KEY` 是否正确
2. 确认账户余额充足
3. 查看硅基流动平台控制台的错误日志

### Q4: 如何查看详细的执行日志？
**A**: 
1. 在 Web 界面点击"Show Progress"查看实时推理步骤
2. 访问 Phoenix 可观测性平台（如已配置）查看完整追踪

### Q5: 如何回退到 OpenAI？
**A**: 修改 `config.py` 中的配置：
```python
SILICONFLOW_API_KEY = os.getenv("OPENAI_API_KEY")
SILICONFLOW_BASE_URL = "https://api.openai.com/v1"
MODEL_NAME = "gpt-4o"
```

### Q6: 为什么配置文件在单独的文件夹中？
**A**: 
- **结构清晰**：所有配置文件集中在 `config_files/` 文件夹，易于管理
- **职责分离**：`.env` 管敏感信息，`config.py` 管其他参数
- **团队协作**：配置模板可以共享，实际 API Key 各自保管
- **安全性**：`.gitignore` 确保 `.env` 不会被提交

---

## 📚 相关资源

- **硅基流动平台**：https://cloud.siliconflow.cn/
- **DeepSeek 模型文档**：https://api-docs.deepseek.com/
- **LlamaIndex 文档**：https://docs.llamaindex.ai/
- **Phoenix 文档**：https://docs.arize.com/phoenix
- **Abaqus Scripting Reference**：Abaqus 安装目录下的文档

---

## 🤝 贡献

欢迎提交 Issue 和 Pull Request！

### 开发指南
1. Fork 本仓库
2. 创建特性分支 (`git checkout -b feature/AmazingFeature`)
3. 提交更改 (`git commit -m 'Add some AmazingFeature'`)
4. 推送到分支 (`git push origin feature/AmazingFeature`)
5. 开启 Pull Request

---

## 📄 许可证

本项目采用 MIT 许可证 - 详见 [LICENSE](LICENSE) 文件。

---

## 🙏 致谢

- [LlamaIndex](https://www.llamaindex.ai/) - 强大的智能体框架
- [硅基流动](https://siliconflow.cn/) - 提供高性能、低成本的 AI 推理服务
- [DeepSeek](https://www.deepseek.com/) - 优秀的开源大模型
- [Arize Phoenix](https://phoenix.arize.com/) - 可观测性平台

---

## 📧 联系方式

如有问题或建议，请通过以下方式联系：
- 提交 GitHub Issue
- 发送邮件至项目维护者

---

**立即开始使用 AI2FEA 辅助智能体，让 AI 为您的有限元分析工作提速！** 🚀
