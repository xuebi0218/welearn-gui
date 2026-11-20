# -*- coding: utf-8 -*-
"""诊断 2：以 startsco.useSeconds 为服务端真值，测心跳累计规则。"""
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
scoid = "m-3-3-8"
ref = "https://welearn.sflep.com/student/StudyCourse.aspx"
H = wg._build_headers(ref)


def use_sec():
    r = s.post(wg.AJAX_SCO_URL,
               data={"action": "startsco160928", "cid": cid, "scoid": scoid,
                     "uid": uid, "classid": classid, "tid": -1, "nocache": time.time()},
               headers=H, timeout=20)
    import json
    return json.loads(r.text)


print("t0 startsco:", use_sec())
base = use_sec()["useSeconds"]

for i in range(1, 4):
    time.sleep(30)
    st = i * 30
    r = s.post(wg.AJAX_SCO_URL,
               data={"action": "keepsco_with_getticket_with_updatecmitime", "uid": uid,
                     "cid": cid, "scoid": scoid, "session_time": st,
                     "total_time": base + st, "timelimitsec": 1080,
                     "endcaltime": "false", "nocache": time.time()},
               headers=H, timeout=20)
    print(f"hb#{i} st={st} ->", r.text[:160])

time.sleep(3)
print("t1 startsco:", use_sec())
