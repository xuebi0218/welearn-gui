# -*- coding: utf-8 -*-
"""探测指定单元的课时：题量、题型、模板长度、timelitsec / useSeconds。

用法：
    python tools/probe_unit.py 8            # 第 8 章
环境变量：WELEARN_COOKIE 或 tools/cookie.txt
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))
import requests  # noqa: E402

import welearn_gui as wg  # noqa: E402


def main():
    unit_idx = int(sys.argv[1]) if len(sys.argv) > 1 else 8
    cookie = os.environ.get("WELEARN_COOKIE", "").strip()
    if not cookie:
        p = os.path.join(os.path.dirname(os.path.abspath(__file__)), "cookie.txt")
        if os.path.exists(p):
            cookie = open(p, encoding="utf-8").read().strip()
    if not cookie:
        print("缺少 Cookie：设置 WELEARN_COOKIE 或写 tools/cookie.txt")
        return

    s = requests.Session()
    s.headers.update(wg._build_headers())
    wg._reset_ua_profile(s)
    ok, data = wg.welearn_validate_session(s, cookie)
    if not ok:
        print("登录失败:", data)
        return
    courses = data
    print("课程:", [(c.get("cid"), c.get("coursename") or c.get("name")) for c in courses])

    cid = courses[0].get("cid") if courses else None
    for c in courses:
        if "3222" in str(c.get("cid")):
            cid = c.get("cid")
    uid, classid = None, None
    for c in courses:
        if str(c.get("cid")) == str(cid):
            uid = c.get("uid")
            classid = c.get("classid")
    if not uid:
        uid, classid = wg.welearn_get_course_info(s, cid)
    print("cid/uid/classid:", cid, uid, classid)

    units = wg.welearn_get_units(s, cid, uid)
    print("单元数:", len(units))
    if unit_idx > len(units):
        print("单元不存在")
        return
    u = units[unit_idx - 1]
    print("目标单元:", u)
    lessons = wg.welearn_get_lessons(s, cid, uid, u.get("unitidx", unit_idx - 1), classid)
    print("课时数:", len(lessons))

    for les in lessons:
        scoid = les.get("scoid") or les.get("id")
        name = les.get("name") or les.get("title")
        addr, aerr = wg.welearn_get_sco_addr(s, cid, scoid)
        tpl = (wg._fetch_sco_template(s, addr) or "") if addr else ""
        qs = wg.parse_sco_questions(tpl) if tpl else []
        kinds = {}
        for q in qs:
            kinds[q.get("type")] = kinds.get(q.get("type"), 0) + 1
        ref = f"https://welearn.sflep.com/Student/StudyCourse.aspx?cid={cid}&classid={classid}&sco={scoid}"
        req = wg.welearn_sco_requirements(s, cid, uid, classid, scoid, referer=ref)
        print(f"\n[{scoid}] {name}")
        print(f"  addr={addr} err={aerr}")
        print(f"  template={len(tpl)}B  questions={len(qs)}  kinds={kinds}")
        print(f"  learntime={les.get('learntime')} iscomplete={les.get('iscomplete')}")
        print(f"  timelitsec={req.get('timelitsec')} useSeconds={req.get('use_seconds')} ok={req.get('ok')}")


if __name__ == "__main__":
    main()
