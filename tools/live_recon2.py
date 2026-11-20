# -*- coding: utf-8 -*-
"""只读侦察 v2：账号密码登录 + 课程/单元/课时字段 + 反作弊线索。

用法: python tools/live_recon2.py
"""
import json
import os
import re
import sys

import requests

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "src"))

BASE = "https://welearn.sflep.com"
AJAX_SCO = BASE + "/Ajax/SCO.aspx"
AJAX_AUTH = BASE + "/ajax/authCourse.aspx"
STUDYSTAT = BASE + "/ajax/StudyStat.aspx"


def hdr(referer=None, ajax=True):
    h = {
        "User-Agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                       "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"),
        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
        "Sec-Fetch-Site": "same-origin",
    }
    if ajax:
        h["Accept"] = "application/json, text/javascript, */*; q=0.01"
        h["X-Requested-With"] = "XMLHttpRequest"
        h["Sec-Fetch-Mode"] = "cors"
        h["Sec-Fetch-Dest"] = "empty"
    else:
        h["Accept"] = "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8"
        h["Sec-Fetch-Mode"] = "navigate"
        h["Sec-Fetch-Dest"] = "document"
    if referer:
        h["Referer"] = referer
    return h


def main():
    user = os.environ.get("WLEARN_USER", "")
    pwd = os.environ.get("WLEARN_PASS", "")
    if not user or not pwd:
        print("缺少 WLEARN_USER / WLEARN_PASS")
        return 1

    import welearn_gui as wg

    s = requests.Session()
    ok, res = wg.welearn_password_login(s, user, pwd)
    print("== 登录 ==", ok, (res if not ok else f"{len(res)} 门课程"))
    if not ok:
        return 1
    courses = res

    for c in courses[:10]:
        print("  ", c.get("cid"), c.get("per"), c.get("name"), "| keys", list(c.keys()))

    cid = str(courses[0]["cid"])
    uid, classid = wg.welearn_get_course_info(s, cid)
    print("\nuid", uid, "classid", classid, "cid", cid)

    r = s.get(BASE + f"/student/course_info.aspx?cid={cid}", headers=hdr(BASE + "/student/index.aspx", False), timeout=20)
    print("\n== 课程页反作弊关键词 ==")
    for k in ["visibilitychange", "blur", "防作弊", "离开", "切屏", "监控", "monitor",
              "无操作", "人脸", "face", "摄像头", "idle", "focus"]:
        n = r.text.lower().count(k.lower())
        if n:
            print(f"  {k}: {n}")

    units = wg.welearn_get_units(s, cid, uid)
    print("\n== 单元 ==", len(units))
    for i, u in enumerate(units[:8], 1):
        print("  ", i, u.get("unitname"), u.get("name"), u.get("visible"))

    print("\n== 课时样本字段 ==")
    sample = None
    for i in range(min(3, len(units))):
        leaves = wg.welearn_get_lessons(s, cid, uid, i, classid)
        if not leaves:
            print("   unit", i, "None")
            continue
        print(f"   unit {i}: {len(leaves)} 个")
        for c in leaves[:2]:
            print("     ", json.dumps(c, ensure_ascii=False)[:500])
            sample = sample or c

    if sample:
        print("\n== getscoinfo_v7（只读） ==")
        r = s.post(AJAX_SCO, data={"action": "getscoinfo_v7", "uid": uid, "cid": cid, "scoid": sample["id"]},
                   headers=hdr(BASE + "/student/StudyCourse.aspx"), timeout=20)
        print("  ", r.status_code, r.text[:800])

        print("\n== 学习页脚本 ==")
        r = s.get(BASE + f"/student/StudyCourse.aspx?cid={cid}&classid={classid}&sco={sample['id']}",
                  headers=hdr(None, False), timeout=20)
        srcs = re.findall(r'<script[^>]+src="([^"]+)"', r.text)
        print("   page_len", len(r.text), "scripts", len(srcs))
        for u in srcs[:20]:
            print("     ", u)
        for k in ["visibilitychange", "blur", "防作弊", "离开", "切屏", "无操作", "monitor", "track"]:
            n = r.text.lower().count(k.lower())
            if n:
                print(f"   关键词 {k}: {n}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
