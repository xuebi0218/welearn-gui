# -*- coding: utf-8 -*-
"""验证 v3.9：单节上限截断 + 节内进度回调 + 停止时也落库。"""
import os
import sys
import threading
import time

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))
import requests  # noqa: E402

import welearn_gui as wg  # noqa: E402

CID, UID, CLASSID, UNIT_POS = 2415, 11433107, 770346, 8


def main():
    cookie = open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "cookie.txt"),
                  encoding="utf-8").read().strip()
    s = requests.Session()
    s.headers.update(wg._build_headers())
    wg._reset_ua_profile(s)
    ok, _ = wg.welearn_validate_session(s, cookie)
    print("login:", ok)

    units = wg.welearn_get_units(s, CID, UID)
    u = units[UNIT_POS - 1]
    lessons = wg.welearn_get_lessons(s, CID, UID, u.get("unitidx", UNIT_POS - 1), CLASSID)
    les = lessons[4]          # 05. Task 1
    scoid = les.get("scoid") or les.get("id")
    print("lesson:", les.get("name"), scoid)

    ticks = []

    def cb(info):
        ticks.append(info)
        print("  cb:", info)

    # 40 秒后请求停止，验证「停止也落库 + 统计不为 0」
    stop_flag = threading.Event()
    threading.Timer(40, stop_flag.set).start()

    t0 = time.time()
    r = wg.welearn_curriculum_submit(s, CID, UID, CLASSID, scoid, crate=85,
                                     learntime=30, stop_check=stop_flag.is_set,
                                     unitidx=u.get("unitidx", UNIT_POS - 1),
                                     lesson_cap=120, progress_cb=cb)
    print("result:", r)
    print("wall:", round(time.time() - t0, 1), "s  callbacks:", len(ticks))
    after = wg.welearn_sco_requirements(s, CID, UID, CLASSID, scoid)
    print("after:", after)


if __name__ == "__main__":
    main()
