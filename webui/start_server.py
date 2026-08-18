"""
AI Novel Analyzer Web UI - 自动启动脚本

每次启动时自动：
1. 检测 Python 环境和依赖
2. 自动关闭占用的旧服务器（端口 18997）
3. 正式启动新服务器
"""
import sys
from pathlib import Path
import socket
import time
import subprocess
import platform

def check_python_version():
    """检查 Python 版本是否兼容"""
    version = sys.version_info[:2]
    if version < (3, 8):
        print(f"⚠️ 警告：检测到 Python {version[0]}.{version[1]}，建议使用 Python 3.8+ 以保证兼容性")
        return False
    else:
        print(f"✓ Python 版本检查通过：{sys.version_info.major}.{sys.version_info.minor}")
        return True

def check_dependencies():
    """检查核心依赖是否已安装"""
    try:
        import uvicorn
        print(f"✓ uvicorn {uvicorn.__version__} 已安装")
    except ImportError:
        print("✗ uvicorn 未安装，正在自动安装...")
        subprocess.check_call([sys.executable, "-m", "pip", "install", "uvicorn", "fastapi"])
        print("✓ uvicorn 安装完成")
    
    try:
        import jinja2
        print(f"✓ jinja2 {jinja2.__version__} 已安装")
    except ImportError:
        print("✗ jinja2 未安装，正在自动安装...")
        subprocess.check_call([sys.executable, "-m", "pip", "install", "jinja2"])
        print("✓ jinja2 安装完成")
    
    try:
        from fastapi import FastAPI
        print("✓ FastAPI 已安装")
    except ImportError:
        print("✗ FastAPI 未安装，正在自动安装...")
        subprocess.check_call([sys.executable, "-m", "pip", "install", "fastapi"])
        print("✓ FastAPI 安装完成")
    
    try:
        import starlette
        print(f"✓ starlette {starlette.__version__} 已安装")
    except ImportError:
        print("✗ starlette 未安装，正在自动安装...")
        subprocess.check_call([sys.executable, "-m", "pip", "install", "starlette"])
        print("✓ starlette 安装完成")
    
    print("\n✅ 依赖环境检查完成\n")
    return True

def is_port_in_use(port):
    """检测端口是否被占用（真实连接测试，不受 SO_REUSEADDR 干扰）"""
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(1)
    try:
        result = sock.connect_ex(('127.0.0.1', port))
        return result == 0
    finally:
        sock.close()


def graceful_shutdown(port, timeout=5):
    """向旧服务器发送关闭请求，等待其退出

    Returns:
        True = 旧服务器已关闭或不存在；False = 关闭失败
    """
    if not is_port_in_use(port):
        print(f"✓ 端口 {port} 当前无服务器运行")
        return True

    print(f"🔍 检测到端口 {port} 有旧服务器运行，正在请求优雅关闭...")
    try:
        import urllib.request
        req = urllib.request.Request(
            f"http://127.0.0.1:{port}/api/shutdown",
            method="POST",
            headers={"Content-Type": "application/json"},
            data=b"{}",
        )
        with urllib.request.urlopen(req, timeout=3) as resp:
            if resp.status == 200:
                print("✓ 已发送关闭请求，等待旧服务器退出...")
    except Exception as e:
        print(f"⚠️ 优雅关闭请求失败：{e}")
        return False

    # 轮询等待端口释放
    deadline = time.time() + timeout
    while time.time() < deadline:
        if not is_port_in_use(port):
            print("✓ 旧服务器已关闭")
            return True
        time.sleep(0.5)

    print("⚠️ 等待超时，旧服务器仍在运行")
    return False


def kill_process_on_port(port):
    """兑底方案：强制杀死占用端口的进程"""
    if not is_port_in_use(port):
        return True
    try:
        import os
        if os.name == 'nt':
            # Windows: 先查 PID 再杀进程，避免 Stop-NetTCPConnection 对 TIME_WAIT 误报
            result = subprocess.run(
                ['powershell', '-Command',
                 f"(Get-NetTCPConnection -LocalPort {port} -State Listen -ErrorAction SilentlyContinue).OwningProcess | Select-Object -First 1"],
                capture_output=True, text=True, encoding="utf-8"
            )
            pid = result.stdout.strip()
            if pid and pid.isdigit():
                subprocess.run(['taskkill', '/PID', pid, '/F'],
                               capture_output=True, text=True)
                print(f"✓ 已强制终止占用端口 {port} 的进程 (PID {pid})")
                return True
            else:
                # 端口处于 TIME_WAIT 等非监听状态，无需处理
                print(f"✓ 端口 {port} 无监听进程（可能处于 TIME_WAIT，不影响启动）")
                return True
        else:
            # Linux/macOS: fuser
            subprocess.run(['fuser', '-k', f'{port}/tcp'], capture_output=True)
            print(f"✓ 已终止占用端口 {port} 的进程")
            return True
    except Exception as e:
        print(f"❌ 强制杀进程失败：{e}")
        return False


def cleanup_old_server(port):
    """清理旧服务器：优雅关闭 → 强制杀进程 → 验证端口"""
    # 第 1 步：优雅关闭（仅对旧版 Web UI 服务器有效）
    if graceful_shutdown(port):
        return True
    # 第 2 步：兑底强杀
    print("🔧 优雅关闭失败，尝试强制终止进程...")
    kill_process_on_port(port)
    time.sleep(1)
    # 第 3 步：验证
    if not is_port_in_use(port):
        return True
    print(f"❌ 端口 {port} 仍被占用，请手动关闭旧服务后重试")
    return False

def ensure_port_available(port):
    """确保端口可用（真实 bind 测试，不设置 SO_REUSEADDR 以反映真实占用）"""
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        sock.bind(('127.0.0.1', port))
        print(f"✅ 端口 {port} 可用，准备启动服务器")
        return True
    except socket.error as e:
        print(f"❌ 端口 {port} 无法绑定：{e}")
        print("请先清理旧服务器后再启动")
        return False
    finally:
        sock.close()


if __name__ == "__main__":
    print("=" * 60)
    print("🚀 AI Novel Analyzer Web UI 启动脚本")
    print("每次启动前会自动：1️⃣检查环境 2️⃣关闭旧服务 3️⃣正式启动")
    print("=" * 60)
    
    # 步骤 1：检查环境
    print("\n📋 检查 Python 版本...")
    check_python_version()
    
    print("\n📦 检查依赖项...")
    check_dependencies()
    
    # 步骤 2：清理旧服务器
    print("\n🔍 扫描旧服务器进程...")
    if not cleanup_old_server(18997):
        print("\n❌ 端口清理失败，启动中止")
        sys.exit(1)

    print("\n✅ 验证端口可用性...")
    if not ensure_port_available(18997):
        sys.exit(1)
    
    # 步骤 3:正式启动
    print("\n🎯 启动服务器...")
    print("=" * 60)
    
    import uvicorn
    import os
    from pathlib import Path
    
    # 设置 PYTHONPATH 以便导入 webui.main
    project_root = Path(__file__).parent.parent
    sys.path.insert(0, str(project_root))
    
    # 切换目录到项目根目录
    old_cwd = os.getcwd()
    os.chdir(str(project_root))
    
    try:
        from main import app
        uvicorn.run(app, host="127.0.0.1", port=18997, reload=False)
    finally:
        os.chdir(old_cwd)
