# -*- coding: utf-8 -*-
"""并发压测：N 路 SCO 同时心跳，验证每路是否都能独立计时（服务端是否按账号限流）。

复制已登录会话的 Cookie 到 N 个独立 Session，避免 requests.Session 跨线程共享连接池。
"""
import random

import os as _os

WL_USER = _os.environ.get("WELEARN_USER", "")
WL_PASS = _os.environ.get("WELEARN_PASS", "")
import sys
import threading
import time

sys.path.insert(0, "src")
import welearn_gui as wg   # noqa: E402

CID, UID, CLASSID = "3222", "13178431", "779946"
LANES = 4
ROUNDS = 3
INTERVAL = 30          # 秒

base = wg.requests.Session()
ok, _ = wg.welearn_password_login(base, WL_USER, WL_PASS)
print("login:", ok)
COOKIES = base.cookies.get_dict()
UA = wg._SESSION_PROFILE


def clone():
    s = wg.requests.Session()
    s.cookies.update(COOKIES)
    s.headers['User-Agent'] = UA[0]
    return s


# 选 N 个待完成课时
lessons = []
for unit_i in range(0, 6):
    for c in (wg.welearn_get_lessons(base, CID, UID, unit_i, CLASSID) or []):
        if str(c.get("isvisible", "true")).lower() == "false":
            continue
        if "未" not in c.get("iscomplete", ""):
            continue
        lessons.append((unit_i, c))
    if len(lessons) >= LANES:
        break
lessons = lessons[:LANES]
print("lanes:", [(u, c["id"]) for u, c in lessons])

results = {}


def lane(i, unit_i, c):
    s = clone()
    scoid = c["id"]
    req = wg.welearn_sco_requirements(s, CID, UID, CLASSID, scoid)
    start = req["use_seconds"]
    used = 0
    for r in range(ROUNDS):
        time.sleep(INTERVAL + random.uniform(-3, 3))
        used += INTERVAL
        resp = wg.welearn_heartbeat_full(s, CID, UID, scoid, str(used),
                                         str(start + used), timelitsec=req["timelitsec"])
        print(f"  L{i} {scoid} st={used} -> ok={resp['ok']} sec={resp['seconds']}")
    req2 = wg.welearn_sco_requirements(s, CID, UID, CLASSID, scoid)
    results[scoid] = (start, req2["use_seconds"], req2["use_seconds"] - start)


threads = [threading.Thread(target=lane, args=(i, u, c)) for i, (u, c) in enumerate(lessons)]
t0 = time.time()
for t in threads:
    t.start()
    time.sleep(0.6)
for t in threads:
    t.join()

print(f"\n并发 {LANES} 路，{ROUNDS}×{INTERVAL}s，总耗时 {time.time()-t0:.0f}s")
for scoid, (a, b, d) in results.items():
    print(f"  {scoid}: {a} -> {b}  (+{d})")

blocked, why = wg.welearn_check_gates(base, UID, CID)
print("闸门:", blocked, why)
