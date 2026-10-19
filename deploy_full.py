#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""deploy_full.py —— WorkBuddy Auto Checkin · 全自动部署脚本

一键完成：
  1. 把当前目录的代码 push 到你的 GitHub 仓库
  2. 把 WECHAT_PUSH_TYPE 与 WECHAT_PUSH_KEY 两个 Secret 写入仓库
  3. 打印后续 2 步的详细指引

为什么用 gh CLI 而不是 GitHub API 直接调？
  - gh CLI 内部处理 Secret 加密（libsodium box_seal），无需写加密代码
  - 无需准备 Personal Access Token（gh auth login 走 OAuth）
  - gh CLI 是 GitHub 官方工具，所有 GitHub Actions 用户都有

用法：
  1. 安装 gh CLI（一次性，5 分钟）：
       Windows:  winget install GitHub.CLI
                 或 https://github.com/cli/cli/releases/latest 下载 gh_windows_amd64.msi
       macOS:    brew install gh
       Linux:    apt install gh  /  dnf install gh
  2. gh auth login（一次性，按提示走完 OAuth）
  3. cd 到项目根目录（包含 wb_auto.py 的目录）
  4. python deploy_full.py
     按提示填：用户名 / 仓库名 / 推送渠道 / 推送 key
"""

import os
import subprocess
import sys


def run(cmd, *, check=True, capture=False, input_text=None):
    """执行命令并打印。失败立即退出。"""
    if isinstance(cmd, list):
        printable = " ".join(cmd)
    else:
        printable = cmd
    print("  $ " + printable)
    try:
        r = subprocess.run(
            cmd,
            shell=isinstance(cmd, str),
            check=False,
            capture_output=capture,
            text=True,
            input=input_text,
        )
    except FileNotFoundError as e:
        print("  [X] 命令未找到：" + str(e))
        sys.exit(1)
    if check and r.returncode != 0:
        if capture and r.stderr:
            print("  [X] 失败：" + r.stderr.strip())
        sys.exit(1)
    return r


def prompt(label, default=None, secret=False):
    """交互式输入，带默认值（回车采用）。"""
    suffix = (" [" + default + "]" if default else "")
    while True:
        v = input(label + suffix + "：").strip()
        if not v and default:
            return default
        if v:
            return v
        print("  ! 不能为空，请重新输入")


def main():
    print()
    print("=" * 64)
    print("  WorkBuddy Auto Checkin · 全自动部署")
    print("=" * 64)
    print()
    print("  这个脚本会做 3 件事：")
    print("    [1] 把当前目录代码 push 到你的 GitHub 仓库")
    print("    [2] 把 WECHAT_PUSH_TYPE 与 WECHAT_PUSH_KEY 写入 Secret")
    print("    [3] 打印剩余 2 步的指引（在 GitHub 网页 + 本机操作）")
    print()

    # ---------- 1. 前提检查 ----------
    print("[检查] gh CLI 是否可用...")
    r = subprocess.run(["gh", "--version"], capture_output=True, text=True)
    if r.returncode != 0:
        print("  [X] gh CLI 未安装或不在 PATH 中")
        print()
        print("  安装方式：")
        print("    Windows: winget install GitHub.CLI")
        print("             或 https://github.com/cli/releases 下载 .msi")
        print("    macOS:   brew install gh")
        print("    Linux:   apt install gh / dnf install gh")
        print()
        sys.exit(1)
    print("  [√] gh CLI 已安装：" + r.stdout.strip().split("\n")[0])

    print("[检查] gh auth status...")
    r = subprocess.run(["gh", "auth", "status"], capture_output=True, text=True)
    if r.returncode != 0:
        print("  [X] gh CLI 未登录")
        print()
        print("  请先运行：gh auth login")
        print("  选 HTTPS + 浏览器登录，登录账号必须能访问目标仓库")
        sys.exit(1)
    # 从 stderr 提取登录用户名（status 把结果打到 stderr）
    import re
    m = re.search(r"Logged in to github\.com account\s+(\S+)", r.stderr + r.stdout)
    logged_in = m.group(1) if m else None
    if logged_in:
        print("  [√] 已登录为 " + logged_in)

    # ---------- 2. 收集参数 ----------
    print()
    print("─" * 40 + " 参数 ")
    user = prompt("你的 GitHub 用户名", default=logged_in or "Zuolijia")
    repo = prompt("仓库名", default="workbuddy_auto_checkin")

    print()
    print("─" * 40 + " 微信推送渠道 ")
    print("  二选一：serverchan（推荐，免费每天 5 条）")
    print("          pushplus  （免费每天 200 条）")
    print()
    while True:
        push_type = prompt("渠道", default="serverchan").lower().strip()
        if push_type in ("serverchan", "pushplus"):
            break
        print("  ! 请输入 serverchan 或 pushplus")

    push_key = prompt("SendKey / token", default=None)
    if not push_key:
        print("  [X] 推送 key 不能为空")
        sys.exit(1)

    # ---------- 3. push ----------
    print()
    print("[1/2] 推送代码...")
    repo_url = "https://github.com/" + user + "/" + repo + ".git"

    # 设置 git 用户身份（push 需要）
    run(["git", "config", "user.email", "workbuddy-auto@local"], check=False)
    run(["git", "config", "user.name", "workbuddy-auto"], check=False)

    # 配置 remote
    run(["git", "remote", "remove", "origin"], check=False)
    run(["git", "remote", "add", "origin", repo_url])

    # push
    r = subprocess.run(["git", "push", "-u", "origin", "main"],
                       text=True, capture_output=True)
    if r.returncode != 0:
        print("  [X] push 失败：" + (r.stderr or r.stdout).strip())
        sys.exit(1)
    print("  [√] 推送完成")

    # ---------- 4. 写入 Secret ----------
    print()
    print("[2/2] 写入微信推送 Secret...")

    r = subprocess.run(
        ["gh", "secret", "set", "WECHAT_PUSH_TYPE",
         "--repo", user + "/" + repo],
        input=push_type, text=True, capture_output=True,
    )
    if r.returncode != 0:
        print("  [X] WECHAT_PUSH_TYPE 写入失败：" + r.stderr.strip())
        sys.exit(1)
    print("  [√] WECHAT_PUSH_TYPE 已写入")

    r = subprocess.run(
        ["gh", "secret", "set", "WECHAT_PUSH_KEY",
         "--repo", user + "/" + repo],
        input=push_key, text=True, capture_output=True,
    )
    if r.returncode != 0:
        print("  [X] WECHAT_PUSH_KEY 写入失败：" + r.stderr.strip())
        sys.exit(1)
    print("  [√] WECHAT_PUSH_KEY 已写入")

    # ---------- 5. 打印剩余步骤 ----------
    print()
    print("=" * 64)
    print("  推送完成！剩下 2 步需要你操作")
    print("=" * 64)
    print()
    print("─ 第 1 步：在你装 WorkBuddy 的电脑上导出 token ───────────")
    print()
    print("  打开 PowerShell 或 cmd，cd 到这个项目目录，运行：")
    print()
    print("      refresh_token.exe --gh-repo " + user + "/" + repo)
    print()
    print("  或装了 Python：")
    print()
    print("      python refresh_token.py --gh-repo " + user + "/" + repo)
    print()
    print("  屏幕显示 '已写入 GitHub Secret WB_ACCESS_TOKEN' 即完成。")
    print("  （token 由 gh CLI 加密后写入仓库，这一步在 GitHub 网页上看不到明文）")
    print()
    print("─ 第 2 步：启用 Actions + 手动跑一次 ─────────────────────")
    print()
    print("  打开 https://github.com/" + user + "/" + repo + "/actions")
    print("  - 第一次进去会提示 'I understand my workflows, go ahead and enable them'，点启用")
    print("  - 左侧选 'Buddy 加油站每日自动化'")
    print("  - 右侧点 'Run workflow' - 'Run workflow'")
    print("  - 几秒后看日志；微信会收到推送")
    print()
    print("=" * 64)
    print()


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n已取消")
        sys.exit(130)