#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""setup_secrets.py —— 一次性写入仓库所需的 3 个 GitHub Actions Secret。

背景：
    Secret 写入必须走 api.github.com（GitHub 对写入内容做 libsodium box_seal 端到端加密），
    SSH 推送通道帮不上忙，所以这一步需要一个带 Contents:Write 权限的 token。
    写完之后，日常推送就走 SSH，不再需要 token。

流程：
    1. getpass 隐藏输入 GitHub token（不回显，不落盘）
    2. 取仓库公钥 → 用 box_seal 加密每个 Secret
    3. PUT /repos/{owner}/{repo}/actions/secrets/{name}
    4. 回读校验，确认 3 个 Secret 都已存在

环境变量：
    WB_PUSH_TYPE   推送渠道，serverchan 或 pushplus（默认 serverchan）
    WB_PUSH_KEY    对应的 SendKey / token（不给则跳过推送类 Secret）
"""

import base64
import json
import os
import sys
import urllib.error
import urllib.request

OWNER = "Zuolijia"
REPO = "workbuddy_auto_checkin"
API = "https://api.github.com"


def log(m):
    print(m, flush=True)


def api(method, path, token, payload=None, raw=False):
    url = API + path
    data = json.dumps(payload).encode("utf-8") if payload is not None else None
    headers = {
        "Authorization": "Bearer " + token,
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
        "User-Agent": "workbuddy-secret-setup",
    }
    if data:
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(url, data=data, method=method, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=45) as resp:
            body = resp.read().decode("utf-8", "replace")
            return resp.status, (body if raw else (json.loads(body) if body.strip() else {}))
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", "replace")
        try:
            return e.code, json.loads(body)
        except ValueError:
            return e.code, {"raw": body[:400]}
    except Exception as e:
        return 0, {"error": "%s: %s" % (type(e).__name__, e)}


def box_seal(plaintext, pubkey_b64):
    """用 PyNaCl 做 box_seal（SealedBox），与 GitHub 官方 secrets 库语义一致。

    pubkey_b64 就是 /actions/secrets/public-key 返回的 key 字段本身（已是纯 base64），
    因此不能再指定 Base64Encoder —— 那会让它再解一次码。
    """
    try:
        import nacl.public
    except ImportError:
        return None, "缺少 PyNaCl，请先运行：pip install pynacl"
    try:
        pk = nacl.public.PublicKey(base64.b64decode(pubkey_b64))
    except Exception as e:
        return None, "公钥解析失败：%s" % e
    sealed = nacl.public.SealedBox(pk).encrypt(plaintext.encode("utf-8"))
    return base64.b64encode(bytes(sealed)).decode("ascii"), None


def main():
    log("=== 写入 GitHub Actions Secret ===")
    log("仓库：%s/%s" % (OWNER, REPO))
    log("")

    # ---- 1. 输入 token ----
    token = os.environ.get("GITHUB_TOKEN", "").strip()
    if not token:
        try:
            import getpass
            token = getpass.getpass("粘贴 GitHub token（输入不回显）: ").strip()
        except Exception:
            token = input("粘贴 GitHub token: ").strip()
    if not token:
        log("[x] 未提供 token，退出。")
        return 2

    st, me = api("GET", "/user", token)
    if st != 200:
        log("[x] token 无效或权限不足（HTTP %s）：%s" % (st, json.dumps(me, ensure_ascii=False)[:300]))
        return 2
    log("[√] token 有效，身份：%s" % me.get("login"))

    # ---- 2. 取仓库公钥 ----
    st, keydata = api("GET", "/repos/%s/%s/actions/secrets/public-key" % (OWNER, REPO), token)
    if st != 200:
        log("[x] 无法读取仓库公钥（HTTP %s）：%s" % (st, json.dumps(keydata, ensure_ascii=False)[:300]))
        return 2
    key_b64 = keydata["key"]
    key_id = keydata["key_id"]
    log("[√] 已获取仓库公钥（key_id=%s）" % key_id)

    # ---- 3. 组装要写的 Secret ----
    secrets = {}

    wb_token = os.environ.get("WB_ACCESS_TOKEN", "").strip()
    if wb_token:
        secrets["WB_ACCESS_TOKEN"] = wb_token
        log("[i] WB_ACCESS_TOKEN：取自环境变量")
    else:
        log("")
        log("请粘贴 WorkBuddy access token（下方脚本已在本机生成过，")
        log("如果你没保存，请重跑 python refresh_token.py 获取）：")
        try:
            import getpass as g2
            wb_token = g2.getpass("粘贴 WB_ACCESS_TOKEN（不回显）: ").strip()
        except Exception:
            wb_token = input("粘贴 WB_ACCESS_TOKEN: ").strip()
        if wb_token:
            secrets["WB_ACCESS_TOKEN"] = wb_token

    push_type = os.environ.get("WB_PUSH_TYPE", "").strip() or input(
        "\n微信推送渠道 [serverchan / pushplus，直接回车默认 serverchan]: "
    ).strip() or "serverchan"
    secrets["WECHAT_PUSH_TYPE"] = push_type

    push_key = os.environ.get("WB_PUSH_KEY", "").strip()
    if not push_key:
        try:
            import getpass as g3
            push_key = g3.getpass("推送 SendKey/token（不回显，留空则不推送）: ").strip()
        except Exception:
            push_key = input("推送 SendKey/token（留空则不推送）: ").strip()
    if push_key:
        secrets["WECHAT_PUSH_KEY"] = push_key
    else:
        log("[!] 未提供推送 key —— 脚本会照常运行，但结果只出现在 Actions 页面，不推微信")

    log("")
    log("准备写入 %d 个 Secret：%s" % (len(secrets), ", ".join(secrets)))
    log("")

    # ---- 4. 逐个加密写入 ----
    failed = []
    for name, value in secrets.items():
        enc, err = box_seal(value, key_b64)
        if err:
            log("[x] %s 加密失败：%s" % (name, err))
            failed.append(name)
            continue
        st, res = api("PUT", "/repos/%s/%s/actions/secrets/%s" % (OWNER, REPO, name), token, {
            "encrypted_value": enc,
            "key_id": key_id,
        })
        if st not in (201, 204):
            log("[x] %s 写入失败（HTTP %s）：%s" % (name, st, json.dumps(res, ensure_ascii=False)[:250]))
            failed.append(name)
        else:
            log("[√] %s 已写入" % name)

    # ---- 5. 回读校验 ----
    log("")
    st, listing = api("GET", "/repos/%s/%s/actions/secrets" % (OWNER, REPO), token)
    if st == 200:
        names = sorted(s["name"] for s in listing.get("secrets", []))
        log("仓库现有 Secret：%s" % (", ".join(names) if names else "(无)"))
        need = ["WB_ACCESS_TOKEN", "WECHAT_PUSH_TYPE", "WECHAT_PUSH_KEY"]
        missing = [n for n in need if n not in names]
        if missing and not failed:
            log("[i] 未写入（可能你选择跳过）：%s" % ", ".join(missing))

    if failed:
        log("")
        log("[x] 部分 Secret 写入失败：%s" % ", ".join(failed))
        return 1

    log("")
    log("========================================")
    log("  Secret 配置完成")
    log("========================================")
    log("")
    log("最后一步：启用并试跑 Actions")
    log("  https://github.com/%s/%s/actions" % (OWNER, REPO))
    log("  左侧选「Buddy 加油站每日自动化」→ 右侧 Run workflow → Run workflow")
    return 0


if __name__ == "__main__":
    sys.exit(main())
