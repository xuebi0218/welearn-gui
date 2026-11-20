# -*- coding: utf-8 -*-
"""v3.6 补丁 10：UA 会话级固定（去掉逐请求轮换指纹）+ 去重复函数。"""
import sys

P = "src/welearn_gui.py"
src = open(P, encoding="utf-8").read()


def rep(old, new, cnt=1):
    global src
    n = src.count(old)
    if n != cnt:
        print("MISMATCH(%d):" % n, old[:80].replace("\n", "\\n"))
        sys.exit(1)
    src = src.replace(old, new)


# 1) 删掉重复的 _rand_delay（第二处）
rep('''def _random_ua():
    """随机返回一个 User-Agent"""
    return random.choice(_UA_PROFILES)[0]


def _rand_delay(base_sec, jitter_pct=0.3):
    """在 base ± jitter_pct% 范围内随机延迟（秒）"""
    lo = base_sec * (1 - jitter_pct)
    hi = base_sec * (1 + jitter_pct)
    return lo + (hi - lo) * random.random()


def _build_headers(referer=None, extra=None, ajax=False):
    """构建与选中 UA 完全一致的请求头（含 CH 客户端提示）"""
    ua, ch_ua, ch_plat = random.choice(_UA_PROFILES)''',
    '''def _random_ua():
    """随机返回一个 User-Agent"""
    return random.choice(_UA_PROFILES)[0]


# 一次运行 = 一个浏览器身份：UA 必须会话级固定。
# 逐请求换 UA 是同一 Cookie 会话里最容易被识别的异常信号。
_SESSION_PROFILE = random.choice(_UA_PROFILES)


def _reset_ua_profile(session=None):
    """换账号/重新登录时换一个浏览器身份（同一个 session 内保持不变）。"""
    global _SESSION_PROFILE
    _SESSION_PROFILE = random.choice(_UA_PROFILES)
    try:
        if session is not None:
            session.headers['User-Agent'] = _SESSION_PROFILE[0]
    except Exception:
        pass


def _build_headers(referer=None, extra=None, ajax=False):
    """构建与当前会话 UA 完全一致的请求头（含 CH 客户端提示）"""
    ua, ch_ua, ch_plat = _SESSION_PROFILE''')

# 2) 登录时刷新身份
rep('''def thread_login(app):''',
    '''def thread_login(app):
    _reset_ua_profile(app.session)''')

open(P, "w", encoding="utf-8").write(src)
print("patch10 ok")
