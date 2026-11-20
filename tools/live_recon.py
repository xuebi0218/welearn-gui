# -*- coding: utf-8 -*-
"""只读侦察：验证 Cookie、枚举课程/单元/课时字段、抓取学习页反作弊线索。

用法: python tools/live_recon.py
不写入任何服务端数据（仅 GET / getscoinfo_v7 之类读取接口）。
"""
import json
import os
import re
import sys

import requests

COOKIE = os.environ.get("WLEARN_COOKIE", "").strip()
BASE = "https://welearn.sflep.com"
AJAX_SCO = BASE + "/Ajax/SCO.aspx"
AJAX_AUTH = BASE + "/ajax/authCourse.aspx"
STUDYSTAT = BASE + "/ajax/StudyStat.aspx"

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36")


def headers(referer=None):
    h = {
        "User-Agent": UA,
        "Accept": "application/json, text/javascript, */*; q=0.01",
        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
        "X-Requested-With": "XMLHttpRequest",
        "Sec-Fetch-Site": "same-origin",
        "Sec-Fetch-Mode": "cors",
        "Sec-Fetch-Dest": "empty",
    }
    if referer:
        h["Referer"] = referer
    return h


def main():
    if not COOKIE:
        print("缺少 WLEARN_COOKIE")
        return 1
    s = requests.Session()
    for item in COOKIE.split(";"):
        if "=" in item:
            k, v = item.split("=", 1)
            s.cookies[k.strip()] = v.strip()

    print("== 1. 课程列表 ==")
    r = s.get(AJAX_AUTH + "?action=gmc", headers=headers(BASE + "/student/index.aspx"), timeout=20)
    print("status", r.status_code, "len", len(r.text))
    try:
        data = r.json()
    except Exception:
        print(r.text[:400])
        return 1
    courses = data.get("clist") or []
    print("courses:", len(courses))
    for c in courses[:8]:
        print("  ", {k: c.get(k) for k in ("cid", "name", "per", "classid", "ocid")})

    if not courses:
        return 0

    cid = str(courses[0]["cid"])
    print("\n== 2. 课程详情 uid/classid ==")
    r = s.get(BASE + f"/student/course_info.aspx?cid={cid}",
              headers=headers(BASE + "/student/index.aspx"), timeout=20)
    uid_m = re.search(r'"uid":\s*(\d+)', r.text)
    class_m = re.search(r'"classid":"(.*?)"', r.text)
    uid = uid_m.group(1) if uid_m else ""
    classid = class_m.group(1) if class_m else ""
    print("uid", uid, "classid", classid, "html_len", len(r.text))

    print("\n== 3. 反作弊关键词（课程页） ==")
    keys = ["visibilitychange", "blur", "anti", "cheat", "防作弊", "离开", "切屏", "监控",
            "monitor", "focus", "idle", "无操作", "摄像头", "face", "人脸", "拍照"]
    for k in keys:
        n = r.text.lower().count(k.lower())
        if n:
            print(f"  {k}: {n}")

    print("\n== 4. 单元列表 ==")
    r = s.get(STUDYSTAT, params={"action": "courseunits", "cid": cid, "uid": uid},
              headers=headers(BASE + "/student/course_info.aspx"), timeout=20)
    units = r.json().get("info", []) if r.text.strip().startswith("{") else []
    print("units:", len(units))
    for i, u in enumerate(units[:6], 1):
        print("  ", i, {k: u.get(k) for k in ("unitname", "name", "visible")})

    print("\n== 5. 课时字段（前 3 个单元） ==")
    sample = None
    for i in range(min(3, len(units))):
        r = s.get(STUDYSTAT, params={"action": "scoLeaves", "cid": cid, "uid": uid,
                                     "unitidx": i, "classid": classid},
                  headers=headers(BASE + f"/student/course_info.aspx?cid={cid}"), timeout=20)
        if not r.text.strip().startswith("{"):
            print("   unit", i, "非 JSON:", r.text[:120])
            continue
        leaves = r.json().get("info", [])
        print(f"   unit {i}: {len(leaves)} 个")
        for c in leaves[:3]:
            print("     ", json.dumps(c, ensure_ascii=False)[:400])
            if sample is None:
                sample = c

    print("\n== 6. 单课时 getscoinfo_v7（只读） ==")
    if sample:
        r = s.post(AJAX_SCO, data={"action": "getscoinfo_v7", "uid": uid, "cid": cid,
                                   "scoid": sample["id"]},
                   headers=headers(BASE + "/student/StudyCourse.aspx"), timeout=20)
        print("   status", r.status_code, "body", r.text[:600])

    print("\n== 7. 学习页脚本清单 ==")
    if sample:
        r = s.get(BASE + f"/student/StudyCourse.aspx?cid={cid}&classid={classid}&sco={sample['id']}",
                  headers={"User-Agent": UA}, timeout=20)
        srcs = re.findall(r'<script[^>]+src="([^"]+)"', r.text)
        print("   page_len", len(r.text), "scripts", len(srcs))
        for u in srcs[:15]:
            print("     ", u)
        for k in ["visibilitychange", "blur", "防作弊", "离开", "切屏", "无操作", "monitor"]:
            n = r.text.lower().count(k.lower())
            if n:
                print(f"   关键词 {k}: {n}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
