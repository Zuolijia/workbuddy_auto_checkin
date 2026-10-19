@echo off
REM =====================================================================
REM  WorkBuddy Auto Checkin —— 一键部署脚本
REM  作用：在你 GitHub 账号下创建私有仓库，并把当前目录代码推上去
REM  后续 4 步会逐项打印详细指引
REM =====================================================================

chcp 65001 >nul
setlocal

cd /d "%~dp0"

echo.
echo ============================================================
echo   WorkBuddy Auto Checkin · 一键部署
echo ============================================================
echo.
echo   这个脚本会完成：
echo     [1] 在你的 GitHub 账号下创建私有仓库
echo     [2] 把当前目录代码推送到 main 分支
echo.
echo   之后会打印剩下 3 步的详细指引（需要在 GitHub 网页和本机操作）。
echo.

REM ---------- 收集参数 ----------
set /p GITHUB_USER=你的 GitHub 用户名：
if "%GITHUB_USER%"=="" goto :input_err

set /p REPO_NAME=仓库名（直接回车使用默认 workbuddy_auto_checkin）：
if "%REPO_NAME%"=="" set REPO_NAME=workbuddy_auto_checkin

set /p REPO_DESC=仓库描述（直接回车跳过）：

echo.
echo ── 准备 GitHub PAT ──
echo 需要一个 Fine-grained PAT（不能用 Classic），权限如下：
echo   1. 打开 https://github.com/settings/tokens?type=beta
echo   2. 点 "Generate new token"
echo   3. Resource owner 选你自己
echo   4. Repository access 选 "All repositories" 或 "Only select repositories"
echo      （Only select 时记得勾上你要推的 %REPO_NAME%，可后补）
echo   5. Permissions - Repository:
echo        - Contents    = Read and write
echo        - Metadata    = Read-only（默认就有）
echo        - Actions     = Read and write（可选）
echo   6. 生成、复制（只会显示一次！）
echo.
set /p GITHUB_TOKEN=GitHub PAT：

if "%GITHUB_TOKEN%"=="" goto :input_err

REM ---------- 1. 创建仓库 ----------
echo.
echo [1/2] 在 GitHub 上创建仓库 %GITHUB_USER%/%REPO_NAME% ...

set DESC_PARAM=
if not "%REPO_DESC%"=="" set DESC_PARAM=, "description": "%REPO_DESC%"

curl -s -o "%TEMP%\wb_create.json" -w "HTTP %%{http_code}\n" ^
     -X POST ^
     -H "Authorization: Bearer %GITHUB_TOKEN%" ^
     -H "Accept: application/vnd.github+json" ^
     -H "Content-Type: application/json" ^
     -H "X-GitHub-Api-Version: 2022-11-28" ^
     https://api.github.com/user/repos ^
     -d "{\"name\":\"%REPO_NAME%\",\"private\":true%DESC_PARAM%,\"auto_init\":false}"

findstr /C:"\"full_name\"" "%TEMP%\wb_create.json" >nul
if errorlevel 1 (
    echo.
    echo [X] 仓库创建失败，响应：
    type "%TEMP%\wb_create.json"
    echo.
    echo 常见原因：PAT 权限不够、仓库名已被占用、网络问题。
    goto :end
)
echo [√] 仓库创建成功

REM ---------- 2. 推送代码 ----------
echo.
echo [2/2] 推送代码到 https://github.com/%GITHUB_USER%/%REPO_NAME%.git ...

REM 删除可能存在但指向错误的 origin
git remote remove origin >nul 2>&1
git remote add origin https://github.com/%GITHUB_USER%/%REPO_NAME%.git

git push -f https://%GITHUB_TOKEN%@github.com/%GITHUB_USER%/%REPO_NAME%.git main
if errorlevel 1 (
    echo.
    echo [X] push 失败，可能原因：
    echo     - PAT 权限不足
    echo     - 网络问题
    goto :end
)
echo [√] 推送成功

REM ---------- 后续指引 ----------
echo.
echo ============================================================
echo   推送完成！下面是剩下 3 步的指引
echo ============================================================
echo.
echo ── 第 3 步：在本机导出 WorkBuddy token ─────────────────
echo.
echo   打开 PowerShell 或 cmd，cd 到这个项目目录（脚本所在目录），运行：
echo.
echo       python refresh_token.py --gh-repo %GITHUB_USER%/%REPO_NAME%
echo.
echo   或没装 Python：
echo.
echo       refresh_token.exe --gh-repo %GITHUB_USER%/%REPO_NAME%
echo.
echo   屏幕看到 "已写入 GitHub Secret WB_ACCESS_TOKEN" 即可。
echo   token 会自动写入到第 4 步要配置的 Secret 里。
echo.
echo ── 第 4 步：在 GitHub 网页上配置 3 个 Secret ─────────────
echo.
echo   打开 https://github.com/%GITHUB_USER%/%REPO_NAME%/settings/secrets/actions/new
echo   （点 "New repository secret"，逐条添加）
echo.
echo   如果第 3 步已经自动写了 WB_ACCESS_TOKEN，只需要再填两条：
echo.
echo       Name: WECHAT_PUSH_TYPE    Value: serverchan  或  pushplus
echo       Name: WECHAT_PUSH_KEY     Value: SendKey / token
echo.
echo   如果第 3 步没能自动写入（比如没装 gh CLI），就填三条：
echo.
echo       Name: WB_ACCESS_TOKEN     Value: refresh_token 输出的 token
echo       Name: WECHAT_PUSH_TYPE    Value: serverchan  或  pushplus
echo       Name: WECHAT_PUSH_KEY     Value: SendKey / token
echo.
echo ── 第 5 步：启用 Actions 并跑一次 ────────────────────────
echo.
echo   1. 进入仓库，点击上方 "Actions" 页签
echo   2. 如果提示 "I understand my workflows..."，点启用
echo   3. 左侧选 "Buddy 加油站每日自动化"
echo   4. 右侧点 "Run workflow" - "Run workflow"
echo   5. 几秒后 Actions 日志会打印结果；微信应收到推送
echo.
echo   推送默认每天 3 次：北京时间 08:10、14:10、20:10（UTC 00:10/06:10/12:10）
echo ============================================================

:end
echo.
pause
endlocal