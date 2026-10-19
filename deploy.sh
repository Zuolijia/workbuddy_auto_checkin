#!/usr/bin/env bash
# ============================================================
# WorkBuddy Auto Checkin —— 一键部署脚本（macOS / Linux）
# 用法：bash deploy.sh
# ============================================================
set -euo pipefail

cd "$(dirname "$0")"

echo
echo "============================================================"
echo "  WorkBuddy Auto Checkin · 一键部署"
echo "============================================================"
echo
echo "  接下来要做的 5 件事："
echo "    [脚本自动] 1. 在你的 GitHub 账号下创建私有仓库"
echo "    [脚本自动] 2. 把当前目录代码推送到 main 分支"
echo "    [你需要]   3. 在本机跑 refresh_token.py 导出 WorkBuddy token"
echo "    [你需要]   4. 在仓库 Settings - Secrets 里填 3 个 Secret"
echo "    [你需要]   5. 启用 Actions 并 Run workflow 一次验证"
echo

read -rp "你的 GitHub 用户名：" GITHUB_USER
[ -n "$GITHUB_USER" ] || { echo "用户名不能为空"; exit 1; }

read -rp "仓库名（回车使用默认 workbuddy_auto_checkin）：" REPO_NAME
REPO_NAME=${REPO_NAME:-workbuddy_auto_checkin}

read -rp "仓库描述（回车跳过）：" REPO_DESC

echo
echo "需要 GitHub PAT（Fine-grained, Contents=Read and write）："
echo "  https://github.com/settings/tokens?type=beta"
echo
read -rsp "GitHub PAT：" GITHUB_TOKEN
echo
[ -n "$GITHUB_TOKEN" ] || { echo "PAT 不能为空"; exit 1; }

# ---------- 1. 创建仓库 ----------
echo
echo "[1/2] 在 GitHub 上创建仓库 ${GITHUB_USER}/${REPO_NAME} ..."

DESC_JSON=""
[ -n "$REPO_DESC" ] && DESC_JSON=", \"description\": \"${REPO_DESC}\""

RESP=$(curl -s -w "\n%{http_code}" \
  -X POST \
  -H "Authorization: Bearer ${GITHUB_TOKEN}" \
  -H "Accept: application/vnd.github+json" \
  -H "Content-Type: application/json" \
  -H "X-GitHub-Api-Version: 2022-11-28" \
  https://api.github.com/user/repos \
  -d "{\"name\":\"${REPO_NAME}\",\"private\":true${DESC_JSON},\"auto_init\":false}")

HTTP_CODE=$(echo "$RESP" | tail -n1)
BODY=$(echo "$RESP" | sed '$d')

if [ "$HTTP_CODE" != "201" ] || ! echo "$BODY" | grep -q '"full_name"'; then
  echo
  echo "[X] 仓库创建失败 (HTTP $HTTP_CODE)："
  echo "$BODY"
  echo "常见原因：PAT 权限不够、仓库名已被占用、网络问题。"
  exit 1
fi
echo "[√] 仓库创建成功"

# ---------- 2. 推送代码 ----------
echo
echo "[2/2] 推送代码到 https://github.com/${GITHUB_USER}/${REPO_NAME}.git ..."

git remote remove origin 2>/dev/null || true
git remote add origin "https://github.com/${GITHUB_USER}/${REPO_NAME}.git"
git push -f "https://${GITHUB_TOKEN}@github.com/${GITHUB_USER}/${REPO_NAME}.git" main
echo "[√] 推送成功"

# ---------- 后续指引 ----------
cat <<EOF

============================================================
  推送完成！下面是剩下 3 步（需要你在 GitHub 网页 + 本机操作）
============================================================

── 第 3 步：在本机导出 WorkBuddy token ─────────────────────
  打开终端，cd 到这个项目目录，运行：

      python refresh_token.py --gh-repo ${GITHUB_USER}/${REPO_NAME}

  屏幕上看到 "已写入 GitHub Secret WB_ACCESS_TOKEN" 即可。
  token 会自动写入到第 4 步要配置的 Secret 里。

  （macOS 上 WorkBuddy 客户端不一定可用；若加密信封无法在本机解密，
   则改用 export token 后手动写入 Secret 的方式，见 README。）

── 第 4 步：配置另外两个 Secret ─────────────────────────────
  打开 https://github.com/${GITHUB_USER}/${REPO_NAME}/settings/secrets/actions/new

  如果第 3 步没自动写，则需要手动建：

      Name: WB_ACCESS_TOKEN     Value: 复制的 token
      Name: WECHAT_PUSH_TYPE    Value: serverchan  或  pushplus
      Name: WECHAT_PUSH_KEY     Value: 拿到的 SendKey / token

── 第 5 步：启用 Actions 并跑一次 ───────────────────────────
  1. 进入仓库，点击上方 "Actions" 页签
  2. 如果提示 "I understand my workflows..."，点启用
  3. 左侧选 "Buddy 加油站每日自动化"
  4. 右侧点 "Run workflow" - "Run workflow"
  5. 几秒后 Actions 日志会打印结果；微信应收到推送

============================================================
EOF