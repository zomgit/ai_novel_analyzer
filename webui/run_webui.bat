@echo off
chcp 65001 >nul
echo ========================================
echo   AI Novel Analyzer Web UI Launcher
echo   FastAPI + Alpine.js 轻量级拆书台
echo ========================================
echo.

REM 检查 Python 环境
python --version >nul 2>&1
if errorlevel 1 (
    echo [错误] 未找到 Python 环境，请先安装并配置虚拟环境
    pause
    exit /b 1
)

REM 检查依赖包 (使用 python -c 方式)
python -c "import fastapi" >nul 2>&1
if errorlevel 1 (
    echo [提示] 首次使用需要安装 Web UI 依赖...
    echo 请运行：uv sync --group webui
    echo.
    pause
    exit /b 1
)

echo [就绪] Web UI 即将启动...
echo [地址] http://127.0.0.1:18997
echo.
echo ========================================
echo 按 Ctrl+C 可停止服务
echo ========================================
echo.

REM 启动服务 (调用 Python 启动脚本，使用 uv 确保依赖完整)
cd /d %~dp0
uv run python start_server.py

pause
