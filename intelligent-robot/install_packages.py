import subprocess
import sys
import os
import time
import logging
import threading

# 配置日志 (保持不变)
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger("installer")


# run_with_timeout 函数 (保持不变)
def run_with_timeout(cmd, timeout=600):  # 默认超时延长到10分钟，因为下载浏览器可能需要时间
    """运行命令，设置超时时间"""
    process = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        universal_newlines=True,
        bufsize=1,
        encoding='utf-8',
        errors='ignore'
    )

    stdout_data = []
    stderr_data = []
    start_time = time.time()

    def read_output(pipe, data_list):
        for line in iter(pipe.readline, ''):
            data_list.append(line)
            line = line.strip()
            if line:
                logger.info(line)

    stdout_thread = threading.Thread(target=read_output, args=(process.stdout, stdout_data))
    stderr_thread = threading.Thread(target=read_output, args=(process.stderr, stderr_data))
    stdout_thread.daemon = True
    stderr_thread.daemon = True
    stdout_thread.start()
    stderr_thread.start()

    while process.poll() is None:
        if timeout and time.time() - start_time > timeout:
            process.terminate()
            logger.error(f"命令执行超时（{timeout}秒）: {' '.join(cmd)}")
            return False, "超时"
        time.sleep(0.1)

    stdout_thread.join(1)
    stderr_thread.join(1)

    return process.returncode == 0, ''.join(stderr_data) if process.returncode != 0 else None


# --- 优化后的 install_packages 函数 ---
def install_packages():
    try:
        current_dir = os.path.dirname(os.path.abspath(__file__))
    except NameError:
        current_dir = os.getcwd()

    python_dir = os.path.join(current_dir, "python", "python-3.8.10-embed-amd64")
    python_exe = os.path.join(python_dir, "python.exe")

    logger.info(f"Python解释器路径: {python_exe}")

    pip_command = [python_exe, "-m", "pip"]

    requirements_path = os.path.join(current_dir, "requirements.txt")
    if not os.path.exists(requirements_path):
        logger.error(f"错误: 依赖文件 requirements.txt 未找到于 {requirements_path}")
        return

    lib_dir = os.path.join(python_dir, "lib")
    if not os.path.exists(lib_dir):
        logger.error(f"错误: 本地包文件夹 'lib' 未找到于 {lib_dir}")
        return

    # --- 新增代码开始 ---
    # 第一步：强制优先安装构建工具 versioneer
    logger.info("=" * 50)
    logger.info("步骤 1/3: 预安装构建必需的工具 (versioneer)...")
    versioneer_cmd = [*pip_command, "install", "--no-index", "versioneer", "--find-links", lib_dir]
    logger.info(f"执行预安装命令: {' '.join(versioneer_cmd)}")

    success, error = run_with_timeout(versioneer_cmd, timeout=120)
    if not success:
        logger.error(f"预安装 'versioneer' 失败: {error}")
        logger.error("安装过程已终止。")
        return
    logger.info("'versioneer' 已成功安装！")
    # --- 新增代码结束 ---

    logger.info("=" * 50)
    logger.info(f"步骤 2/3: 正在从本地安装所有依赖包，请稍候...")
    logger.info(f"依赖文件路径: {requirements_path}")
    logger.info(f"本地包搜索路径: {lib_dir}")

    cmd = [*pip_command, "install", "--no-index", "-r", requirements_path, "--find-links", lib_dir]
    logger.info(f"执行标准离线安装命令: {' '.join(cmd)}")

    success, error = run_with_timeout(cmd, timeout=300)

    if success:
        logger.info("所有Python依赖包安装完成！")

        logger.info("=" * 50)
        logger.info("步骤 3/3: 准备初始化浏览器内核 (rfbrowser init)...")

        rfbrowser_exe = os.path.join(python_dir, "Scripts", "rfbrowser.exe")

        if not os.path.exists(rfbrowser_exe):
            logger.error(f"错误: 未能找到 rfbrowser.exe 于 {rfbrowser_exe}")
            logger.error("无法自动初始化浏览器，请手动执行。")
            return

        init_cmd = [rfbrowser_exe, "init"]
        logger.info(f"执行浏览器初始化命令: {' '.join(init_cmd)}")
        logger.info("正在下载浏览器内核，此过程可能需要几分钟，请耐心等待...")

        init_success, init_error = run_with_timeout(init_cmd, timeout=600)

        if init_success:
            logger.info("浏览器内核初始化成功！")
            logger.info("=" * 50)
            logger.info("所有安装和配置步骤已成功完成！")
        else:
            logger.error(f"浏览器内核初始化失败: {init_error}")
            return

    else:
        logger.error(f"离线安装失败: {error}")
        return


if __name__ == "__main__":
    install_packages()