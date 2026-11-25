# -*- coding: utf-8 -*-
"""实测第 8 章某一节的完整提交链路：题量 → 学习 → setscoinfo → savescoinfo → 回读。

用法: python tools/probe_submit_unit8.py <课时序号 1-17> [学习秒数]
"""
import os
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))
import requests  # noqa: E402

import welearn_gui as wg  # noqa: E402

CID, UID, CLASSID, UNIT_POS = 2415, 11433107, 770346, 8


def main():
    idx = int(sys.argv[1]) if len(sys.argv) > 1 else 8
    secs = int(sys.argv[2]) if len(sys.argv) > 2 else 60
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
    les = lessons[idx - 1]
    scoid = les.get("scoid") or les.get("id")
    print("lesson:", les.get("name"), scoid)

    addr, _ = wg.welearn_get_sco_addr(s, CID, scoid)
    tpl = wg._fetch_sco_template(s, addr) or ""
    qs = wg.parse_sco_questions(tpl)
    print("questions:", len(qs), [q.get("type") for q in qs][:10])
    inter = wg.generate_interactions(qs, 80) if qs else ("", "")
    i_json, i_info = (inter + ("", ""))[:2] if isinstance(inter, tuple) else (inter, "")
    print("interactions json:", type(i_json).__name__, "count:", len(i_json))
    print("interactions info len:", len(i_info))
    if i_json:
        print("  json head:", str(i_json)[:300])

    before = wg.welearn_sco_requirements(s, CID, UID, CLASSID, scoid)
    print("before:", before)

    t0 = time.time()
    r = wg.welearn_curriculum_submit(s, CID, UID, CLASSID, scoid, crate=80,
                                     learntime=secs, unitidx=u.get("unitidx", UNIT_POS - 1),
                                     adaptive=False, duration_cap=secs + 30)
    print("submit result:", r)
    print("wall:", round(time.time() - t0, 1), "s")

    after = wg.welearn_sco_requirements(s, CID, UID, CLASSID, scoid)
    print("after:", after)
    print("delta useSeconds:", (after.get("use_seconds") or 0) - (before.get("use_seconds") or 0))


if __name__ == "__main__":
    main()
