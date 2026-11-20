# -*- coding: utf-8 -*-
"""探测：并发 SCO 是否各自并行累计时长；长时间间隔是否被截断（cap）。"""
import json

import os as _os

WL_USER = _os.environ.get("WELEARN_USER", "")
WL_PASS = _os.environ.get("WELEARN_PASS", "")
import sys
import time

import requests

sys.path.insert(0, "src")
import welearn_gui as wg  # noqa: E402

s = requests.Session()
ok, _ = wg.welearn_password_login(s, WL_USER, WL_PASS)
cid = "3222"
uid, classid = wg.welearn_get_course_info(s, cid)
H = wg._build_headers("https://welearn.sflep.com/student/StudyCourse.aspx")
units = wg.welearn_get_units(s, cid, uid)
todo = []
for i, u in enumerate(units):
    for c in (wg.welearn_get_lessons(s, cid, uid, i, classid) or []):
        if "未" in (c.get("iscomplete") or "") and c.get("isvisible") != "false":
            todo.append(c)
A, B = todo[3], todo[4]
print("A", A["id"], A["name"])
print("B", B["id"], B["name"])


def start(sco):
    r = s.post(wg.AJAX_SCO_URL, data={"action": "startsco160928", "cid": cid, "scoid": sco,
                                      "uid": uid, "classid": classid, "tid": -1, "nocache": time.time()},
               headers=H, timeout=20)
    print(" start", sco, r.text[:160])
    return r


def hb(sco, st, tt, tl=1080, end="false"):
    r = s.post(wg.AJAX_SCO_URL, data={"action": "keepsco_with_getticket_with_updatecmitime", "uid": uid, "cid": cid,
                                      "scoid": sco, "session_time": st, "total_time": tt,
                                      "timelimitsec": tl, "endcaltime": end, "nocache": time.time()},
               headers=H, timeout=20)
    txt = r.text
    try:
        idx = txt.rindex('{"ret":0')
        tail = json.loads(txt[idx:])
    except Exception:
        tail = {}
    print(f" hb {sco} st={st} -> {txt[:200]}")
    return tail.get("seconds")


start(A["id"])
start(B["id"])
t0 = time.time()
time.sleep(45)
sa = hb(A["id"], 45, 45 + int(A.get("learntime_s", 0) or 0))
sb = hb(B["id"], 45, 45)
print(f">>> 并发 45s 后:A 记 {sa}s,B 记 {sb}s(两者都≈45 说明并发各自计时)")

t1 = time.time()
time.sleep(150)
sc = hb(A["id"], 45 + int(time.time() - t0), 0)
print(f">>> A 间隔 {int(time.time()-t0)}s 后单次记 {sc}s(判断服务端是否有 cap)")
print("完成,用时", int(time.time() - t0), "s")
