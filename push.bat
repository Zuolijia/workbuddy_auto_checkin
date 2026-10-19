@echo off
REM =====================================================================
REM  push.bat —— 把代码推送到 Zuolijia/workbuddy_auto_checkin
REM
REM  使用前：
REM    1. 在 https://github.com/settings/tokens?type=beta 申请 PAT
REM       - Resource owner: Zuolijia
REM       - Repository access: Public repositories (only)
REM       - Permissions: Repository - Contents = Read and write
REM       - 生成、复制
REM    2. 双击本文件
REM    3. 粘 PAT（屏幕会显示这一行，看完即丢），回车
REM =====================================================================

chcp 65001 >nul
cd /d "%~dp0"

echo.
echo ============================================================
echo   WorkBuddy Auto Checkin · 一键推送
echo ============================================================
echo.
echo 即将推送当前目录的所有代码到:
echo   https://github.com/Zuolijia/workbuddy_auto_checkin
echo.
echo ── 需要你准备 ──
echo   1. 申请 PAT: https://github.com/settings/tokens?type=beta
echo      - Resource owner: Zuolijia
echo      - Repository access: Public repositories (only)
echo      - Permissions: Repository - Contents = Read and write
echo      - 生成、复制（关掉就再也看不到了）
echo   2. 把 PAT 粘到下面
echo.
echo 提示: PAT 会显示在屏幕上这一行，脚本跑完就丢，不用担心
echo.
set /p PAT=粘 PAT 后按回车:

if "%PAT%"=="" (
    echo.
    echo [X] 没有输入 PAT，退出
    pause
    exit /b 1
)

echo.
echo [推送中...]
git push -u https://%PAT%@github.com/Zuolijia/workbuddy_auto_checkin.git main

if errorlevel 1 (
    echo.
    echo [X] 推送失败，常见原因：
    echo     - PAT 没勾 Contents R/W 权限
    echo     - 仓库不是 public（需要 Public repositories (only) 权限）
    echo     - 网络问题
    echo.
) else (
    echo.
    echo ============================================================
    echo   推送成功！
    echo ============================================================
    echo.
    echo 打开 https://github.com/Zuolijia/workbuddy_auto_checkin 应该看到所有代码。
    echo.
    echo ── 接下来 3 件事 ──
    echo   1) 在仓库 Settings - Secrets and variables - Actions 里填 3 个 Secret:
    echo      - WB_ACCESS_TOKEN    (先填占位字符如 x)
    echo      - WECHAT_PUSH_TYPE   (serverchan 或 pushplus)
    echo      - WECHAT_PUSH_KEY    (SendKey / token)
    echo   2) 在本机跑: refresh_token.exe --gh-repo Zuolijia/workbuddy_auto_checkin
    echo      (这步会覆盖第 1 条的占位)
    echo   3) 进入 Actions 页签 + 手动 Run workflow 一次
    echo.
)

set PAT=
pause