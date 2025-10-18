import os
import subprocess
import sys


def start_robot_test(robot_file_path):
    """
    启动一个Robot Framework测试，并返回其进程ID。

    参数:
        robot_file_path (str): Robot Framework测试文件的绝对或相对路径。

    返回:
        int: 启动的测试进程的ID。
        None: 如果启动失败。
    """
    # 获取当前脚本所在的目录
    current_dir = os.path.dirname(os.path.abspath(__file__))

    # 构建robot命令的绝对路径
    robot_executable_path = os.path.join(
        current_dir,
        '..', '..', 'python', 'python-3.8.10-embed-amd64', 'Scripts', 'robot.exe'
    )

    # 检查robot.exe是否存在
    if not os.path.exists(robot_executable_path):
        print(f"错误: 未在指定路径找到robot.exe: {robot_executable_path}", file=sys.stderr)
        return None

    # 检查robot文件是否存在
    if not os.path.exists(robot_file_path):
        print(f"错误: 指定的Robot Framework文件不存在: {robot_file_path}", file=sys.stderr)
        return None

    # 构建完整的执行命令
    command = [robot_executable_path, robot_file_path]

    try:
        # 使用subprocess.Popen启动新进程
        # 这允许我们在不阻塞当前脚本的情况下运行测试
        process = subprocess.Popen(command)

        # 返回新进程的ID
        return process.pid
    except Exception as e:
        print(f"启动Robot Framework测试时发生错误: {e}", file=sys.stderr)
        return None
