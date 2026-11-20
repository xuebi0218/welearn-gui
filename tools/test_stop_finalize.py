# -*- coding: utf-8 -*-
"""验证「停止也要收尾」：中途停止后，已学时长是否真的入账。"""
import sys

import os as _os

WL_USER = _os.environ.get("WELEARN_USER", "")
WL_PASS = _os.environ.get("WELEARN_PASS", "")
import time

sys.path.insert(0, "src")
import welearn_gui as wg   # noqa: E402

s = wg.requests.Session()
wg.welearn_password_login(s, WL_USER, WL_PASS)
cid, uid, classid = "3222", "13178431", "779946"
unit_i, scoid = 2, "m-3-3-9"

before = wg.welearn_sco_requirements(s, cid, uid, classid, scoid)
print("before:", before)

t0 = time.time()
r = wg.welearn_curriculum_submit(s, cid, uid, classid, scoid, 85, learntime=120,
                                 unitidx=unit_i, adaptive=False, duration_cap=120,
                                 stop_check=lambda: time.time() - t0 > 50)
print("result:", r, f"实际 {time.time()-t0:.1f}s")
print("after :", wg.welearn_sco_requirements(s, cid, uid, classid, scoid))
