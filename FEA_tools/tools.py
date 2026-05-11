import os
import subprocess
import shutil
import re
import json

def generate_input_file(applied_displacement):
    """
    生成带有指定位移的 Abaqus 输入文件

    此函数运行 Abaqus 脚本（`create_inp_file.py`），使用提供的位移作为参数，
    生成输入文件，并将其移动到指定目录。

    参数:
        applied_displacement (float): 管道向下推动的位移，用于 Abaqus 模型（单位：米）

    处理流程:
        1. 构造执行 Abaqus 脚本的命令
        2. 使用 `subprocess.run` 运行命令
        3. 将生成的 `.inp` 文件移动到指定目标目录

    异常:
        subprocess.CalledProcessError: 如果 Abaqus 命令执行失败

    副作用:
        - 将生成的 `cantilever_beam.inp` 文件移动到 `FEA_Results/cantilever_beam.inp`
        - 向控制台打印成功或错误消息

    示例:
        generate_input_file(0.015)
    """
    # 确保工作目录存在
    os.makedirs('FEA_Results', exist_ok=True)

    print("Abaqus 正在运行中...")

    # 在 FEA_Results 目录中运行 Abaqus
    command = f"cd FEA_Results && abaqus cae noGUI=../FEA_scripts/create_inp_file.py -- {applied_displacement}"
    try:
        subprocess.run(command, shell=True, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)

        # 检查生成的文件是否存在
        output_file = 'FEA_Results/cantilever_beam.inp'
        if not os.path.exists(output_file):
            # 列出 FEA_Results 目录的文件，帮助调试
            fea_files = os.listdir('FEA_Results')
            inp_files = [f for f in fea_files if f.endswith('.inp')]
            return f"错误：未找到生成的输入文件。FEA_Results 目录的 .inp 文件: {inp_files}"

        return f"输入文件生成成功，位置：{output_file}"

    except subprocess.CalledProcessError as e:
        print("Abaqus 作业执行期间出错。")
        print("错误输出:", e.stderr)
        return f"Abaqus 命令执行失败：{e.stderr}"

def run_abaqus():
    """
    运行 Abaqus 作业并在 FEA_Results 目录中生成所有输出文件

    此函数使用位于 `FEA_Results` 目录中的输入文件 `cantilever_beam.inp`
    执行 Abaqus 作业。所有输出文件直接生成在 `FEA_Results` 目录中。

    处理流程:
        1. 确保 FEA_Results 目录存在
        2. 在 FEA_Results 目录中运行 Abaqus 作业
        3. 所有输出文件自动生成在 FEA_Results 目录

    异常:
        subprocess.CalledProcessError: 如果 Abaqus 作业执行失败

    副作用:
        - 所有以 `cantilever_beam` 开头的 Abaqus 生成的输出文件
          直接保存在 `FEA_Results` 目录
        - 向控制台打印成功或错误消息

    示例:
        run_abaqus()
    """
    # 确保目标目录存在
    os.makedirs("FEA_Results", exist_ok=True)

    print("Abaqus 求解器正在运行中...")

    # 在 FEA_Results 目录中运行 Abaqus
    command = f"cd FEA_Results && abaqus job=cantilever_beam input=cantilever_beam.inp"
    try:
        subprocess.run(command, shell=True, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        return f"Abaqus 作业成功完成，输出文件位置：FEA_Results/cantilever_beam.odb"
    except subprocess.CalledProcessError as e:
        print("Abaqus 作业执行期间出错。")
        print("错误输出:", e.stderr)
        return f"Abaqus 作业执行失败：{e.stderr}"

def extract_von_mises_stress_from_ODB():
    """
    从 Abaqus ODB 文件中提取 Von-Mises 应力数据

    此函数使用 Abaqus 运行 Python 脚本（`retrieve_vm_stress.py`）来提取
    Von-Mises 应力数据。脚本在 FEA_Results 目录中运行，数据保存在该目录的 `max_vm_stress.txt` 文件中。

    处理流程:
        1. 在 FEA_Results 目录中使用 Abaqus Python 命令执行 `retrieve_vm_stress.py` 脚本
        2. 从生成的 `max_vm_stress.txt` 文件读取应力值
        3. 将应力值从 Pa 转换为 MPa

    返回:
        str: 应力值（单位：MPa）

    异常:
        subprocess.CalledProcessError: 如果 Abaqus Python 脚本执行失败

    副作用:
        - 在 `FEA_Results` 目录生成 `max_vm_stress.txt` 文件
        - 向控制台打印成功或错误消息

    示例:
        stress_data = extract_von_mises_stress_from_ODB()
    """
    # 确保目标目录存在
    os.makedirs("FEA_Results", exist_ok=True)

    print("正在提取应力数据...")

    # 获取绝对路径
    script_path = os.path.abspath("FEA_scripts/retrieve_vm_stress.py")
    work_dir = os.path.abspath("FEA_Results")

    # 在 FEA_Results 目录中运行脚本
    command = f"abaqus python {script_path}"
    try:
        subprocess.run(command, shell=True, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, cwd=work_dir)

        # 验证文件是否生成
        stress_file = "FEA_Results/max_vm_stress.txt"
        if not os.path.exists(stress_file):
            return "错误：应力文件未生成"

        # 从文件读取应力数据（避免标准输出被编译器环境信息污染）
        with open(stress_file, 'r', encoding='utf-8') as f:
            content = f.read().strip()

        # 解析应力数据
        # 文件格式: "Maximum Mises stress in the cantilever beam is 123.456"
        if "Maximum Mises stress" in content and "is" in content:
            # 提取 "is" 后面的数字
            parts = content.split("is")
            if len(parts) > 1:
                stress_str = parts[-1].strip()
                data = round(float(stress_str) / 1e6, 2)
                return f"von_mises 应力为 {data} MPa，结果文件位置：{stress_file}"
            else:
                raise ValueError("无法从文件中解析应力数据")
        else:
            raise ValueError(f"文件格式不正确: {content}")

    except subprocess.CalledProcessError as e:
        print("Abaqus 作业执行期间出错。")
        print("错误输出:", e.stderr)
        return "应力提取失败"
    except (ValueError, IndexError) as e:
        print(f"数据解析错误: {e}")
        return "应力数据解析失败"
    except FileNotFoundError:
        return "错误：应力文件不存在"
    except Exception as e:
        print(f"未预期的错误: {e}")
        return "应力数据读取失败"


ACTION_RE = re.compile(r"Action:\s*([A-Za-z0-9_]+)")
INPUT_RE  = re.compile(r"Action Input:\s*(\{.*\})", re.S)

def extract_action(messages):
    """
    从包含 "Action:" 行的第一条助手消息中返回 (tool_name, json_args)

    参数:
        messages: 消息列表，每个消息包含角色和内容

    返回:
        tuple: (工具名称, JSON 参数字符串)，如果未找到则返回 (None, "{}")
    """
    for m in messages:                                 # 遍历 output_messages 中的每个元素
        msg = m.get("message", m)                      # 容忍两种形状
        if msg.get("role") != "assistant":
            continue

        content = msg.get("content", "")
        m_action = ACTION_RE.search(content)
        if not m_action:
            continue

        name = m_action.group(1)
        m_args = INPUT_RE.search(content)
        args  = m_args.group(1) if m_args else "{}"

        # 通过 json 往返，使评分器看到有效的 JSON
        try:
            args = json.dumps(json.loads(args))
        except json.JSONDecodeError:
            args = "{}"

        return name, args

    return None, "{}" 