# -*- coding: utf-8 -*-
"""v3.6 补丁 11：修正 thread_login 插入位置（docstring 位置）。"""
import sys

P = "src/welearn_gui.py"
src = open(P, encoding="utf-8").read()

old = '''def thread_login(app):
    _reset_ua_profile(app.session)
    """后台线程：根据登录模式执行 Cookie 或密码登录"""'''
new = '''def thread_login(app):
    """后台线程：根据登录模式执行 Cookie 或密码登录"""
    _reset_ua_profile(app.session)'''

if src.count(old) != 1:
    print("MISMATCH", src.count(old))
    sys.exit(1)
src = src.replace(old, new)
open(P, "w", encoding="utf-8").write(src)
print("patch11 ok")
