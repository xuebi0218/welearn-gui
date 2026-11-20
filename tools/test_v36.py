# -*- coding: utf-8 -*-
"""v3.6 端到端自检：登录 → 闸门检查 → 单课时提交（短时长）→ 回读校验。"""
import sys

import os as _os

WL_USER = _os.environ.get("WELEARN_USER", "")
WL_PASS = _os.environ.get("WELEARN_PASS", "")
import time

sys.path.insert(0, "src")
import welearn_gui as wg   # noqa: E402

USER, PWD = WL_USER, WL_PASS


def main():
    s = wg.requests.Session()
    ok, msg = wg.welearn_password_login(s, USER, PWD)
    print("login:", ok, msg if not ok else f"{len(msg)} courses")
    if not ok:
        return 1

    cid = "3222"
    uid, classid = wg.welearn_get_course_info(s, cid)
    print("uid/classid:", uid, classid)

    blocked, why = wg.welearn_check_gates(s, uid, cid)
    print("gates:", blocked, why)

    target = None
    for unit_i in range(0, 6):
        lessons = wg.welearn_get_lessons(s, cid, uid, unit_i, classid) or []
        for c in lessons:
            if str(c.get("isvisible", "true")).lower() != "false" \
                    and "未" in c.get("iscomplete", ""):
                target = (unit_i, c)
                break
        if target:
            break
    if not target:
        print("no unfinished lesson")
        return 0
    unit_i, c = target
    print(f"test lesson: unit={unit_i} scoid={c['id']} loc={c['location']} learntime={c.get('learntime')}")

    req = wg.welearn_sco_requirements(s, cid, uid, classid, c["id"])
    print("requirements:", req)

    t0 = time.time()
    r = wg.welearn_curriculum_submit(s, cid, uid, classid, c["id"], 85,
                                     learntime=60, unitidx=unit_i,
                                     adaptive=False, duration_cap=90)
    print("submit:", r, f"耗时 {time.time()-t0:.1f}s")

    after = wg.welearn_verify_learntime(s, cid, uid, classid, unit_i, c["id"])
    print("回读 learntime:", after)
    return 0


if __name__ == "__main__":
    sys.exit(main())
