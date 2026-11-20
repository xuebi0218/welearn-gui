# -*- coding: utf-8 -*-
"""v3.6 补丁 1：解码统一 + 解析容错。"""
import sys

P = "src/welearn_gui.py"
src = open(P, encoding="utf-8").read()


def rep(old, new, cnt=1):
    global src
    n = src.count(old)
    if n != cnt:
        print("MISMATCH(%d):" % n, old[:70].replace("\n", "\\n"))
        sys.exit(1)
    src = src.replace(old, new)


rep(r'''    if '\"clist\":[]}' in resp.text or '错误' in resp.text:
        return False, "Cookie无效或已过期"

    try:
        courses = resp.json()["clist"]
    except ValueError as e:
        return False, f"服务器返回格式异常: {e}"

    return True, courses''',
    '''    body = _text(resp)
    if '"clist":[]}' in body or '错误' in body:
        return False, "Cookie 无效或已过期（请重新从浏览器复制一次）"

    try:
        courses = resp.json()["clist"]
    except ValueError as e:
        return False, f"服务器返回格式异常: {e}"

    return True, courses''')

rep("        if \"我的主页\" in resp.text or '/student/' in resp.url:",
    "        if \"我的主页\" in _text(resp) or '/student/' in resp.url:")

rep('''        if "我的主页" in resp.text:
            return _verify_login(session)''',
    '''        if "我的主页" in _text(resp):
            return _verify_login(session)''')

rep(r'''    if '\"clist\":[]}' in resp.text or '错误' in resp.text:
        return False, "登录成功但未找到课程"
    courses = resp.json()["clist"]
    return True, courses''',
    '''    body = _text(resp)
    if '"clist":[]}' in body or '错误' in body:
        return False, "登录成功，但该账号下没有课程"
    try:
        courses = resp.json()["clist"]
    except ValueError:
        return False, "课程列表解析失败，请重新登录"
    return True, courses''')

rep(r'''    uid_match = re.search(r'"uid":\s*(\d+)', resp.text)
    classid_match = re.search(r'"classid":"(.*?)"', resp.text)''',
    r'''    page = _text(resp)
    uid_match = re.search(r'"uid":\s*(\d+)', page)
    classid_match = re.search(r'"classid":"(.*?)"', page)''')

rep(r'''        raise ValueError(f"无法从课程页面提取uid/classid，页面结构可能已更新。\n页面前500字符:\n{resp.text[:500]}")''',
    r'''        raise ValueError(f"无法从课程页面提取 uid/classid（可能未选课或会话已失效）。\n页面: {page[:300]}")''')

rep('''                       headers=_build_headers('https://welearn.sflep.com/student/course_info.aspx'),
                       timeout=15)
    return resp.json()['info']''',
    '''                       headers=_build_headers('https://welearn.sflep.com/student/course_info.aspx',
                                              ajax=True),
                       timeout=20)
    try:
        return resp.json().get('info') or []
    except ValueError:
        raise ValueError(f"单元列表解析失败：{_text(resp)[:120]}")''')

rep('''                       headers=_build_headers(COURSE_INFO_URL + f"?cid={cid}"),
                       timeout=15)
    if "异常" in resp.text or "出错了" in resp.text:
        return None
    return resp.json()['info']''',
    '''                       headers=_build_headers(COURSE_INFO_URL + f"?cid={cid}", ajax=True),
                       timeout=20)
    body = _text(resp)
    if "异常" in body or "出错了" in body:
        return None
    try:
        return resp.json().get('info') or []
    except ValueError:
        return None''')

open(P, "w", encoding="utf-8").write(src)
print("patch1 ok")
