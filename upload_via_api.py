#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""upload_via_api.py —— 通过 GitHub REST API（api.github.com）把整个目录推送到仓库。

为什么不用 `git push`：
    部分网络环境（含本机当前状态）无法连通 github.com:443，但 api.github.com 可达。
    GitHub 的 REST 与 Git Database API 完全等价于一次 git push，
    会生成同样的 commit / branch / tree，只是由脚本代劳。

用法：
    1) 在 https://github.com/settings/tokens 申请 Fine-grained token
       （Repository access 选中目标仓库，Contents = Read and write）
    2) 运行本脚本，按提示粘贴 token（输入不回显，不会留在屏幕上）
    3) 脚本逐个文件建 blob -> 组 tree -> 建 commit -> 更新 main 分支

不落盘：token 只在内存中，用完即弃。
"""

import base64
import fnmatch
import json
import mimetypes
import os
import sys
import urllib.error
import urllib.request

OWNER = "Zuolijia"
REPO = "workbuddy_auto_checkin"
BRANCH = "main"
API = "https://api.github.com"

# 忽略规则：gitignore 内容 + 额外排除（编译产物、体积大、无需入库）
EXTRA_IGNORE = [
    "*.exe",
    ".git/*",
    "__pycache__/*",
    "*.pyc",
    "*.png",
]


def log(msg):
    print(msg, flush=True)


def api(method, path, token, payload=None):
    """调用 GitHub REST API，返回 (status, body_dict)。"""
    url = API + path
    data = None
    headers = {
        "Authorization": "Bearer " + token,
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
        "User-Agent": "workbuddy-uploader",
    }
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(url, data=data, method=method, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=45) as resp:
            body = resp.read().decode("utf-8", "replace")
            return resp.status, (json.loads(body) if body.strip() else {})
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", "replace")
        try:
            return e.code, json.loads(body)
        except ValueError:
            return e.code, {"raw": body[:500]}
    except Exception as e:
        return 0, {"error": "%s: %s" % (type(e).__name__, e)}


def read_token():
    """优先读环境变量；否则交互式输入（不回显）。"""
    tok = os.environ.get("GITHUB_TOKEN", "").strip()
    if tok:
        return tok
    if sys.stdin.isatty():
        try:
            import getpass
            return getpass.getpass("粘贴 GitHub token（输入不回显）: ").strip()
        except Exception:
            pass
    try:
        return input("粘贴 GitHub token: ").strip()
    except EOFError:
        return ""


def load_ignore_patterns():
    pats = list(EXTRA_IGNORE)
    gi = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".gitignore")
    if os.path.isfile(gi):
        with open(gi, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                if line.endswith("/"):
                    line = line + "*"
                pats.append(line)
    return pats


def collect_files():
    root = os.path.dirname(os.path.abspath(__file__))
    pats = load_ignore_patterns()
    files = []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in (".git", "__pycache__")]
        for name in filenames:
            full = os.path.join(dirpath, name)
            rel = os.path.relpath(full, root).replace("\\", "/")
            if any(fnmatch.fnmatch(rel, p) or fnmatch.fnmatch(name, p) for p in pats):
                continue
            files.append((rel, full))
    return sorted(files)


def main():
    log("=== GitHub 仓库上传（走 REST API 通道）===")
    log("目标：https://github.com/%s/%s  分支：%s" % (OWNER, REPO, BRANCH))
    log("")

    token = read_token()
    if not token:
        log("未提供 token，退出。")
        return 2

    # 0) 验证 token + 仓库权限
    status, me = api("GET", "/user", token)
    if status != 200:
        log("[x] token 校验失败（HTTP %s）：%s" % (status, json.dumps(me, ensure_ascii=False)[:300]))
        return 2
    log("[√] token 有效，身份：%s" % me.get("login"))

    status, repo = api("GET", "/repos/%s/%s" % (OWNER, REPO), token)
    if status != 200:
        log("[x] 无法访问仓库（HTTP %s）：%s" % (status, json.dumps(repo, ensure_ascii=False)[:300]))
        return 2
    log("[√] 仓库可访问：%s（%s）" % (repo.get("full_name"), "private" if repo.get("private") else "public"))

    files = collect_files()
    if not files:
        log("[x] 没有可上传的文件，退出。")
        return 2
    log("[i] 待上传 %d 个文件" % len(files))
    log("")

    # 1) 取当前 main 的 commit（用来建 parent 与判断是否需要先建分支）
    status, ref = api("GET", "/repos/%s/%s/git/ref/heads/%s" % (OWNER, REPO, BRANCH), token)
    parent = None
    branch_exists = (status == 200)
    if branch_exists:
        parent = ref.get("object", {}).get("sha")

    # 2) 逐个建 blob
    tree_entries = []
    ok = 0
    for idx, (rel, full) in enumerate(files, 1):
        with open(full, "rb") as f:
            raw = f.read()
        mime = mimetypes.guess_type(rel)[0] or "application/octet-stream"
        is_text = mime.startswith("text/") or rel.endswith(
            (".yml", ".yaml", ".md", ".py", ".js", ".sh", ".bat", ".json", ".txt", ".gitignore")
        ) or rel == ".gitignore"
        content = raw.decode("utf-8") if is_text else base64.b64encode(raw).decode("ascii")
        st, blob = api("POST", "/repos/%s/%s/git/blobs" % (OWNER, REPO), token, {
            "content": content,
            "encoding": "utf-8" if is_text else "base64",
        })
        if st != 201:
            log("[x] blob 失败 %s（HTTP %s）：%s" % (rel, st, json.dumps(blob, ensure_ascii=False)[:200]))
            return 1
        tree_entries.append({
            "path": rel,
            "mode": "100755" if rel.endswith((".sh", ".bat")) else "100644",
            "type": "blob",
            "sha": blob["sha"],
        })
        ok += 1
        log("    (%2d/%2d) %-40s %6d B" % (idx, len(files), rel, len(raw)))

    log("")
    log("[√] %d 个 blob 全部创建成功" % ok)

    # 3) 组 tree
    st, tree = api("POST", "/repos/%s/%s/git/trees" % (OWNER, REPO), token, {
        "base_tree": parent,   # 基于现有 tree 增量提交
        "tree": tree_entries,
    })
    if st != 201:
        log("[x] tree 创建失败（HTTP %s）：%s" % (st, json.dumps(tree, ensure_ascii=False)[:300]))
        return 1
    log("[√] tree 创建成功：%s" % tree["sha"])

    # 4) 建 commit
    st, commit = api("POST", "/repos/%s/%s/git/commits" % (OWNER, REPO), token, {
        "message": "feat: 初始化 Buddy 加油站每日自动化（微信推送版）\n\n"
                   "- wb_auto.py：签到领积分 + 派猫猫旅行领礼物 + 微信推送（Server酱/PushPlus）\n"
                   "- daily.yml：每天北京时间 08:10 / 14:10 / 20:10 自动执行\n"
                   "- refresh_token.py：本机一次性导出登录态并写入 Secret\n"
                   "- 移除原项目飞书推送依赖",
        "tree": tree["sha"],
        "parents": [parent] if parent else [],
    })
    if st != 201:
        log("[x] commit 创建失败（HTTP %s）：%s" % (st, json.dumps(commit, ensure_ascii=False)[:300]))
        return 1
    log("[√] commit 创建成功：%s" % commit["sha"])

    # 5) 更新/创建分支
    if branch_exists:
        st, res = api("PATCH", "/repos/%s/%s/git/refs/heads/%s" % (OWNER, REPO, BRANCH), token,
                      {"sha": commit["sha"], "force": False})
    else:
        st, res = api("POST", "/repos/%s/%s/git/refs" % (OWNER, REPO), token,
                      {"ref": "refs/heads/%s" % BRANCH, "sha": commit["sha"]})
    if st not in (200, 201):
        log("[x] 分支更新失败（HTTP %s）：%s" % (st, json.dumps(res, ensure_ascii=False)[:300]))
        return 1

    log("")
    log("========================================")
    log("  推送完成！")
    log("  https://github.com/%s/%s" % (OWNER, REPO))
    log("  commit: %s" % commit["sha"])
    log("========================================")
    log("")
    log("剩余步骤：")
    log("  1) 网页填 Secret：")
    log("     https://github.com/%s/%s/settings/secrets/actions/new" % (OWNER, REPO))
    log("     - WB_ACCESS_TOKEN  （先填占位符，等第 2 步自动覆盖）")
    log("     - WECHAT_PUSH_TYPE （serverchan 或 pushplus）")
    log("     - WECHAT_PUSH_KEY  （SendKey / token）")
    log("  2) 本机导出 WorkBuddy token：")
    log("     cd %s" % os.path.dirname(os.path.abspath(__file__)))
    log("     python refresh_token.py --gh-repo %s/%s" % (OWNER, REPO))
    log("  3) 启用并试跑 Actions：")
    log("     https://github.com/%s/%s/actions" % (OWNER, REPO))
    return 0


if __name__ == "__main__":
    sys.exit(main())
