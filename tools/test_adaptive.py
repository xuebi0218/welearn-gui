# -*- coding: utf-8 -*-
"""完整闭环验证：按 timelitsec 缺口自适应学习一个课时，直到达标。"""
import sys

import os as _os

WL_USER = _os.environ.get("WELEARN_USER", "")
WL_PASS = _os.environ.get("WELEARN_PASS", "")
import time

sys.path.insert(0, "src")
import welearn_gui as wg   # noqa: E402

s = wg.requests.Session()
ok, _ = wg.welearn_password_login(s, WL_USER, WL_PASS)
cid, uid, classid = "3222", "13178431", "779946"

# 选一个未完成且缺口最小的课时，缩短验证时间
best = None
for unit_i in range(0, 6):
    for c in (wg.welearn_get_lessons(s, cid, uid, unit_i, classid) or []):
        if str(c.get("isvisible", "true")).lower() == "false":
            continue
        if "未" not in c.get("iscomplete", ""):
            continue
        req = wg.welearn_sco_requirements(s, cid, uid, classid, c["id"])
        deficit = max(0, req["timelitsec"] - req["use_seconds"])
        print(f"  {c['id']} {c['location'][:40]:40s} use={req['use_seconds']} need={req['timelitsec']} deficit={deficit}")
        if best is None or deficit < best[0]:
            best = (deficit, unit_i, c)

if not best:
    print("没有待完成课时")
    sys.exit(0)
deficit, unit_i, c = best
print(f"\n选定 {c['id']} 缺口 {deficit}s，开始自适应学习…")

t0 = time.time()
r = wg.welearn_curriculum_submit(s, cid, uid, classid, c["id"], 88,
                                 learntime=60, unitidx=unit_i, adaptive=True,
                                 duration_cap=1200)
print("result:", r, f"实际耗时 {time.time()-t0:.1f}s")
print("课后回读:", wg.welearn_verify_learntime(s, cid, uid, classid, unit_i, c["id"]))
