@echo off
REM =====================================================================
REM  WorkBuddy Auto Checkin —— 一键部署脚本（走 PAT 路线，无需 gh CLI）
REM
REM  这个脚本会做：
REM    [1] 检查仓库是否存在；不存在则创建
REM    [2] 把当前目录的代码 push 到 main 分支
REM    [3] 打印剩余 3 步的详细指引
REM
REM  PAT 申请指引：
REM    1. 打开 https://github.com/settings/tokens?type=beta
REM    2. 点 "Generate new token"（Fine-grained）
REM    3. Resource owner: 选你自己
REM    4. Repository access: 选 "All repositories"（省心）
REM    5. Permissions:
REM         Repository - Contents    = Read and write
REM         Repository - Metadata    = Read-only（默认就有）
REM         Repository - Actions     = Read and write（不然 workflow 记录读不到）
REM    6. 点 "Generate token"，复制（只会显示一次）
REM =====================================================================

chcp 65001 >nul
setlocal

cd /d "%~dp0"

echo.
echo ============================================================
echo   WorkBuddy Auto Checkin · 一键部署（PAT 路线）
echo ============================================================
echo.

REM ---------- 收集参数 ----------
set /p GITHUB_USER=你的 GitHub 用户名：
if "%GITHUB_USER%"=="" goto :input_err

set /p REPO_NAME=仓库名（直接回车使用默认 workbuddy_auto_checkin）：
if "%REPO_NAME%"=="" set REPO_NAME=workbuddy_auto_checkin

echo.
echo ── GitHub PAT 申请提示 ──
echo  1. 打开 https://github.com/settings/tokens?type=beta
echo  2. 点 "Generate new token"（Fine-grained）
echo  3. Resource owner: 选你自己
echo  4. Repository access: 选 "All repositories"
echo  5. Permissions:
echo       Repository - Contents = Read and write
echo       Repository - Metadata = Read-only（默认）
echo       Repository - Actions  = Read and write
echo  6. 生成、复制（只会显示一次！）
echo.
echo 粘贴到下方（建议右键粘贴；脚本不回显）：

REM 用 PowerShell Read-Host 隐藏输入
for /f "delims=" %%T in ('powershell -NoProfile -Command "$secure = Read-Host -AsSecureString; $BSTR = [System.Runtime.InteropServices.Marshal]::SecureStringToBSTR($secure); [System.Runtime.InteropServices.Marshal]::PtrToStringAuto($BSTR)"') do set "GITHUB_TOKEN=%%T"

if "%GITHUB_TOKEN%"=="" goto :input_err

REM ---------- 1. 检查/创建仓库 ----------
echo.
echo [1/2] 检查仓库 %GITHUB_USER%/%REPO_NAME% ...

set REPO_EXISTED=0
curl -s -o "%TEMP%\wb_check.json" -w "" ^
     -H "Authorization: Bearer %GITHUB_TOKEN%" ^
     -H "Accept: application/vnd.github+json" ^
     -H "X-GitHub-Api-Version: 2022-11-28" ^
     "https://api.github.com/repos/%GITHUB_USER%/%REPO_NAME%"

findstr /C:"\"full_name\": \"%GITHUB_USER%/%REPO_NAME%\"" "%TEMP%\wb_check.json" >nul
if not errorlevel 1 (
    echo  [√] 仓库已存在，跳过创建
    set REPO_EXISTED=1
) else (
    echo  仓库不存在，正在创建 ...
    curl -s -o "%TEMP%\wb_create.json" -w "HTTP %%{http_code}\n" ^
         -X POST ^
         -H "Authorization: Bearer %GITHUB_TOKEN%" ^
         -H "Accept: application/vnd.github+json" ^
         -H "Content-Type: application/json" ^
         -H "X-GitHub-Api-Version: 2022-11-28" ^
         https://api.github.com/user/repos ^
         -d "{\"name\":\"%REPO_NAME%\",\"private\":true,\"auto_init\":false}"
    findstr /C:"\"full_name\"" "%TEMP%\wb_create.json" >nul
    if errorlevel 1 (
        echo.
        echo [X] 仓库创建失败，响应：
        type "%TEMP%\wb_create.json"
        echo.
        echo 常见原因：PAT 权限不够、仓库名已被占用、网络问题。
        goto :end
    )
    echo  [√] 仓库创建成功
)

REM ---------- 2. 推送代码 ----------
echo.
echo [2/2] 推送代码到 https://github.com/%GITHUB_USER%/%REPO_NAME%.git ...

REM 删除可能存在但指向错误的 origin
git remote remove origin >nul 2>&1
git remote add origin https://github.com/%GITHUB_USER%/%REPO_NAME%.git

git push -u https://%GITHUB_TOKEN%@github.com/%GITHUB_USER%/%REPO_NAME%.git main
if errorlevel 1 (
    echo.
    echo [X] push 失败
    goto :end
)
echo  [√] 推送成功

REM ---------- 后续指引 ----------
echo.
echo ============================================================
echo   推送完成！下面是剩下的事
echo ============================================================
echo.
echo ── 第 A 步：拿一个微信推送渠道 ────────────────────────────
echo.
echo  二选一：
echo.
echo    Server酱：微信扫码打开 https://sct.ftqq.com/login
echo              登录后顶部 'SendKey' 形如 SCT2xxxxx，复制整串
echo              免费每天 5 条，签到够用
echo.
echo    PushPlus： 微信扫码关注公众号「pushplus 推送加」
echo              公众号菜单 → 个人中心 → 复制 token
echo              免费每天 200 条
echo.
echo ── 第 B 步：在 GitHub 仓库填 3 个 Secret ───────────────────
echo.
echo  打开 https://github.com/%GITHUB_USER%/%REPO_NAME%/settings/secrets/actions/new
echo  点 'New repository secret'，逐条添加：
echo.
echo    Name: WB_ACCESS_TOKEN     Value: 先随便填一个占位字符（如 x）
echo    Name: WECHAT_PUSH_TYPE    Value: serverchan  或  pushplus
echo    Name: WECHAT_PUSH_KEY     Value: 第 A 步拿到的 SendKey / token
echo.
echo  WB_ACCESS_TOKEN 用占位即可，等第 C 步会覆盖为真实 token。
echo.
echo ── 第 C 步：在本机导出 token（覆盖第 B 步的占位）──────────
echo.
echo  打开 PowerShell 或 cmd，cd 到这个项目目录，运行：
echo.
echo      refresh_token.exe --gh-repo %GITHUB_USER%/%REPO_NAME%
echo.
echo  或装了 Python：
echo.
echo      python refresh_token.py --gh-repo %GITHUB_USER%/%REPO_NAME%
echo.
echo  屏幕显示 '已写入 GitHub Secret WB_ACCESS_TOKEN' 即完成。
echo.
echo ── 第 D 步：启用 Actions 并跑一次验证 ─────────────────────
echo.
echo  1. 进入 https://github.com/%GITHUB_USER%/%REPO_NAME%/actions
echo  2. 第一次进去会提示启用 workflows，点启用
echo  3. 左侧选 'Buddy 加油站每日自动化'
echo  4. 右侧点 'Run workflow' - 'Run workflow'
echo  5. 几秒后看日志 + 微信收到推送
echo.
echo ============================================================

:end
echo.
pause
endlocal