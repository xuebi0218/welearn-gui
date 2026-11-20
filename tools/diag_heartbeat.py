# -*- coding: utf-8 -*-
"""诊断：心跳到底有没有把时长记上去。"""
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
unit_i, scoid = 2, "m-3-3-8"

print("before:", wg.welearn_verify_learntime(s, cid, uid, classid, unit_i, scoid))
req = wg.welearn_sco_requirements(s, cid, uid, classid, scoid)
print("req:", req)
base = req["use_seconds"]

ref = "https://welearn.sflep.com/student/StudyCourse.aspx"
H = wg._build_headers(ref)


def hb(st, tt):
    r = s.post(wg.AJAX_SCO_URL,
               data={"action": "keepsco_with_getticket_with_updatecmitime",
                     "uid": uid, "cid": cid, "scoid": scoid,
                     "session_time": st, "total_time": tt,
                     "timelimitsec": req["timelitsec"], "endcaltime": "false",
                     "nocache": time.time()},
               headers=H, timeout=20)
    print(f"hb(st={st},tt={tt}) ->", r.text[:200])
    return r


hb(0, base)
time.sleep(70)
hb(70, base + 70)
time.sleep(2)
print("after hb:", wg.welearn_verify_learntime(s, cid, uid, classid, unit_i, scoid))

# 显式 updatecmitime
r = s.post(wg.AJAX_SCO_URL,
           data={"action": "updatecmitime", "uid": uid, "cid": cid, "scoid": scoid,
                 "total_time": base + 70, "session_time": 70, "nocache": time.time()},
           headers=H, timeout=20)
print("updatecmitime ->", r.text[:200])
time.sleep(2)
print("after update:", wg.welearn_verify_learntime(s, cid, uid, classid, unit_i, scoid))
