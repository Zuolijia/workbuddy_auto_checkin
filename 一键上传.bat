@echo off
chcp 65001 >nul
cd /d "%~dp0"

echo ================================================
echo   推送代码到 Zuolijia/workbuddy_auto_checkin
echo ================================================
echo.

REM 优先用系统 Python；找不到再试 py 启动器
set PY=
where python >nul 2>nul && set PY=python
if "%PY%"=="" (
  where py >nul 2>nul && set PY=py
)

if "%PY%"=="" (
  echo [x] 未检测到 Python。
  echo.
  echo     请安装 Python 3： https://www.python.org/downloads/
  echo     安装时务必勾选 "Add Python to PATH"
  echo.
  pause
  exit /b 1
)

echo 使用解释器：
%PY% --version
echo.

%PY% upload_via_api.py
code=%?

echo.
if "%code%"=="0" (
  echo [√] 全部完成，代码已推送到 GitHub。
) else (
  echo [x] 上传未完成，退出码 %code%。请把上方红色文字截图发我。
)

echo.
pause
exit /b %code%
