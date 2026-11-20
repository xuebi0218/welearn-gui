# -*- coding: utf-8 -*-
"""并发验证 2：两路真实提交，看各自课时时长是否都增加。"""
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

base = wg.requests.Session()
wg.welearn_password_login(base, WL_USER, WL_PASS)
COOKIES = base.cookies.get_dict()
UA = wg._SESSION_PROFILE


def clone():
    s = wg.requests.Session()
    s.cookies.update(COOKIES)
    s.headers['User-Agent'] = UA[0]
    return s


targets = []
for unit_i in range(0, 6):
    for c in (wg.welearn_get_lessons(base, CID, UID, unit_i, CLASSID) or []):
        if str(c.get("isvisible", "true")).lower() == "false":
            continue
        if "未" not in c.get("iscomplete", ""):
            continue
        targets.append((unit_i, c))
    if len(targets) >= LANES:
        break
targets = targets[:LANES]

before = {}
for u, c in targets:
    before[c["id"]] = wg.welearn_sco_requirements(base, CID, UID, CLASSID, c["id"])["use_seconds"]
print("before:", before)

out = {}


def lane(u, c, delay):
    time.sleep(delay)
    s = clone()
    t0 = time.time()
    r = wg.welearn_curriculum_submit(s, CID, UID, CLASSID, c["id"], 88, learntime=60,
                                     unitidx=u, adaptive=False, duration_cap=90)
    out[c["id"]] = (r, round(time.time() - t0, 1))


ths = [threading.Thread(target=lane, args=(u, c, 8 * i)) for i, (u, c) in enumerate(targets)]
t0 = time.time()
for t in ths:
    t.start()
for t in ths:
    t.join()
print(f"总耗时 {time.time()-t0:.0f}s")

time.sleep(4)
for u, c in targets:
    after = wg.welearn_sco_requirements(base, CID, UID, CLASSID, c["id"])["use_seconds"]
    r, secs = out[c["id"]]
    print(f"{c['id']}: {before[c['id']]} -> {after} (+{after-before[c['id']]}) "
          f"用时{secs}s way1={r['way1']} way2={r['way2']} verified={r['verified']}")
