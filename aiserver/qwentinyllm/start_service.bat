@echo off
echo ========================================
echo   Qwen3 Tiny LLM 服务启动脚本
echo ========================================
echo.

REM 检查虚拟环境
if not exist "venv\Scripts\activate.bat" (
    echo [错误] 未找到虚拟环境
    echo 请先运行: python -m venv venv
    echo 然后运行: venv\Scripts\activate
    echo 最后安装依赖: pip install -r requirements.txt
    pause
    exit /b 1
)

REM 激活虚拟环境
echo [1/2] 激活虚拟环境...
call venv\Scripts\activate.bat

REM 启动服务
echo [2/2] 启动服务...
echo.
python service.py

pause
