@echo off
echo 创建全局命令 mcp-lessons...
echo.

REM 获取当前完整路径
set SCRIPT_PATH=%~dp0use-lessons.js

REM 创建批处理文件内容
set BATCH_FILE=%USERPROFILE%\mcp-lessons.bat

echo @echo off > "%BATCH_FILE%"
echo node "%SCRIPT_PATH%" %%* >> "%BATCH_FILE%"

echo.
echo ========================================
echo 全局命令创建成功！
echo.
echo 已创建文件: %BATCH_FILE%
echo.
echo 现在你需要将以下目录添加到系统PATH：
echo %USERPROFILE%
echo.
echo 或者将 %BATCH_FILE% 复制到已在PATH中的目录
echo 例如: C:\Windows\System32
echo.
echo 完成后，你可以在任何位置使用：
echo   mcp-lessons help
echo   mcp-lessons record "问题" "解决方案"
echo   mcp-lessons search "关键词"
echo   mcp-lessons recent
echo ========================================
echo.

REM 询问是否立即复制到System32（需要管理员权限）
choice /C YN /M "是否尝试复制到 C:\Windows\System32（需要管理员权限）"
if errorlevel 2 goto :end
if errorlevel 1 goto :copyToSystem32

:copyToSystem32
copy "%BATCH_FILE%" "C:\Windows\System32\" >nul 2>&1
if %errorlevel% == 0 (
    echo.
    echo ✓ 成功复制到 System32！现在可以在任何地方使用 mcp-lessons 命令了。
    del "%BATCH_FILE%"
) else (
    echo.
    echo ✗ 复制失败（需要管理员权限）。请手动复制或添加 %USERPROFILE% 到PATH。
)

:end
echo.
pause