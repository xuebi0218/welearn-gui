# -*- coding: utf-8 -*-
"""
Welearn 刷课工具 GUI v3.5
整合刷课模式和刷时长模式，使用 CustomTkinter 构建界面。
v3.2: 新增题目解析和答题记录提交功能。
v3.3: 修复章节学习时长为0的bug，刷课模式支持多线程并发+真实学习时长。
v3.4: 修复刷时长模式心跳未触发导致时长不增长的bug。
v3.5: 修复最后一项卡住问题(join超时类型错误)、停止按钮即时响应(分段sleep+轮询join)、增强日志输出。
v3.8: 界面重绘——渐变横幅 + 立绘动效，配色统一为深海色系。
v3.7: 多路并行（每路独立 Session 各自真实计时，实测 4 路零损耗）+ 并发可调。
v3.6: 按平台协议重写核心——自适应补齐课时时长、边学边心跳、提交后回读校验、
      isPausing/checkNoCaptcha 闸门检测、危险参数拦截、界面立绘改为本地开源素材。
"""

import re
import sys
import json
import time
import queue
import random
import hashlib
import base64
import threading
import secrets
from html import unescape
from urllib.parse import urlparse, parse_qs

import requests
import customtkinter as ctk
from PIL import Image
from tkinter import messagebox

# ── 常量 ──────────────────────────────────────────────

def _rand_delay(base_sec, jitter_pct=0.3):
    """在 base ± jitter_pct% 范围内随机延迟（秒）"""
    lo = base_sec * (1 - jitter_pct)
    hi = base_sec * (1 + jitter_pct)
    return lo + (hi - lo) * random.random()


# 客户端提示与 UA 必须是同一套身份，否则 sec-ch-ua 与 UA 自相矛盾
# （旧版 Safari UA 配 Windows 的 sec-ch-ua，是明显的脚本指纹）
_UA_PROFILES = [
    ('Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36',
     '"Google Chrome";v="131", "Chromium";v="131", "Not_A Brand";v="24"', '"Windows"'),
    ('Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36',
     '"Google Chrome";v="130", "Chromium";v="130", "Not_A Brand";v="24"', '"Windows"'),
    ('Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/129.0.0.0 Safari/537.36 Edg/129.0.0.0',
     '"Microsoft Edge";v="129", "Chromium";v="129", "Not_A Brand";v="24"', '"Windows"'),
]


def _random_ua():
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
    ua, ch_ua, ch_plat = _SESSION_PROFILE
    chrome_like = 'Firefox' not in ua
    h = {
        'User-Agent': ua,
        'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
        'Accept-Encoding': 'gzip, deflate',
        'Cache-Control': 'max-age=0',
        'Sec-Fetch-Dest': 'document',
        'Sec-Fetch-Mode': 'navigate',
        'Sec-Fetch-Site': 'cross-site',
        'Sec-Fetch-User': '?1',
        'Upgrade-Insecure-Requests': '1',
        'Connection': 'keep-alive',
    }
    if ajax:
        h.update({
            'Accept': 'application/json, text/javascript, */*; q=0.01',
            'X-Requested-With': 'XMLHttpRequest',
            'Sec-Fetch-Dest': 'empty',
            'Sec-Fetch-Mode': 'cors',
        })
    else:
        h['Accept'] = ('text/html,application/xhtml+xml,application/xml;q=0.9,'
                       'image/avif,image/webp,image/apng,*/*;q=0.8')
    if chrome_like:
        h['sec-ch-ua'] = ch_ua
        h['sec-ch-ua-mobile'] = '?0'
        h['sec-ch-ua-platform'] = ch_plat
    if referer:
        h['Referer'] = referer
        h['Sec-Fetch-Site'] = 'same-origin'
    if extra:
        h.update(extra)
    return h


def _text(resp):
    """统一按 UTF-8 解码：welearn 多数响应没有 charset，requests 会退回 ISO-8859-1
    导致 '我的主页' / '错误' / '"clist":[]}' 这类判定全部失效。"""
    try:
        if not resp.encoding or resp.encoding.lower() in ('iso-8859-1', 'latin-1'):
            resp.encoding = 'utf-8'
        return resp.text
    except Exception:
        return ''


AJAX_SCO_URL = "https://welearn.sflep.com/Ajax/SCO.aspx"
AJAX_STUDYSTAT_URL = "https://welearn.sflep.com/ajax/StudyStat.aspx"
AJAX_AUTHCOURSE_URL = "https://welearn.sflep.com/ajax/authCourse.aspx"
COURSE_INFO_URL = "https://welearn.sflep.com/student/course_info.aspx"

# 图片资源路径（打包后从 exe 内部读取，源码运行从同目录读取）
import os as _os
_SRC_DIR = _os.path.dirname(_os.path.abspath(__file__))
if getattr(sys, 'frozen', False):
    _DONATE_QR_PATH = _os.path.join(sys._MEIPASS, 'src', 'donate_qr.jpg')
    _MASCOT_PATH = _os.path.join(sys._MEIPASS, 'src', 'mascot.png')
else:
    _DONATE_QR_PATH = _os.path.join(_SRC_DIR, 'donate_qr.jpg')
    _MASCOT_PATH = _os.path.join(_SRC_DIR, 'mascot.png')

_ANIM_FRAMES = [f"anim_{i}.png" for i in range(6)]


def _asset(name):
    """打包后从 _MEIPASS 取，开发时从 src/ 取。"""
    base = getattr(sys, '_MEIPASS', None)
    if base:
        return _os.path.join(base, 'src', name)
    return _os.path.join(_os.path.dirname(_os.path.abspath(__file__)), name)

# 用户配置（主题/语言/免责声明跳过等）
CONFIG_PATH = _os.path.join(_os.path.expanduser("~"), ".welearn_config.json")


# ── API 函数 ──────────────────────────────────────────
def parse_cookie_string(cookie_str):
    """
    解析 Cookie 字符串为字典。
    支持两种格式:
    1. 浏览器复制格式: name1=value1; name2=value2; ...
    2. JSON 数组格式 (EditThisCookie/Chrome导出): [{"name":..., "value":...}, ...]
    """
    s = cookie_str.strip()
    cookie = {}

    # ── 格式1: JSON 数组 ──
    if s.startswith('['):
        try:
            arr = json.loads(s)
            for c in arr:
                name = c.get('name', '')
                value = c.get('value', '')
                if name:
                    cookie[name] = value
            if cookie:
                return cookie
        except (json.JSONDecodeError, TypeError):
            pass  # 不是合法 JSON，继续按旧格式解析

    # ── 格式2: name=value; name=value ──
    for item in s.split(";"):
        item = item.strip()
        if item and '=' in item:
            k, v = item.split('=', 1)
            cookie[k.strip()] = v.strip()

    if not cookie:
        raise ValueError("空Cookie或格式不识别")
    return cookie


def welearn_validate_session(session, cookie_str):
    """
    设置 Cookie 到 session 并验证是否有效。
    返回 (success: bool, courses_or_error: list | str)
    """
    cookie = parse_cookie_string(cookie_str)
    for k, v in cookie.items():
        session.cookies[k] = v

    try:
        resp = session.get(AJAX_AUTHCOURSE_URL + "?action=gmc",
                          headers=_build_headers('https://welearn.sflep.com/student/index.aspx'),
                          timeout=15)
    except requests.exceptions.RequestException as e:
        return False, f"网络连接失败: {e}"

    body = _text(resp)
    if '"clist":[]}' in body or '错误' in body:
        return False, "Cookie 无效或已过期（请重新从浏览器复制一次）"

    try:
        courses = resp.json()["clist"]
    except ValueError as e:
        return False, f"服务器返回格式异常: {e}"

    return True, courses


def welearn_password_login(session, username, password):
    """
    使用账号密码登录 — 模拟真实浏览器 SSO 流程。
    IdentityServer4 + PKCE + SPA，全程 Follow 重定向 + 加载静态资源。
    返回 (success: bool, courses_or_error: list | str)
    """
    try:
        # ═══ 第1步：从 welearn 首页开始（模拟用户打开浏览器访问） ═══
        home_headers = _build_headers()
        home_headers['Sec-Fetch-Site'] = 'none'
        session.get('https://welearn.sflep.com/', headers=home_headers, timeout=15)

        # ═══ 第2步：点击登录按钮 → prelogin → 跟随完整 SSO 重定向链 ═══
        prelogin_url = ('https://welearn.sflep.com/user/prelogin.aspx'
                        '?loginret=http%3a%2f%2fwelearn.sflep.com%2fuser%2floginredirect.aspx')
        resp = session.get(prelogin_url,
                          headers=_build_headers('https://welearn.sflep.com/'),
                          allow_redirects=True, timeout=30)

        # 从重定向历史中提取 ReturnUrl 和 Account/Login 地址
        return_url = None
        login_page_url = None
        authorize_url = None
        for h in resp.history:
            loc = h.headers.get('Location', '')
            if 'ReturnUrl=' in loc:
                parsed = parse_qs(urlparse(loc).query)
                return_url = parsed.get('ReturnUrl', [None])[0]
            if '/Account/Login' in loc:
                login_page_url = loc if loc.startswith('http') else f'https://sso.sflep.com{loc}'
            if '/connect/authorize' in loc:
                authorize_url = loc if loc.startswith('http') else f'https://sso.sflep.com{loc}'

        if not return_url or not login_page_url:
            return False, "SSO登录流程已变更，请改用Cookie登录"

        # ═══ 第3步：加载 SSO 登录页面 + 静态资源（模拟浏览器渲染） ═══
        sso_origin = 'https://sso.sflep.com'
        sso_headers = _build_headers(authorize_url or prelogin_url)
        sso_headers['Sec-Fetch-Site'] = 'cross-site'  # welearn → sso 是跨站
        session.get(login_page_url, headers=sso_headers, timeout=15)

        # 拉取 SSO 页面引用的 JS 资源（像浏览器一样加载）
        for js_path in ['/idsvr/assets/js/baseurl.js',
                        '/idsvr/assets/js/browser.min.js']:
            try:
                js_headers = _build_headers(login_page_url)
                js_headers.update({
                    'Accept': '*/*',
                    'Sec-Fetch-Dest': 'script',
                    'Sec-Fetch-Mode': 'no-cors',
                    'Sec-Fetch-Site': 'same-origin',
                })
                session.get(f'{sso_origin}{js_path}', headers=js_headers, timeout=10)
            except Exception:
                pass  # 资源加载失败不影响登录

        # ═══ 第4步：模拟用户输入延迟（真实人类不会瞬间填表） ═══
        time.sleep(_rand_delay(2.0, 0.5))  # 2秒 ± 50%

        # ═══ 第5步：提交登录表单 ═══
        data = {
            'ReturnUrl': return_url,
            'Account': username,
            'pwd': password,
            'RememberMe': 'false',
        }
        post_headers = _build_headers(login_page_url)
        post_headers.update({
            'Content-Type': 'application/x-www-form-urlencoded',
            'Origin': sso_origin,
            'Sec-Fetch-Site': 'same-origin',
        })
        resp = session.post(login_page_url, data=data,
                          headers=post_headers,
                          allow_redirects=True, timeout=30)

        # ═══ 第6步：验证登录结果 ═══
        if "我的主页" in _text(resp) or '/student/' in resp.url:
            return _verify_login(session)

        # 检查是否登录失败还留在 SSO
        if 'sso.sflep.com' in resp.url and 'Account/Login' in resp.url:
            return False, "账号或密码错误，请重试"

        # 兜底验证
        resp = session.get('https://welearn.sflep.com/student/index.aspx',
                          headers=_build_headers(sso_origin), timeout=15)
        if "我的主页" in _text(resp):
            return _verify_login(session)

        return False, "登录失败，请检查账号密码或改用Cookie登录"

    except requests.exceptions.RequestException as e:
        return False, f"网络连接失败: {e}"
    except (ValueError, KeyError) as e:
        return False, f"服务器返回格式异常: {e}"


def _verify_login(session):
    """验证登录状态并返回课程列表"""
    resp = session.get(AJAX_AUTHCOURSE_URL + "?action=gmc",
                      headers=_build_headers('https://welearn.sflep.com/student/index.aspx'),
                      timeout=15)
    body = _text(resp)
    if '"clist":[]}' in body or '错误' in body:
        return False, "登录成功，但该账号下没有课程"
    try:
        courses = resp.json()["clist"]
    except ValueError:
        return False, "课程列表解析失败，请重新登录"
    return True, courses


def welearn_get_course_info(session, cid):
    """
    从课程详情页提取 uid 和 classid。
    返回 (uid: str, classid: str)，失败抛出 ValueError。
    """
    resp = session.get(COURSE_INFO_URL + f"?cid={cid}",
                      headers=_build_headers('https://welearn.sflep.com/student/index.aspx'),
                      timeout=15)

    page = _text(resp)
    uid_match = re.search(r'"uid":\s*(\d+)', page)
    classid_match = re.search(r'"classid":"(.*?)"', page)
    if not uid_match or not classid_match:
        raise ValueError(f"无法从课程页面提取 uid/classid（可能未选课或会话已失效）。\n页面: {page[:300]}")
    return uid_match.group(1), classid_match.group(1)


def welearn_get_units(session, cid, uid):
    """
    获取课程的单元列表。
    返回 [{"unitname":..., "name":..., "visible":...}, ...]
    """
    resp = session.get(AJAX_STUDYSTAT_URL,
                       params={'action': 'courseunits', 'cid': cid, 'uid': uid},
                       headers=_build_headers('https://welearn.sflep.com/student/course_info.aspx',
                                              ajax=True),
                       timeout=20)
    try:
        return resp.json().get('info') or []
    except ValueError:
        raise ValueError(f"单元列表解析失败：{_text(resp)[:120]}")


def welearn_get_lessons(session, cid, uid, unitidx, classid):
    """
    获取某单元下的小节列表（scoLeaves）。
    返回 [{"id":..., "location":..., "isvisible":..., "iscomplete":..., "learntime":...}, ...]
    """
    resp = session.get(AJAX_STUDYSTAT_URL,
                       params={'action': 'scoLeaves', 'cid': cid, 'uid': uid,
                               'unitidx': unitidx, 'classid': classid},
                       headers=_build_headers(COURSE_INFO_URL + f"?cid={cid}", ajax=True),
                       timeout=20)
    body = _text(resp)
    if "异常" in body or "出错了" in body:
        return None
    try:
        return resp.json().get('info') or []
    except ValueError:
        return None



# ── 时长策略 ─────────────────────────────────────────
# 平台每个课时都带 timelitsec（要求学习的秒数，实测常见 1080s = 18min），
# 并回传 useSeconds（该课时已累计的有效时长）。脚本按"缺口"补齐，而不是固定 60~120s，
# 这样既不会因为"90 秒干完 18 分钟的活"被时钟流速校验命中，也不浪费多余时间。
HEARTBEAT_MIN = 20      # 心跳间隔下限（秒），平台硬上限 60s
HEARTBEAT_MAX = 32      # 心跳间隔上限（秒）
DURATION_CAP = 1800     # 单课时最多等待（秒），平台单页上限 30min
# 注：实际目标还会被 startsco 返回的 timelitsec 截断（达标即停表），所以这里只是保险上限，留余量


def _last_json(body):
    """响应可能形如 {"ret":-1}{"ret":0,"timelitsec":1080,...}（两段拼接），
    取最后一段可解析的 JSON 对象；解析失败返回 {}。"""
    body = (body or "").strip()
    idx = body.rfind('{"ret"')
    if idx < 0:
        idx = body.find("{")
    if idx < 0:
        return {}
    try:
        return json.loads(body[idx:])
    except ValueError:
        return {}


def _as_bool(v):
    """服务端布尔值可能是 true / "true" / 1 / "1" / "false" 字符串。"""
    if isinstance(v, bool):
        return v
    if isinstance(v, (int, float)):
        return v == 1
    return str(v).strip().lower() in ("true", "1", "yes")


def _clamp(v, lo, hi):
    return max(lo, min(hi, v))


def _parse_hms(txt):
    """'00:08:37' -> 517；无法解析返回 None"""
    m = re.match(r"^\s*(\d+):(\d{1,2}):(\d{1,2})\s*$", str(txt or ""))
    if not m:
        return None
    return int(m.group(1)) * 3600 + int(m.group(2)) * 60 + int(m.group(3))


def welearn_sco_requirements(session, cid, uid, classid, scoid, referer=None):
    """startsco160928 的响应会给出该课时的要求时长与已累计时长。
    返回 {"ok":bool, "timelitsec":int, "use_seconds":int, "review":bool, "error":str}
    """
    referer = referer or (f"https://welearn.sflep.com/Student/StudyCourse.aspx"
                          f"?cid={cid}&classid={classid}&sco={scoid}")
    out = {"ok": False, "timelitsec": 0, "use_seconds": 0, "review": False, "error": ""}
    try:
        resp = session.post(AJAX_SCO_URL,
                            data={"action": "startsco160928", "cid": cid, "scoid": scoid,
                                  "uid": uid, "classid": classid, "tid": -1,
                                  "nocache": random.random()},
                            headers=_build_headers(referer), timeout=20)
        js = _last_json(_text(resp))
        out["ok"] = js.get("ret") == 0
        out["timelitsec"] = int(js.get("timelitsec") or 0)
        out["use_seconds"] = int(js.get("useSeconds") or 0)
        out["review"] = (js.get("enableview") == "true")
    except Exception as e:
        out["error"] = str(e)
    return out


def welearn_verify_learntime(session, cid, uid, classid, unitidx, scoid):
    """提交后回读服务端真值：返回该课时累计学习秒数（失败返回 None）。

    以 startsco160928 的 useSeconds 为准——课时列表里的 learntime 有明显延迟，
    实测刚提交完仍是旧值，用它判断会误报。
    """
    try:
        req = welearn_sco_requirements(session, cid, uid, classid, scoid)
        if req.get("ok"):
            return req["use_seconds"]
    except Exception:
        pass
    try:
        lessons = welearn_get_lessons(session, cid, uid, unitidx, classid) or []
        for c in lessons:
            if str(c.get("id")) == str(scoid):
                return _parse_hms(c.get("learntime"))
    except Exception:
        pass
    return None


def welearn_curriculum_submit(session, cid, uid, classid, scoid, crate, learntime=0,
                              stop_check=None, unitidx=0, adaptive=True,
                              duration_cap=DURATION_CAP):
    """
    刷课模式：完成一个小节。
    流程：解析题目 → startsco160928（读 timelitsec/useSeconds）→ 边等边心跳 → setscoinfo
          → savescoinfo160928 → 回读 learntime 校验

    learntime: 用户设定的课时时长下限（秒）；adaptive=True 时按 timelitsec 缺口自动补齐。
    返回 dict：
      {"way1":bool,"way2":bool,"questions":int,"target":int,"timelitsec":int,
       "verified":int|None,"stopped":bool,"note":str}
    """
    referer = (f"https://welearn.sflep.com/Student/StudyCourse.aspx"
               f"?cid={cid}&classid={classid}&sco={scoid}")
    result = {"way1": False, "way2": False, "questions": 0, "target": int(learntime or 0),
              "timelitsec": 0, "verified": None, "stopped": False, "note": "",
              "reached": False}

    # ── 0. 解析课件题目（失败不阻塞）──
    questions = []
    try:
        template_url, _err = welearn_get_sco_addr(session, cid, scoid)
        if template_url:
            html = _fetch_sco_template(session, template_url)
            if html:
                questions = parse_sco_questions(html)
    except Exception:
        pass
    result["questions"] = len(questions)

    try:
        crate_int = _clamp(int(str(crate).strip()), 0, 100)
    except (TypeError, ValueError):
        crate_int = 88

    if questions:
        interactions_json, interactions_info = generate_interactions(questions, crate_int)
    else:
        interactions_json, interactions_info = [], ""

    # ── 1. 读取平台要求时长，按缺口自适应 ──
    req = welearn_sco_requirements(session, cid, uid, classid, scoid, referer)
    result["timelitsec"] = req["timelitsec"]
    target = max(int(learntime or 0), 0)
    if adaptive and req["timelitsec"] > 0:
        deficit = max(0, req["timelitsec"] - req["use_seconds"])
        if deficit > target:
            target = deficit
    target = _clamp(target, 0, duration_cap if duration_cap else DURATION_CAP)
    result["target"] = target

    # ── 2. 等时长 + 心跳（官方 60s 一次，这里 20~32s 更稳；达标即停表）──
    base_total = req["use_seconds"]
    timer_target = req["timelitsec"] or 0
    elapsed = 0.0
    next_hb = random.randint(HEARTBEAT_MIN, HEARTBEAT_MAX)
    reached = timer_target > 0 and base_total >= timer_target
    while elapsed < target and not reached:
        if stop_check and stop_check():
            result["stopped"] = True
            result["note"] = "用户停止"
            break
        step = min(1.0, target - elapsed)
        time.sleep(step * random.uniform(0.92, 1.08))
        elapsed += step
        if timer_target and base_total + elapsed >= timer_target:
            reached = True
        if elapsed >= next_hb or reached:
            welearn_time_heartbeat(session, cid, uid, scoid,
                                   str(int(elapsed)), str(base_total + int(elapsed)),
                                   timelitsec=timer_target,
                                   endcaltime="true" if reached else "false")
            next_hb = elapsed + random.randint(HEARTBEAT_MIN, HEARTBEAT_MAX)

    if stop_check and stop_check():
        result["stopped"] = True
        result["note"] = "用户停止"

    # 结束时补一次心跳，把最后一段时长落库（停止时也要落库，已学的时间不能白等）
    final_reached = bool(timer_target) and (base_total + elapsed) >= timer_target * 0.99
    welearn_time_heartbeat(session, cid, uid, scoid,
                           str(int(elapsed)), str(base_total + int(elapsed)),
                           timelitsec=timer_target,
                           endcaltime="true" if final_reached else "false")

    # ── 3. 提交 SCORM 数据 ──
    # 严格模式：时长没学满就不谎报 completed。
    # 平台风控看的是「完成得比要求快多少」，秒完成的 completed 是典型脚本特征。
    learned_total = base_total + int(elapsed)
    if timer_target:
        reached_final = learned_total >= timer_target * 0.95
        progress_val = min(1.0, learned_total / float(timer_target))
    else:
        reached_final = target == 0 or elapsed >= target * 0.95
        progress_val = 1.0 if reached_final else 0.5
    result["reached"] = reached_final

    cstatus_val = "completed" if reached_final else "incomplete"
    progress_str = f"{progress_val:.2f}"
    now_utc = time.strftime("%Y-%m-%dT%H:%M:%S", time.gmtime())
    data_obj = {
        "cmi": {
            "completion_status": cstatus_val,
            "interactions": interactions_json,
            "launch_data": "",
            "location": "",
            "exit": "",
            "progress_measure": progress_str,
            "score": {"scaled": str(crate_int), "raw": str(crate_int), "min": "0", "max": "100"},
            "session_time": str(int(elapsed)),
            "success_status": "unknown",
            "total_time": str(learned_total),
            "mode": "normal",
            "timestamp": now_utc,
        },
        "adl": {"data": []},
        "cci": {
            "data": [],
            "service": {
                "dictionary": {"headword": "", "short_cuts": ""},
                "new_words": [],
                "notes": [],
                "writing_marking": [],
                "record": {"files": []},
                "play": {"offline_media_id": ""},
            },
            "retry_count": "0",
            "submit_time": now_utc,
        },
    }
    full_data = json.dumps(data_obj, ensure_ascii=False)
    if interactions_info:
        full_data += '[INTERACTIONINFO]' + interactions_info

    resp1 = session.post(AJAX_SCO_URL,
                         data={"action": "setscoinfo", "cid": cid, "scoid": scoid,
                               "uid": uid, "data": full_data, "isend": "False"},
                         headers=_build_headers(referer), timeout=20)
    result["way1"] = '"ret":0' in _text(resp1)

    time.sleep(_rand_delay(0.3, 0.5))

    resp2 = session.post(AJAX_SCO_URL,
                         data={"action": "savescoinfo160928", "cid": cid, "scoid": scoid,
                               "uid": uid,
                               "progress": str(int(round(progress_val * 100))),
                               "crate": str(crate_int),
                               "status": "unknown", "cstatus": cstatus_val, "trycount": "0",
                               "session_time": str(int(elapsed)),
                               "total_time": str(learned_total),
                               "endcaltime": "true" if reached_final else "false",
                               "nocache": random.random()},
                         headers=_build_headers(referer), timeout=20)
    result["way2"] = '"ret":0' in _text(resp2)

    # ── 4. 回读校验：平台是否真的把时长记上了（入账有几秒延迟，补一次）──
    result["verified"] = welearn_verify_learntime(session, cid, uid, classid, unitidx, scoid)
    if timer_target and (result["verified"] or 0) < min(timer_target, base_total + int(elapsed)):
        time.sleep(3)
        again = welearn_verify_learntime(session, cid, uid, classid, unitidx, scoid)
        if again is not None and again > (result["verified"] or 0):
            result["verified"] = again
    return result


def welearn_time_init(session, cid, uid, scoid):
    """
    刷时长模式：初始化学习数据（获取当前 CMi 状态）。
    返回 {"cstatus":..., "progress":..., "session_time":..., "total_time":..., "crate":...}
    """
    ref = 'https://welearn.sflep.com/student/StudyCourse.aspx'

    resp = session.post(AJAX_SCO_URL,
                        data={'action': 'getscoinfo_v7', 'uid': uid, 'cid': cid, 'scoid': scoid},
                        headers=_build_headers(ref), timeout=15)

    if '学习数据不正确' in resp.text:
        session.post(AJAX_SCO_URL,
                     data={'action': 'startsco160928', 'uid': uid, 'cid': cid, 'scoid': scoid},
                     headers=_build_headers(ref), timeout=15)
        resp = session.post(AJAX_SCO_URL,
                            data={'action': 'getscoinfo_v7', 'uid': uid, 'cid': cid, 'scoid': scoid},
                            headers=_build_headers(ref), timeout=15)
        if '学习数据不正确' in resp.text:
            return None

    back = json.loads(resp.text)['comment']
    if 'cmi' in back:
        cmi = json.loads(back)['cmi']
        return {
            'cstatus': cmi.get('completion_status', 'not_attempted'),
            'progress': cmi.get('progress_measure', '0'),
            'session_time': cmi.get('session_time', '0'),
            'total_time': cmi.get('total_time', '0'),
            'crate': cmi.get('score', {}).get('scaled', ''),
        }
    return {'cstatus': 'not_attempted', 'progress': '0',
            'session_time': '0', 'total_time': '0', 'crate': ''}



def welearn_check_gates(session, uid, cid=None):
    """平台的两道显式闸门（都是服务端判定，绕过不了）：
      isPausing       —— 判定"刷课行为"后锁定 N 分钟 / 今日锁定
      checkNoCaptcha  —— status==0 时强制滑块验证
    返回 (blocked: bool, message: str)
    """
    ref = 'https://welearn.sflep.com/student/StudyCourse.aspx'
    try:
        r = session.post(AJAX_SCO_URL,
                         data={"action": "isPausing", "uid": uid,
                               "nocache": random.random()},
                         headers=_build_headers(ref), timeout=15)
        js = _last_json(_text(r))
        if _as_bool(js.get("isPausing")):
            mins = js.get("pausingMinute") or 0
            if mins:
                return True, (f"平台判定存在刷课行为，已锁定 {mins} 分钟。"
                              f"请先停下，过 ${mins} 分钟后再继续，否则有清空记录的风险。").replace("$", "")
            return True, "平台已锁定今日刷课（pausingMinute=0），请明天再试。"
    except Exception:
        pass

    try:
        r = session.post(AJAX_SCO_URL,
                         data={"action": "checkNoCaptcha", "uid": uid,
                               "nocache": random.random()},
                         headers=_build_headers(ref), timeout=15)
        js = _last_json(_text(r))
        if js.get("status") == 0:
            return True, ("平台要求滑块验证（checkNoCaptcha）。脚本无法自动通过："
                          "请用浏览器打开 welearn 手动拖一次滑块，再回来继续。")
    except Exception:
        pass

    return False, ""


def welearn_heartbeat_full(session, cid, uid, scoid, session_time, total_time,
                           timelitsec=0, endcaltime="false"):
    """心跳详情版：返回 {"ok","seconds","ticket","endcaltime"}。
    seconds 是服务端授予的权威增量（ret==0 才会有），ret==1 表示计时被复位。
    """
    out = {"ok": False, "seconds": 0, "ticket": "", "endcaltime": False}
    try:
        resp = session.post(AJAX_SCO_URL,
                            data={'action': 'keepsco_with_getticket_with_updatecmitime',
                                  'uid': uid, 'cid': cid, 'scoid': scoid,
                                  'session_time': session_time, 'total_time': total_time,
                                  'timelitsec': timelitsec, 'timelimitsec': timelitsec,
                                  'endcaltime': endcaltime,
                                  'nocache': random.random()},
                            headers=_build_headers('https://welearn.sflep.com/student/StudyCourse.aspx'),
                            timeout=20)
        js = _last_json(_text(resp))
        out["ok"] = (js.get("ret") == 0)
        out["seconds"] = int(js.get("seconds") or 0)
        out["ticket"] = js.get("ticket") or ""
        out["endcaltime"] = _as_bool(js.get("endcaltime"))
    except Exception:
        pass
    return out


def welearn_time_heartbeat(session, cid, uid, scoid, session_time, total_time,
                           timelitsec=0, endcaltime="false"):
    """刷时长模式：发送心跳包保持在线（薄封装，返回是否成功）"""
    return welearn_heartbeat_full(session, cid, uid, scoid, session_time, total_time,
                                  timelitsec=timelitsec, endcaltime=endcaltime)["ok"]


def welearn_time_finalize(session, cid, uid, scoid, progress, crate, cstatus,
                          session_time, total_time, endcaltime="true"):
    """刷时长模式：保存最终学习数据（含累加后的学习时间）"""
    resp = session.post(AJAX_SCO_URL,
                        data={'action': 'savescoinfo160928', 'cid': cid, 'scoid': scoid,
                              'uid': uid, 'progress': progress, 'crate': crate,
                              'status': 'unknown', 'cstatus': cstatus, 'trycount': '0',
                              'session_time': session_time, 'total_time': total_time,
                              'endcaltime': endcaltime, 'nocache': random.random()},
                        headers=_build_headers('https://welearn.sflep.com/student/StudyCourse.aspx'),
                        timeout=15)
    return '"ret":0' in resp.text


# ── 题目解析 & Interactions 生成 ─────────────────────

def _js_escape(s):
    """模拟 JavaScript 的 escape() 函数（用于 interactionsInfo 编码）"""
    result = []
    for ch in s:
        code = ord(ch)
        if (48 <= code <= 57) or (65 <= code <= 90) or (97 <= code <= 122) or \
           ch in '@*-_+./':
            result.append(ch)
        elif code < 256:
            result.append(f'%{code:02X}')
        else:
            result.append(f'%u{code:04X}')
    return ''.join(result)


def welearn_get_sco_addr(session, cid, scoid):
    """
    获取 SCO 内容的模板 URL。
    返回 (template_url: str|None, error: str|None)
    """
    try:
        ref = f"https://welearn.sflep.com/Student/StudyCourse.aspx?cid={cid}&sco={scoid}"
        resp = session.post(AJAX_SCO_URL,
                            data={'action': 'scoAddr', 'cid': cid, 'scoid': scoid},
                            headers=_build_headers(ref), timeout=15)
        data = resp.json()
        if data.get('ret') != 0 or 'addr' not in data:
            return None, f"scoAddr 返回异常: {resp.text[:200]}"

        addr_full = data['addr']
        sco_url = 'https:' + addr_full.split('|')[0]

        # 从 hash 路由解析 unit/file: #/2/4-3 → unit=2, file=4-3
        match = re.search(r'#/(\d+)/([\d\-]+)', sco_url)
        if not match:
            return None, f"无法解析 SCO URL: {sco_url}"

        unit = int(match.group(1))
        file = match.group(2)
        base_path = sco_url.split('#')[0].rsplit('/', 1)[0]
        template_url = f"{base_path}/data/{unit}/{file}.html"
        return template_url, None
    except Exception as e:
        return None, str(e)


def _fetch_sco_template(session, template_url):
    """抓取 SCO HTML 模板（使用已认证 session）"""
    try:
        resp = session.get(template_url,
                           headers=_build_headers(),
                           timeout=15)
        if resp.status_code != 200:
            return None
        return resp.text
    except Exception:
        return None


def parse_sco_questions(html):
    """
    从 SCO HTML 模板解析题目和正确答案。
    支持题型: <et-blank g> (填空), <et-tof key> (判断), <et-choice key> (选择)
    返回 list[dict]: 每道题 {type, answer, text?}
    """
    questions = []

    # ── 填空: <et-blank g>答案</et-blank> ──
    for m in re.finditer(r'<et-blank\s+g>(.*?)</et-blank>', html, re.DOTALL):
        answer = m.group(1).strip()
        answer = re.sub(r'<[^>]+>', '', answer)
        answer = unescape(answer).strip()
        if answer:
            questions.append({'type': 'blank', 'answer': answer})

    # ── 判断: <et-tof key="t|f"> ──
    for m in re.finditer(r'<et-tof\s+key="([tf])"', html, re.DOTALL):
        questions.append({'type': 'tof', 'answer': m.group(1)})

    # ── 选择: <et-choice key="..."> ──
    for m in re.finditer(r'<et-choice[^>]*key="([^"]*)"', html, re.DOTALL):
        questions.append({'type': 'choice', 'answer': m.group(1)})

    return questions


def generate_interactions(questions, crate):
    """
    根据题目列表和正确率生成:
    - interactions_json: SCORM cmi.interactions 数组
    - interactions_info: [INTERACTIONINFO] 后面的字符串
    """
    interactions_json = []
    interactions_info_parts = []

    for i, q in enumerate(questions):
        is_correct = random.random() * 100 < crate

        if q['type'] == 'blank':
            learner_response = q['answer'] if is_correct else 'wrong_answer_' + str(i)
            result = 'correct' if is_correct else 'wrong'
        elif q['type'] == 'tof':
            learner_response = q['answer'] if is_correct else ('f' if q['answer'] == 't' else 't')
            result = 'correct' if is_correct else 'wrong'
        elif q['type'] == 'choice':
            learner_response = q['answer'] if is_correct else (
                'B' if q['answer'] == 'A' else 'A')
            result = 'correct' if is_correct else 'wrong'
        else:
            continue

        # SCORM interactions 对象
        scorm_obj = {
            'id': f'interaction_{i}',
            'type': q['type'],
            'student_response': learner_response,
            'result': result,
            'weighting': '1',
        }
        if is_correct:
            scorm_obj['correct_responses'] = [{'pattern': q['answer']}]
        interactions_json.append(scorm_obj)

        # interactionsInfo 单项
        interactions_info_parts.append(
            f'{i}[]false[]false[]'
            f'{_js_escape(learner_response)}[]'
            f'{result}'
        )

    interactions_info = '$$'.join(interactions_info_parts)
    return interactions_json, interactions_info


# ── 工作线程 ──────────────────────────────────────────
def thread_login(app):
    """后台线程：根据登录模式执行 Cookie 或密码登录"""
    _reset_ua_profile(app.session)
    try:
        if app.login_mode == "cookie":
            app.message_queue.put({"type": "log", "text": "正在验证Cookie..."})
            success, result = welearn_validate_session(app.session, app.login_cookie)
        else:
            app.message_queue.put({"type": "log", "text": "正在使用账号密码登录..."})
            success, result = welearn_password_login(app.session, app.login_username, app.login_password)
        if success:
            app.message_queue.put({"type": "login_success", "courses": result})
        else:
            app.message_queue.put({"type": "login_fail", "error": result})
    except Exception as e:
        app.message_queue.put({"type": "login_fail", "error": f"登录异常: {e}"})


def thread_refresh_courses(app):
    """后台线程：仅刷新课程列表（已登录状态下），不走登录流程"""
    try:
        app.message_queue.put({"type": "log", "text": "正在刷新课程列表..."})
        resp = app.session.get(AJAX_AUTHCOURSE_URL + "?action=gmc",
                               headers=_build_headers('https://welearn.sflep.com/student/index.aspx'),
                               timeout=15)
        body = _text(resp)
        if '"clist":[]}' in body or '错误' in body:
            app.message_queue.put({"type": "refresh_fail", "error": "会话已过期，请重新登录"})
            return
        courses = resp.json()["clist"]
        app.message_queue.put({"type": "login_success", "courses": courses})
    except Exception as e:
        app.message_queue.put({"type": "refresh_fail", "error": str(e)})


def thread_fetch_units(app, cid):
    """后台线程：获取课程的 uid/classid 和单元列表"""
    try:
        app.message_queue.put({"type": "log", "text": "获取单元信息中..."})
        uid, classid = welearn_get_course_info(app.session, cid)
        units = welearn_get_units(app.session, cid, uid)
        app.message_queue.put({"type": "units_loaded", "uid": uid, "classid": classid, "units": units})
    except Exception as e:
        app.message_queue.put({"type": "log_error", "text": f"获取单元失败: {e}"})



def _collect_lessons(app, only_unfinished):
    """收集课时列表；返回 ([(unit_i, course), ...], error)"""
    cid, uid, classid = app.selected_cid, app.uid, app.classid
    unitidx = app.selected_unit_idx
    unit_count = len(getattr(app, "units", []) or [])
    if unitidx == 0:
        unit_start, unit_end = 0, (unit_count or 20)
    else:
        unit_start, unit_end = unitidx - 1, unitidx
    out = []
    failed_units = []
    for i in range(unit_start, unit_end):
        if app.stop_requested:
            break
        lessons = welearn_get_lessons(app.session, cid, uid, i, classid)
        if lessons is None:
            failed_units.append(i)
            continue
        for c in lessons:
            visible = str(c.get('isvisible', 'true')).lower() != 'false'
            done = ("已" in c.get('iscomplete', '')) and ("未" not in c.get('iscomplete', ''))
            if not visible:
                continue
            if only_unfinished and done:
                continue
            out.append((i, c))
    err = ("部分单元课时读取失败：%s（会话可能已过期）" % failed_units) if failed_units else None
    return out, err


def thread_curriculum_execute(app):
    """后台线程：刷课（v3.6：单并发 + 缺口自适应 + 心跳 + 回读校验）"""
    try:
        _curriculum_worker(app)
    except Exception as e:
        app.message_queue.put({"type": "log_error", "text": f"✗ 任务异常终止：{e}"})
        app.message_queue.put({"type": "curriculum_complete", "way1_ok": 0, "way1_fail": 0,
                               "way2_ok": 0, "way2_fail": 0, "stopped": app.stop_requested})
    finally:
        app.message_queue.put({"type": "task_finished"})


def _curriculum_worker(app):
    cid, uid, classid = app.selected_cid, app.uid, app.classid
    mycrate = app.curriculum_rate
    randommode = app.curriculum_random
    duration = app.curriculum_duration
    random_duration = isinstance(duration, list)
    max_threads = _clamp(int(getattr(app, 'curriculum_max_threads', 4) or 4), 1, 8)

    stats_lock = threading.Lock()
    counters = {"way1_ok": 0, "way1_fail": 0, "way2_ok": 0, "way2_fail": 0}

    all_lessons, err = _collect_lessons(app, only_unfinished=True)
    total = len(all_lessons)
    app.message_queue.put({"type": "progress", "current": 0, "total": total})

    if err:
        app.message_queue.put({"type": "log_error", "text": f"✗ {err}"})
    if total == 0:
        app.message_queue.put({"type": "log", "text": "没有需要完成的小节。"})
        app.message_queue.put({"type": "curriculum_complete", "way1_ok": 0, "way1_fail": 0,
                               "way2_ok": 0, "way2_fail": 0, "stopped": False})
        return

    dur_label = f"{duration[0]}~{duration[1]}s（自动补齐不足部分）" if random_duration \
        else f"{duration}s（自动补齐不足部分）"
    app.message_queue.put({"type": "log_warning",
                           "text": f"📝 待完成 {total} 个小节 | 基准时长 {dur_label} | 并发 {max_threads}"})
    app.message_queue.put({"type": "log",
                           "text": "ℹ️ 每个小节的时长按平台要求（timelitsec）自动补齐，实际耗时取决于课件要求。"})

    # 单日上限：只处理前面 N 个（其余留到下次）
    daily_cap = int(getattr(app, 'daily_lesson_cap', 24) or 24)
    if total > daily_cap:
        app.message_queue.put({"type": "log_warning",
                               "text": f"⚠ 本次只处理前 {daily_cap} 个（单日上限），其余请明天再跑，"
                                       f"避免短时间内集中完成被平台复核。"})
        all_lessons = all_lessons[:daily_cap]
        total = len(all_lessons)

    processed = [0]
    cooldown_every = int(getattr(app, 'cooldown_every', 4) or 0)
    cooldown_range = getattr(app, 'cooldown_range', (400, 900))

    def process_one(unit_i, course, lane_id=0, session=None):
        if app.stop_requested:
            return
        session = session or app.session
        tag_pre = f"[L{lane_id + 1}] "
        loc = course.get("location", "?")
        scoid = course.get("id")
        try:
            blocked, why = welearn_check_gates(session, uid, cid)
            if blocked:
                app.message_queue.put({"type": "log_error", "text": f"🛑 {why}"})
                app.stop_requested = True
                return
            crate = random.randint(mycrate[0], mycrate[1]) if randommode else int(mycrate)
            dur = random.randint(duration[0], duration[1]) if random_duration else int(duration)
            app.message_queue.put({"type": "log",
                                   "text": f'{tag_pre}[刷课] {loc} → 正确率 {crate}%，至少学 {dur}s'})
            r = welearn_curriculum_submit(session, cid, uid, classid, scoid, crate,
                                          learntime=dur, stop_check=lambda: app.stop_requested,
                                          unitidx=unit_i)
            if r["stopped"]:
                app.message_queue.put({"type": "log_warning",
                                       "text": f'  ⏹ {loc} 已停止（已学 {r["target"]}s 已落库）'})
                return
            with stats_lock:
                counters["way1_ok" if r["way1"] else "way1_fail"] += 1
                counters["way2_ok" if r["way2"] else "way2_fail"] += 1

            detail = f'目标{r["target"]}s'
            if r["timelitsec"]:
                detail += f' / 平台要求{r["timelitsec"]}s'
            if r["verified"] is not None:
                detail += f' / 回读{r["verified"]}s'
            tag = "log_success" if (r["way1"] and r["way2"]) else "log_error"
            ok_txt = "答题记录✓" if r["way1"] else "答题记录✗"
            sv_txt = "进度保存✓" if r["way2"] else "进度保存✗"
            app.message_queue.put({"type": tag, "text": f'  {tag_pre}{ok_txt} {sv_txt}｜{detail}'})
            if r["timelitsec"] and (r["verified"] or 0) < r["timelitsec"]:
                app.message_queue.put({"type": "log_warning",
                                       "text": f'  ⚠ 该课时时长仍未达标，再跑一次会自动补齐剩余部分'})
        except Exception as e:
            app.message_queue.put({"type": "log_error", "text": f'  {tag_pre}✗ [异常] {loc} - {e}'})
            with stats_lock:
                counters["way1_fail"] += 1
                counters["way2_fail"] += 1
        finally:
            with stats_lock:
                processed[0] += 1
                cur = processed[0]
            app.message_queue.put({"type": "progress", "current": cur, "total": total})

    cursor = [0]
    cursor_lock = threading.Lock()

    def next_item():
        with cursor_lock:
            if cursor[0] >= total:
                return None
            item = all_lessons[cursor[0]]
            cursor[0] += 1
            return item

    def lane(lane_id):
        """一路独立浏览器：自己的 Session、自己的心跳节奏，抢剩余课时。"""
        session = _clone_session(app.session)
        time.sleep(random.uniform(0, 12))          # 错峰启动，别让几路同时开始
        done_here = 0
        while not app.stop_requested:
            item = next_item()
            if item is None:
                return
            unit_i, course = item
            process_one(unit_i, course, lane_id, session)
            done_here += 1
            if cooldown_every and done_here % cooldown_every == 0:
                rest = random.randint(cooldown_range[0], cooldown_range[1])
                app.message_queue.put({"type": "log",
                                       "text": f'☕ L{lane_id + 1} 休息 {rest}s（降低集中完成特征）'})
                _sleep_interruptible(rest, lambda: app.stop_requested)

    threads = [threading.Thread(target=lane, args=(i,), daemon=True)
               for i in range(max_threads)]
    for t in threads:
        t.start()
        time.sleep(_rand_delay(0.8, 0.6))
    for t in threads:
        while t.is_alive():
            t.join(timeout=1.0)
    if app.stop_requested:
        app.message_queue.put({"type": "log_warning",
                               "text": f'⚠️ 已停止 | 完成 {processed[0]}/{total}'})
    app.message_queue.put({"type": "log",
                           "text": f'✅ 进度 {processed[0]}/{total}｜剩余 {total - processed[0]} 个'})

    app.message_queue.put({"type": "curriculum_complete",
                           "way1_ok": counters["way1_ok"], "way1_fail": counters["way1_fail"],
                           "way2_ok": counters["way2_ok"], "way2_fail": counters["way2_fail"],
                           "stopped": app.stop_requested})



def thread_time_execute(app):
    """后台线程：刷时长（v3.6：心跳 20~32s、并发上限、结束校验）"""
    try:
        _time_worker(app)
    except Exception as e:
        app.message_queue.put({"type": "log_error", "text": f"✗ 任务异常终止：{e}"})
        app.message_queue.put({"type": "time_complete", "errors": 1, "stopped": app.stop_requested})
    finally:
        app.message_queue.put({"type": "task_finished"})


def _time_worker(app):
    cid, uid, classid = app.selected_cid, app.uid, app.classid
    inputtime = app.time_duration
    mode = app.time_mode
    max_threads = _clamp(int(getattr(app, 'time_max_threads', 4) or 4), 1, 8)

    errors = []
    processed = 0

    all_lessons, err = _collect_lessons(app, only_unfinished=False)
    if err:
        app.message_queue.put({"type": "log_error", "text": f"✗ {err}"})
    already_done = sum(1 for _i, c in all_lessons
                       if "已" in c.get('iscomplete', '') and "未" not in c.get('iscomplete', ''))
    total = len(all_lessons)
    if total == 0:
        app.message_queue.put({"type": "log", "text": "没有可处理的课时。"})
        app.message_queue.put({"type": "time_complete", "errors": 0, "stopped": False})
        return

    app.message_queue.put({"type": "progress", "current": 0, "total": total})
    app.message_queue.put({"type": "log_warning",
                           "text": f"⏱ 刷时长 | 共 {total} 个课时（已完成 {already_done}）| 并发 {max_threads}"})

    cursor = [0]
    cursor_lock = threading.Lock()
    counter = [0]

    def next_item():
        with cursor_lock:
            if cursor[0] >= total:
                return None
            item = all_lessons[cursor[0]]
            cursor[0] += 1
            return item

    def lane(lane_id):
        session = _clone_session(app.session)
        time.sleep(random.uniform(0, 12))
        while not app.stop_requested:
            item = next_item()
            if item is None:
                return
            unit_i, course = item
            learn = random.randint(inputtime[0], inputtime[1]) if mode == 2 else int(inputtime)
            _time_one(app, cid, uid, classid, unit_i, course, learn, errors,
                      lambda: counter[0], session=session)
            with cursor_lock:
                counter[0] += 1
                cur = counter[0]
            app.message_queue.put({"type": "progress", "current": cur, "total": total})

    threads = [threading.Thread(target=lane, args=(i,), daemon=True)
               for i in range(max_threads)]
    for t in threads:
        t.start()
        time.sleep(_rand_delay(0.8, 0.6))
    for t in threads:
        while t.is_alive():
            t.join(timeout=1.0)
    processed = counter[0]
    app.message_queue.put({"type": "log",
                           "text": f'✅ 进度 {processed}/{total}｜剩余 {total - processed} 个'})

    app.message_queue.put({"type": "time_complete", "errors": len(errors),
                           "stopped": app.stop_requested})


def _time_one(app, cid, uid, classid, unit_i, course, learntime, errors, _processed, session=None):
    session = session or app.session
    loc = course.get("location", "?")
    scoid = course.get("id")
    app.message_queue.put({"type": "log", "text": f'[刷时长] {loc} → +{learntime}s 开始...'})
    try:
        blocked, why = welearn_check_gates(session, uid, cid)
        if blocked:
            app.message_queue.put({"type": "log_error", "text": f"🛑 {why}"})
            app.stop_requested = True
            return
        cmi = welearn_time_init(session, cid, uid, scoid)
        if cmi is None:
            app.message_queue.put({"type": "log_error", "text": f'  [失败] {loc} - 初始化学习数据失败'})
            errors.append(loc)
            return
        try:
            init_total = int(cmi.get('total_time') or 0)
        except (TypeError, ValueError):
            init_total = 0

        req = welearn_sco_requirements(session, cid, uid, classid, scoid)
        if req.get("timelitsec"):
            deficit = max(0, req["timelitsec"] - req["use_seconds"])
            if deficit and deficit < learntime:
                learntime = deficit  # 只需补齐差额，不空等
            if req["use_seconds"] >= req["timelitsec"]:
                app.message_queue.put({"type": "log",
                                       "text": f'  [跳过] {loc} 已满足平台要求 {req["timelitsec"]}s'})
                return

        welearn_time_heartbeat(session, cid, uid, scoid, "0", str(init_total))
        elapsed = 0
        hb_count = 0
        next_hb = random.randint(HEARTBEAT_MIN, HEARTBEAT_MAX)
        while elapsed < learntime:
            if app.stop_requested:
                app.message_queue.put({"type": "log_warning",
                                       "text": f'  ⏹ {loc} 中断于 {elapsed}/{learntime}s'})
                break
            time.sleep(_rand_delay(1.0, 0.15))
            elapsed += 1
            if elapsed >= next_hb:
                welearn_time_heartbeat(app.session, cid, uid, scoid, str(elapsed),
                                       str(init_total + elapsed))
                hb_count += 1
                next_hb = elapsed + random.randint(HEARTBEAT_MIN, HEARTBEAT_MAX)

        welearn_time_heartbeat(app.session, cid, uid, scoid, str(elapsed),
                               str(init_total + elapsed))
        hb_count += 1
        ok = welearn_time_finalize(app.session, cid, uid, scoid,
                                   cmi.get('progress', '100'), cmi.get('crate', '0'),
                                   cmi.get('cstatus', 'completed'),
                                   str(elapsed), str(init_total + elapsed))
        if ok:
            app.message_queue.put({"type": "log_success",
                                   "text": f'  [完成] {loc} (+{elapsed}s, {hb_count}次心跳, 累计{init_total + elapsed}s)'})
        else:
            app.message_queue.put({"type": "log_error", "text": f'  [失败] {loc} - 保存失败'})
            errors.append(loc)
    except Exception as e:
        app.message_queue.put({"type": "log_error", "text": f'  [异常] {loc} - {e}'})
        errors.append(loc)


def _load_config():
    """加载持久化配置"""
    try:
        if _os.path.exists(CONFIG_PATH):
            with open(CONFIG_PATH, 'r', encoding='utf-8') as f:
                return json.load(f)
    except Exception:
        pass
    return {}

def _save_config(cfg):
    """保存持久化配置"""
    try:
        tmp = CONFIG_PATH + ".tmp"
        with open(tmp, 'w', encoding='utf-8') as f:
            json.dump(cfg, f, ensure_ascii=False, indent=2)
        _os.replace(tmp, CONFIG_PATH)
    except Exception:
        pass


def _clone_session(src):
    """复制登录态到一个独立 Session。

    requests.Session 的连接池/CookieJar 不是线程安全的，多路并发必须各用各的；
    但 UA 与 Cookie 必须和主会话一致，否则就是「同一账号多个浏览器指纹」。
    """
    s = requests.Session()
    try:
        s.cookies.update(src.cookies.get_dict())
    except Exception:
        pass
    try:
        s.headers['User-Agent'] = _SESSION_PROFILE[0]
    except Exception:
        pass
    return s


def _sleep_interruptible(seconds, stop_check):
    """分段睡眠，停止时能在 1 秒内响应。"""
    waited = 0.0
    while waited < seconds:
        if stop_check():
            return False
        step = min(1.0, seconds - waited)
        time.sleep(step)
        waited += step
    return True


# ── GUI 主类 ──────────────────────────────────────────
class WelearnApp:
    def __init__(self):
        # 加载持久化配置
        self._config = _load_config()

        # 外观模式（从配置恢复，默认跟随系统）
        appearance = self._config.get("appearance", "System")
        ctk.set_appearance_mode(appearance)
        ctk.set_default_color_theme("blue")

        self.root = ctk.CTk()
        self.root.title("Welearn 刷课工具 v3.8")
        self.root.geometry("1060x700")
        self.root.minsize(960, 640)

        # 语言（从配置恢复）
        self.lang = self._config.get("lang", "zh")

        # 应用状态
        self.session = requests.Session()
        self.message_queue = queue.Queue()
        self.stop_requested = False
        self.running = False

        # 课程数据
        self.courses = []
        self.units = []
        self.selected_cid = None
        self.selected_unit_idx = 0
        self.uid = None
        self.classid = None

        # 登录模式
        self.login_mode = "cookie"
        self.login_cookie = ""
        self.login_username = ""
        self.login_password = ""

        # 刷课参数（v3.6 安全默认：正确率带随机、时长按平台要求补齐、单并发）
        self.curriculum_rate = [80, 92]
        self.curriculum_random = True
        self.curriculum_duration = [600, 900]
        self.curriculum_max_threads = 4

        # 刷时长参数
        self.time_duration = [600, 900]
        self.time_mode = 2
        self.time_max_threads = 4

        # 节奏与配额（防"短时间集中完成"被打回）
        self.risk_preset = "safe"
        self.daily_lesson_cap = 24
        self.cooldown_every = 4
        self.cooldown_range = (400, 900)

        self._build_sidebar()
        self._build_content()
        self._build_statusbar()
        self._show_page("home")
        self.root.after(100, self._poll_queue)
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)
        self.root.bind("<Control-Return>", lambda _e: self._on_start_task())
        self.root.bind("<Escape>", lambda _e: self._on_stop() if self.running else None)

        # 免责声明（从配置检查是否跳过）
        if not self._config.get("disclaimer_skip", False):
            self.root.after(300, self._show_disclaimer)

    def _save_prefs(self):
        """保存当前偏好到配置文件"""
        self._config["lang"] = self.lang
        self._config["appearance"] = ctk.get_appearance_mode()
        try:
            self._config["preset"] = self.risk_preset
            self._config["daily_cap"] = self.daily_lesson_cap
            self._config["rate"] = list(self.curriculum_rate) if isinstance(self.curriculum_rate, list) \
                else self.curriculum_rate
            self._config["ratio_random"] = self.curriculum_random
        except Exception:
            pass
        _save_config(self._config)

    def _tick_mascot(self):
        """idle 动效：6 帧循环，运行中稍快一点（像在陪你干活）。"""
        try:
            self._anim_i = (self._anim_i + 1) % len(self._anim_imgs)
            self.mascot_label.configure(image=self._anim_imgs[self._anim_i])
        except Exception:
            return
        delay = 150 if getattr(self, "running", False) else 240
        self.root.after(delay, self._tick_mascot)

    # ═══ 侧边栏 ═══════════════════════════════════════
    def _build_sidebar(self):
        self.sidebar = ctk.CTkFrame(self.root, width=300, corner_radius=0,
                                     fg_color=("#1a1a2e", "#0d1117"))
        self.sidebar.pack(side="left", fill="y")
        self.sidebar.pack_propagate(False)

        # ── 侧边栏立绘：循环播放的 idle 动效（不标注角色名） ──
        mascot_frame = ctk.CTkFrame(self.sidebar, fg_color="transparent")
        mascot_frame.pack(fill="x", padx=20, pady=(18, 4))
        try:
            badge = ctk.CTkFrame(mascot_frame, corner_radius=28,
                                 fg_color=("#e8eefc", "#0e1730"),
                                 border_width=1, border_color=("#b9c8f2", "#26406f"))
            badge.pack(anchor="center")
            self._anim_imgs = []
            for name in _ANIM_FRAMES:
                p = _asset(name)
                if _os.path.exists(p):
                    self._anim_imgs.append(ctk.CTkImage(Image.open(p), size=(112, 112)))
            self._mascot_img = self._anim_imgs[0] if self._anim_imgs else None
            self.mascot_label = ctk.CTkLabel(badge, image=self._mascot_img, text="")
            self.mascot_label.pack(padx=8, pady=8)
            if len(self._anim_imgs) > 1:
                self._anim_i = 0
                self.root.after(220, self._tick_mascot)
        except Exception:
            ctk.CTkLabel(mascot_frame, text="🐳", font=ctk.CTkFont(size=48)).pack(anchor="center")

        # 分隔线 + 导航按钮区
        nav_header = ctk.CTkFrame(self.sidebar, fg_color="transparent")
        nav_header.pack(fill="x", padx=12, pady=(10, 5))
        ctk.CTkFrame(nav_header, height=1, fg_color=("#30363d", "#21262d")).pack(fill="x", pady=(0, 8))
        ctk.CTkLabel(nav_header, text="导航", font=ctk.CTkFont(size=10),
                     text_color=("#484f58", "#484f58")).pack(anchor="w")

        nav_items = [
            ("home", "🏠  主页"),
            ("donate", "☕  赞助"),
            ("help", "📖  帮助"),
            ("settings", "⚙️  设置"),
        ]
        self.nav_buttons = {}
        for key, label in nav_items:
            btn = ctk.CTkButton(self.sidebar, text=label, width=270, height=36,
                               corner_radius=8,
                               fg_color="transparent",
                               text_color=("#8b949e", "#8b949e"),
                               hover_color=("#30363d", "#21262d"),
                               font=ctk.CTkFont(size=12),
                               anchor="w",
                               command=lambda k=key: self._show_page(k))
            btn.pack(pady=1, padx=15)
            self.nav_buttons[key] = btn

        # ── 日志区（填满剩余侧边栏空间） ──
        log_header = ctk.CTkFrame(self.sidebar, fg_color="transparent")
        log_header.pack(fill="x", padx=15, pady=(10, 0))
        ctk.CTkFrame(log_header, height=1, fg_color=("#30363d", "#21262d")).pack(fill="x", pady=(0, 6))
        title_row = ctk.CTkFrame(log_header, fg_color="transparent")
        title_row.pack(fill="x")
        ctk.CTkLabel(title_row, text="📋 运行日志",
                     font=ctk.CTkFont(size=12, weight="bold"),
                     text_color=("#8b949e", "#8b949e")).pack(side="left")
        ctk.CTkButton(title_row, text="清空", width=44, height=20, corner_radius=6,
                      fg_color="transparent", hover_color=("#30363d", "#21262d"),
                      text_color=("#64748b", "#8b949e"),
                      font=ctk.CTkFont(size=10),
                      command=self._clear_log).pack(side="right", padx=(4, 0))
        ctk.CTkButton(title_row, text="导出", width=44, height=20, corner_radius=6,
                      fg_color="transparent", hover_color=("#30363d", "#21262d"),
                      text_color=("#64748b", "#8b949e"),
                      font=ctk.CTkFont(size=10),
                      command=self._export_log).pack(side="right")

        self.log_text = ctk.CTkTextbox(self.sidebar, wrap="word",
                                        font=ctk.CTkFont(size=11),
                                        fg_color=("#0d1117", "#0d1117"))
        self.log_text.pack(fill="both", expand=True, padx=10, pady=(4, 0))
        self.log_text.configure(state="disabled")
        self._setup_log_tags()

        # 底部：状态 + 版本（紧凑一行）
        bottom_frame = ctk.CTkFrame(self.sidebar, fg_color="transparent")
        bottom_frame.pack(side="bottom", fill="x", padx=15, pady=(4, 10))
        ctk.CTkFrame(bottom_frame, height=1, fg_color=("#30363d", "#21262d")).pack(fill="x", pady=(0, 6))
        ctk.CTkLabel(bottom_frame, text="v3.8 · 免费开源",
                     font=ctk.CTkFont(size=9),
                     text_color=("#484f58", "#484f58")).pack(anchor="w")

    # ═══ 内容区 ═══════════════════════════════════════
    def _build_content(self):
        self.content_area = ctk.CTkFrame(self.root, fg_color="transparent")
        self.content_area.pack(side="left", fill="both", expand=True)

        self.pages = {}
        self._build_home_page()
        self._build_donate_page()
        self._build_help_page()
        self._build_settings_page()

    def _show_page(self, name):
        for key, frame in self.pages.items():
            frame.pack_forget()
        self.pages[name].pack(fill="both", expand=True, padx=(0, 0), pady=0)

        for key, btn in self.nav_buttons.items():
            if key == name:
                btn.configure(fg_color=("#30363d", "#21262d"),
                              text_color=("#f0abfc", "#c084fc"))
            else:
                btn.configure(fg_color="transparent",
                              text_color=("#8b949e", "#8b949e"))

    # ═══ 主页 ═════════════════════════════════════════
    def _build_home_page(self):
        page = ctk.CTkFrame(self.content_area, fg_color="transparent")
        self.pages["home"] = page

        # 可滚动容器（解决内容溢出问题）
        self.home_scroll = ctk.CTkScrollableFrame(page, fg_color="transparent")
        self.home_scroll.pack(fill="both", expand=True)

        # ── 顶部标题 + 渐变条 ──
        hero = ctk.CTkFrame(self.home_scroll, corner_radius=0, fg_color="transparent")
        hero.pack(fill="x", padx=12, pady=(10, 2))
        try:
            self._strip_src = Image.open(_asset("strip.png")).convert("RGB")
            self.strip_label = ctk.CTkLabel(hero, text="", height=8)
            self.strip_label.pack(fill="x", pady=(0, 10))

            def _strip_once():
                """只按当前宽度画一次，避免 Configure 递归把 GDI 资源耗光。"""
                try:
                    w = max(240, min(1200, hero.winfo_width()))
                    img = self._strip_src.resize((w, 8), Image.LANCZOS)
                    self._strip_img = ctk.CTkImage(img, size=(w, 8))
                    self.strip_label.configure(image=self._strip_img)
                except Exception:
                    pass

            self.root.after(150, _strip_once)
        except Exception:
            pass

        ctk.CTkLabel(hero, text="WE·LEARN 学习助手",
                     font=ctk.CTkFont(size=20, weight="bold"),
                     text_color=("#1b2a4a", "#e9f1ff")).pack(anchor="w")
        ctk.CTkLabel(hero, text="按平台要求补齐学时 · 多路并行 · 提交后回读校验",
                     font=ctk.CTkFont(size=11),
                     text_color=("#5b7099", "#8aa4c8")).pack(anchor="w", pady=(3, 2))

        # ── 安全节奏卡片（v3.6）──
        self.risk_frame = ctk.CTkFrame(self.home_scroll, corner_radius=12,
                                       fg_color=("#fffbeb", "#241d10"),
                                       border_width=1,
                                       border_color=("#fde68a", "#6b5320"))
        self.risk_frame.pack(fill="x", padx=10, pady=(5, 3))

        head = ctk.CTkFrame(self.risk_frame, fg_color="transparent")
        head.pack(fill="x", padx=15, pady=(12, 2))
        ctk.CTkLabel(head, text="🛡 节奏与风险", font=ctk.CTkFont(size=15, weight="bold")
                     ).pack(side="left")
        self.preset_label = ctk.CTkLabel(head, text="", font=ctk.CTkFont(size=11),
                                         text_color=("#92400e", "#d6b370"))
        self.preset_label.pack(side="right")

        for line in (
            "· 平台按真实在线时长计学时，单课时通常 18 分钟，脚本自动补齐并回读校验",
            "· 并行 = 同时上多节课，每节仍按真实时间算，只是总墙钟被摊薄",
            "· 集中完成最容易被复核，默认 3~4 路 + 单日上限 + 每几节休息",
        ):
            ctk.CTkLabel(self.risk_frame, text=line, font=ctk.CTkFont(size=11),
                         justify="left", wraplength=380,
                         text_color=("#78350f", "#c9b48a")
                         ).pack(anchor="w", padx=15, pady=1)

        preset_row = ctk.CTkFrame(self.risk_frame, fg_color="transparent")
        preset_row.pack(fill="x", padx=15, pady=(0, 6))
        self.preset_seg = ctk.CTkSegmentedButton(
            preset_row, values=["安全（推荐）", "标准", "极速"],
            command=self._on_preset_change, height=30)
        self.preset_seg.pack(side="left")
        self.preset_seg.set("安全（推荐）")
        ctk.CTkLabel(preset_row, text="  并行 = 多开",
                     font=ctk.CTkFont(size=10), text_color=("#92400e", "#a08a63")).pack(side="left")

        self.estimate_label = ctk.CTkLabel(self.risk_frame, text="", font=ctk.CTkFont(size=11),
                                           justify="left", wraplength=620,
                                           text_color=("#78350f", "#c9b48a"))
        self.estimate_label.pack(anchor="w", padx=15, pady=(0, 12))

        # ── 登录面板 ──
        self.login_frame = ctk.CTkFrame(self.home_scroll, corner_radius=12,
                                         fg_color=("#f8fafc", "#1e293b"),
                                         border_width=1,
                                         border_color=("#e2e8f0", "#334155"))
        self.login_frame.pack(fill="x", padx=10, pady=(5, 3))

        ctk.CTkLabel(self.login_frame, text="🔑 登录方式",
                     font=ctk.CTkFont(size=15, weight="bold")).pack(anchor="w", padx=15, pady=(12, 5))

        mode_frame = ctk.CTkFrame(self.login_frame, fg_color="transparent")
        mode_frame.pack(fill="x", padx=15, pady=(0, 5))
        self.login_mode_var = ctk.StringVar(value="cookie")
        ctk.CTkRadioButton(mode_frame, text="Cookie 登录（推荐）",
                           variable=self.login_mode_var, value="cookie",
                           command=self._on_login_mode_change).pack(side="left", padx=(0, 20))
        ctk.CTkRadioButton(mode_frame, text="账号密码登录（实验性）",
                           variable=self.login_mode_var, value="password",
                           command=self._on_login_mode_change).pack(side="left")

        # Cookie 输入（使用 Textbox 避免大段 JSON 粘贴卡顿）
        self.cookie_panel = ctk.CTkFrame(self.login_frame, fg_color="transparent")
        self.cookie_panel.pack(fill="x", padx=15, pady=(5, 5))
        ctk.CTkLabel(self.cookie_panel, text="Cookie:").pack(anchor="w")
        self.cookie_entry = ctk.CTkTextbox(self.cookie_panel, height=60, wrap="word",
                                            font=ctk.CTkFont(size=11))
        self.cookie_entry.pack(fill="x", padx=(0, 0), pady=(2, 5))
        self.btn_login = ctk.CTkButton(self.cookie_panel, text="登录", width=100, command=self._on_login)
        self.btn_login.pack(anchor="e")

        # 密码输入（初始隐藏）
        self.password_panel = ctk.CTkFrame(self.login_frame, fg_color="transparent")
        self.username_entry = ctk.CTkEntry(self.password_panel, placeholder_text="账号", width=200)
        self.username_entry.pack(side="left", padx=(0, 10))
        self.password_entry = ctk.CTkEntry(self.password_panel, placeholder_text="密码", show="●", width=200)
        self.password_entry.pack(side="left", padx=(0, 10))
        self.btn_password_login = ctk.CTkButton(self.password_panel, text="登录", width=100, command=self._on_login)
        self.btn_password_login.pack(side="left")

        self.login_status = ctk.CTkLabel(self.login_frame, text="未登录", text_color="gray")
        self.login_status.pack(anchor="w", padx=15, pady=(0, 10))

        # ── 课程选择 ──
        self.course_frame = ctk.CTkFrame(self.home_scroll, corner_radius=12,
                                          fg_color=("#f8fafc", "#1e293b"),
                                          border_width=1,
                                          border_color=("#e2e8f0", "#334155"))

        row1 = ctk.CTkFrame(self.course_frame, fg_color="transparent")
        row1.pack(fill="x", padx=15, pady=(10, 5))
        ctk.CTkLabel(row1, text="选择课程:", width=70).pack(side="left")
        self.course_menu = ctk.CTkOptionMenu(row1, values=["请先登录"], width=400,
                                             command=self._on_course_selected)
        self.course_menu.pack(side="left", padx=(10, 10))
        self.btn_refresh = ctk.CTkButton(row1, text="刷新", width=60, command=self._on_refresh, state="disabled")
        self.btn_refresh.pack(side="left")

        row2 = ctk.CTkFrame(self.course_frame, fg_color="transparent")
        row2.pack(fill="x", padx=15, pady=(0, 10))
        ctk.CTkLabel(row2, text="选择单元:", width=70).pack(side="left")
        self.unit_menu = ctk.CTkOptionMenu(row2, values=["请先选择课程"], width=400,
                                           command=self._on_unit_selected)
        self.unit_menu.pack(side="left", padx=(10, 10))

        # ── 任务设置面板（v3.3: 整合刷课+刷时长） ──
        self.task_frame = ctk.CTkFrame(self.home_scroll, corner_radius=12,
                                        fg_color=("#f8fafc", "#1e293b"),
                                        border_width=1,
                                        border_color=("#e2e8f0", "#334155"))
        self.task_frame.pack(fill="x", padx=10, pady=5)

        # 模式选择
        mode_header = ctk.CTkFrame(self.task_frame, fg_color="transparent")
        mode_header.pack(fill="x", padx=15, pady=(12, 8))
        ctk.CTkLabel(mode_header, text="⚡ 任务模式", font=ctk.CTkFont(size=14, weight="bold")).pack(anchor="w")

        self.task_mode_var = ctk.StringVar(value="curriculum")
        mode_row = ctk.CTkFrame(self.task_frame, fg_color="transparent")
        mode_row.pack(fill="x", padx=15, pady=(0, 8))
        ctk.CTkRadioButton(mode_row, text="📝 刷课并计时（解析题目+答题记录+学习时长）",
                           variable=self.task_mode_var, value="curriculum",
                           command=self._on_task_mode_change).pack(anchor="w", pady=2)
        ctk.CTkRadioButton(mode_row, text="⏱ 仅刷时长（心跳保活，不操作题目）",
                           variable=self.task_mode_var, value="timeonly",
                           command=self._on_task_mode_change).pack(anchor="w", pady=2)

        # 分隔线
        ctk.CTkFrame(self.task_frame, height=1, fg_color=("#e2e8f0", "#334155")).pack(fill="x", padx=15)

        # ── 正确率设置（仅刷课模式显示） ──
        self.rate_panel = ctk.CTkFrame(self.task_frame, fg_color="transparent")
        self.rate_panel.pack(fill="x", padx=15, pady=(6, 0))
        ctk.CTkLabel(self.rate_panel, text="正确率设置",
                     font=ctk.CTkFont(size=13, weight="bold")).pack(anchor="w", pady=(0, 8))

        self.rate_var = ctk.StringVar(value="random")
        fixed_frame = ctk.CTkFrame(self.rate_panel, fg_color="transparent")
        fixed_frame.pack(fill="x", pady=1)
        ctk.CTkRadioButton(fixed_frame, text="固定:", variable=self.rate_var, value="fixed",
                           command=self._on_rate_mode_change).pack(side="left")
        self.fixed_rate_entry = ctk.CTkEntry(fixed_frame, width=65, placeholder_text="88")
        self.fixed_rate_entry.pack(side="left", padx=5)
        self.fixed_rate_entry.insert(0, "88")
        ctk.CTkLabel(fixed_frame, text="%").pack(side="left")

        rand_frame = ctk.CTkFrame(self.rate_panel, fg_color="transparent")
        rand_frame.pack(fill="x", pady=1)
        ctk.CTkRadioButton(rand_frame, text="随机:", variable=self.rate_var, value="random",
                           command=self._on_rate_mode_change).pack(side="left")
        self.rand_min_entry = ctk.CTkEntry(rand_frame, width=55, placeholder_text="80")
        self.rand_min_entry.pack(side="left", padx=5)
        self.rand_min_entry.insert(0, "80")
        ctk.CTkLabel(rand_frame, text="~").pack(side="left")
        self.rand_max_entry = ctk.CTkEntry(rand_frame, width=55, placeholder_text="92")
        self.rand_max_entry.pack(side="left", padx=5)
        self.rand_max_entry.insert(0, "92")
        ctk.CTkLabel(rand_frame, text="%").pack(side="left")
        self._on_rate_mode_change()

        # ── 时长 + 线程（共享） ──
        ctk.CTkFrame(self.task_frame, height=1, fg_color=("#e2e8f0", "#334155")).pack(fill="x", padx=15, pady=(6, 0))

        shared_panel = ctk.CTkFrame(self.task_frame, fg_color="transparent")
        shared_panel.pack(fill="x", padx=15, pady=(10, 5))
        ctk.CTkLabel(shared_panel, text="时长与并发设置",
                     font=ctk.CTkFont(size=13, weight="bold")).pack(anchor="w", pady=(0, 8))

        ctk.CTkLabel(shared_panel,
                     text="课时时长 = 下限，不足部分由平台要求（timelitsec）自动补齐；上限 1500s。",
                     font=ctk.CTkFont(size=10), text_color=("#64748b", "#7c8db5")
                     ).pack(anchor="w", pady=(0, 6))

        time_mode_row = ctk.CTkFrame(shared_panel, fg_color="transparent")
        time_mode_row.pack(fill="x", pady=1)
        self.time_var = ctk.StringVar(value="random")
        ctk.CTkRadioButton(time_mode_row, text="固定:", variable=self.time_var, value="fixed",
                           command=self._on_time_mode_change).pack(side="left")
        self.fixed_time_entry = ctk.CTkEntry(time_mode_row, width=65, placeholder_text="720")
        self.fixed_time_entry.pack(side="left", padx=5)
        self.fixed_time_entry.insert(0, "720")
        ctk.CTkLabel(time_mode_row, text="秒/课").pack(side="left")

        rand_time_row = ctk.CTkFrame(shared_panel, fg_color="transparent")
        rand_time_row.pack(fill="x", pady=1)
        ctk.CTkRadioButton(rand_time_row, text="随机:", variable=self.time_var, value="random",
                           command=self._on_time_mode_change).pack(side="left")
        self.time_min_entry = ctk.CTkEntry(rand_time_row, width=55, placeholder_text="600")
        self.time_min_entry.pack(side="left", padx=5)
        self.time_min_entry.insert(0, "600")
        ctk.CTkLabel(rand_time_row, text="~").pack(side="left")
        self.time_max_entry = ctk.CTkEntry(rand_time_row, width=55, placeholder_text="900")
        self.time_max_entry.pack(side="left", padx=5)
        self.time_max_entry.insert(0, "900")
        ctk.CTkLabel(rand_time_row, text="秒/课").pack(side="left")
        self._on_time_mode_change()

        thread_row = ctk.CTkFrame(shared_panel, fg_color="transparent")
        thread_row.pack(fill="x", pady=(8, 0))
        ctk.CTkLabel(thread_row, text="并发路数:").pack(side="left")
        self.threads_entry = ctk.CTkEntry(thread_row, width=55, placeholder_text="4")
        self.threads_entry.pack(side="left", padx=5)
        self.threads_entry.insert(0, "4")
        ctk.CTkLabel(thread_row, text="（每路各自真实计时：实测 4 路各 +61s/86s 无损耗；建议 3~4，上限 8）",
                     font=ctk.CTkFont(size=10), text_color=("#64748b", "#7c8db5")).pack(side="left")

        # ── 开始按钮 + 进度 ──
        btn_row = ctk.CTkFrame(self.task_frame, fg_color="transparent")
        btn_row.pack(fill="x", padx=15, pady=(12, 5))
        self.btn_start_task = ctk.CTkButton(btn_row, text="🚀 开始运行",
                                            fg_color=("#3f6ee0", "#2f5bd0"),
                                            hover_color=("#3560cc", "#3d6ee6"),
                                            height=42, width=180, corner_radius=8,
                                            font=ctk.CTkFont(size=14, weight="bold"),
                                            command=self._on_start_task)
        self.btn_start_task.pack(side="left")

        # 进度条 + 统计
        progress_frame = ctk.CTkFrame(self.task_frame, fg_color="transparent")
        progress_frame.pack(fill="x", padx=15, pady=(0, 10))
        self.task_progress_label = ctk.CTkLabel(progress_frame, text="进度: -/-", font=ctk.CTkFont(size=12))
        self.task_progress_label.pack(anchor="w")
        self.task_progress_bar = ctk.CTkProgressBar(progress_frame, width=500,
                                                    height=8, corner_radius=4,
                                                    progress_color=("#4cc9d6", "#5b8def"))
        self.task_progress_bar.pack(fill="x", pady=(3, 3))
        self.task_progress_bar.set(0)
        self.task_stats_label = ctk.CTkLabel(progress_frame, text="", font=ctk.CTkFont(size=11),
                                              text_color=("#64748b", "#94a3b8"))
        self.task_stats_label.pack(anchor="w")

        # 恢复上次使用的节奏预设
        saved_preset = (self._config or {}).get("preset")
        preset_name = {"safe": "安全（推荐）", "standard": "标准", "fast": "极速"}.get(saved_preset)
        if preset_name:
            try:
                self.preset_seg.set(preset_name)
                self._on_preset_change(preset_name)
            except Exception:
                pass

        # 初始化节奏预估文案
        try:
            self._update_estimate()
            self.preset_label.configure(text="当前：安全（推荐）")
        except Exception:
            pass

        # ── 日志已移至侧边栏 ──

    PRESETS = {
        "安全（推荐）": dict(rate=(80, 92), dur=(600, 900), cooldown_every=4,
                         cooldown=(400, 900), cap=24, lanes=3,
                         note="3 路并行，每路真实学满；每 4 节休息，单日最多 24 节。"),
        "标准": dict(rate=(75, 90), dur=(480, 720), cooldown_every=6,
                   cooldown=(120, 300), cap=36, lanes=4,
                   note="4 路并行，节奏略快；适合课时多、时间紧。"),
        "极速": dict(rate=(70, 85), dur=(120, 300), cooldown_every=0,
                   cooldown=(0, 0), cap=999, lanes=6,
                   note="⚠ 6 路 + 短时长；每节没学够平台要求，被复核打回概率很高，仅救急。"),
    }

    def _on_preset_change(self, choice):
        p = self.PRESETS.get(choice)
        if not p:
            return
        self.risk_preset = {"安全（推荐）": "safe", "标准": "standard", "极速": "fast"}[choice]
        self.daily_lesson_cap = p["cap"]
        self.cooldown_every = p["cooldown_every"]
        self.cooldown_range = p["cooldown"]

        # 同步控件
        lo, hi = p["rate"]
        self.rate_var.set("random")
        self.rand_min_entry.delete(0, "end")
        self.rand_min_entry.insert(0, str(lo))
        self.rand_max_entry.delete(0, "end")
        self.rand_max_entry.insert(0, str(hi))
        self._on_rate_mode_change()

        dlo, dhi = p["dur"]
        self.time_var.set("random")
        self.time_min_entry.delete(0, "end")
        self.time_min_entry.insert(0, str(dlo))
        self.time_max_entry.delete(0, "end")
        self.time_max_entry.insert(0, str(dhi))
        self._on_time_mode_change()

        self.threads_entry.delete(0, "end")
        self.threads_entry.insert(0, str(p.get("lanes", 4)))

        self.preset_label.configure(text=f"当前：{choice}")
        self._update_estimate()

    def _update_estimate(self):
        try:
            lo = int(self.time_min_entry.get())
            hi = int(self.time_max_entry.get())
        except (ValueError, AttributeError):
            lo, hi = 600, 900
        avg = max(1, (lo + hi) // 2)
        cap = min(self.daily_lesson_cap, 999)
        try:
            lanes = max(1, int(self.threads_entry.get()))
        except (ValueError, AttributeError):
            lanes = 4
        per_day_min = avg * cap / 60.0 / lanes
        extra = ""
        if self.cooldown_every:
            extra = f"，另加每 {self.cooldown_every} 节约 {self.cooldown_range[0]//60}~" \
                    f"{self.cooldown_range[1]//60} 分钟休息"
        self.estimate_label.configure(
            text=f"⏱ 单节 {lo//60}~{hi//60} 分 × {lanes} 路 ⇒ 单日 {cap} 节约 {per_day_min/60:.1f} 小时")

    def _on_task_mode_change(self):
        """切换任务模式时显示/隐藏正确率面板"""
        if self.task_mode_var.get() == "curriculum":
            self.rate_panel.pack(fill="x", padx=15, pady=(6, 0),
                                before=self.task_frame.winfo_children()[-4])
        else:
            self.rate_panel.pack_forget()

    # ═══ 赞助页 ═══════════════════════════════════════
    def _build_donate_page(self):
        page = ctk.CTkFrame(self.content_area, fg_color="transparent")
        self.pages["donate"] = page

        container = ctk.CTkFrame(page)
        container.pack(expand=True, padx=40, pady=30)

        ctk.CTkLabel(container, text="支持作者",
                     font=ctk.CTkFont(size=26, weight="bold")).pack(pady=(30, 20))

        desc_labels = [
            ("", 22),
            ("", 22),
            ("", 22),
            ("", 22),
            ("", 22),
        ]
        desc_text = (
            "此程序为免费开源项目\n"
            "如果你付了钱，请立刻退款！\n\n"
            "如果喜欢本项目\n"
            "可以微信赞赏送作者一杯咖啡 ☕\n\n"
            "你的支持就是作者开发维护的动力"
        )
        ctk.CTkLabel(container, text=desc_text, font=ctk.CTkFont(size=15),
                     justify="center", text_color="gray").pack(pady=(0, 25))

        sep = ctk.CTkFrame(container, height=1, fg_color="gray")
        sep.pack(fill="x", padx=60, pady=(0, 20))

        try:
            pil_qr = Image.open(_DONATE_QR_PATH)
            qw = 300
            qh = int(pil_qr.size[1] * (qw / pil_qr.size[0]))
            pil_qr = pil_qr.resize((qw, qh), Image.LANCZOS)
            qr_img = ctk.CTkImage(pil_qr, size=(qw, qh))
            ctk.CTkLabel(container, image=qr_img, text="").pack(pady=(0, 10))
        except Exception:
            ctk.CTkLabel(container, text="(赞赏码图片未找到)",
                        font=ctk.CTkFont(size=12), text_color="gray", height=280).pack(pady=(0, 10))

        ctk.CTkLabel(container, text="微信扫码即可赞赏",
                     font=ctk.CTkFont(size=13), text_color="gray").pack(pady=(0, 20))

        ctk.CTkButton(container, text="下次一定", height=38, width=180,
                      fg_color="#7f8c8d", hover_color="#6c7a7a",
                      font=ctk.CTkFont(size=14),
                      command=lambda: self._show_page("home")).pack(pady=(0, 30))

    # ═══ 帮助页 ═══════════════════════════════════════
    def _build_help_page(self):
        page = ctk.CTkFrame(self.content_area, fg_color="transparent")
        self.pages["help"] = page

        scroll = ctk.CTkScrollableFrame(page)
        scroll.pack(fill="both", expand=True, padx=15, pady=15)

        ctk.CTkLabel(scroll, text="Cookie 获取教程",
                     font=ctk.CTkFont(size=20, weight="bold")).pack(anchor="w", pady=(10, 15))

        steps = [
            "1. 登录 welearn 网页版，按 F12 打开开发者工具",
            "2. 点击顶部的 Network（网络）选项卡",
            "3. 按 F5 刷新页面",
            "4. 在左侧列表找到第一个请求并点击",
            "5. 在右侧找到 Request Headers 中的 Cookie 字段",
            "6. 复制完整的 Cookie 值，粘贴到软件中",
        ]
        for step in steps:
            ctk.CTkLabel(scroll, text=step, font=ctk.CTkFont(size=14),
                        justify="left").pack(anchor="w", pady=4, padx=10)

        # 教程图片
        img_infos = [
            ("help_1.jpg", "步骤 1-2: 打开控制台和网络标签"),
            ("help_2.jpg", "步骤 3-4: 刷新并找到第一个请求"),
            ("help_3.jpg", "步骤 5-6: 找到并复制 Cookie"),
        ]
        for img_file, img_title in img_infos:
            try:
                if getattr(sys, 'frozen', False):
                    img_path = _os.path.join(sys._MEIPASS, 'src', img_file)
                else:
                    img_path = _os.path.join(_os.path.dirname(_os.path.abspath(__file__)), img_file)
                pil_img = Image.open(img_path)
                tw = 480
                th = int(pil_img.size[1] * (tw / pil_img.size[0]))
                pil_img = pil_img.resize((tw, th), Image.LANCZOS)
                img = ctk.CTkImage(pil_img, size=(tw, th))
                ctk.CTkLabel(scroll, text=img_title, font=ctk.CTkFont(size=13, weight="bold"),
                            text_color="#3498db").pack(anchor="w", padx=10, pady=(15, 5))
                ctk.CTkLabel(scroll, image=img, text="").pack(pady=(0, 10))
            except Exception:
                ctk.CTkLabel(scroll, text=f"(教程图片 {img_file} 未找到)",
                            font=ctk.CTkFont(size=12), text_color="gray").pack(pady=5)

        # 为什么会被清记录
        ctk.CTkLabel(scroll, text="为什么刷完当天没事、隔天却被清掉？",
                     font=ctk.CTkFont(size=16, weight="bold")).pack(anchor="w", padx=10, pady=(20, 8))
        reasons = [
            "1. 学时是「真实在线时长」：平台按 startsco→savescoinfo 的墙钟差计时，"
            "单课通常要求 18 分钟。几十秒刷完一节，属于时钟流速异常。",
            "2. 平台按天复核：完成事件当天入库，T+1 再跨事件聚合（完成密度、心跳连续性、登录时间），"
            "命中就整批回滚——这就是「隔天消失」。",
            "3. studyTicket 互踢只在浏览器 JS 里生效（多开会弹框并 EndSCO）；纯发包不受影响，"
            "实测 4 路并行各 +61s/86s、零损耗——所以并行是合法的提速手段，代价是完成密度更像脚本。",
            "4. 老师端有「学习监控 / 需要关注学生」，正确率 100% 而答题记录缺失很容易被人工清除。",
            "5. 平台还有两道闸门：isPausing（判定刷课行为后锁 N 分钟/今日锁定）、"
            "checkNoCaptcha（强制滑块验证）。本工具会检测到并提示你停下。",
        ]
        for r in reasons:
            ctk.CTkLabel(scroll, text=r, font=ctk.CTkFont(size=12), justify="left",
                         wraplength=760, text_color=("#475569", "#94a3b8")
                         ).pack(anchor="w", padx=10, pady=3)

        ctk.CTkLabel(scroll, text="本工具的做法", font=ctk.CTkFont(size=16, weight="bold")
                     ).pack(anchor="w", padx=10, pady=(16, 8))
        fixes = [
            "• 按平台要求（timelitsec）自动补齐课时时长，不再固定几十秒；",
            "• 学习过程中每 20~32 秒发一次心跳，结束时补心跳，再提交完成，最后回读校验时长；",
            "• 默认 3~4 路并行（每路真实计时）+ 单日上限 + 每几节休息，兼顾速度与痕迹；",
            "• 正确率默认 80~92% 随机，避免「100% 但没有答题记录」的异常组合；",
            "• 课时多时请分几天跑：学时无法压缩，想拿 6 小时就得真在线 6 小时。",
        ]
        for f in fixes:
            ctk.CTkLabel(scroll, text=f, font=ctk.CTkFont(size=12), justify="left",
                         wraplength=760).pack(anchor="w", padx=10, pady=3)

        # 注意事项
        ctk.CTkLabel(scroll, text="注意事项",
                     font=ctk.CTkFont(size=16, weight="bold")).pack(anchor="w", padx=10, pady=(20, 10))
        notes = [
            "Cookie 具有时效性，过期后需重新获取",
            "请勿将 Cookie 泄露给他人，否则他人可登录你的账号",
            "如遇登录失败，请先检查 Cookie 是否完整复制",
        ]
        for note in notes:
            ctk.CTkLabel(scroll, text=f"  {note}",
                        font=ctk.CTkFont(size=13), text_color="gray").pack(anchor="w", padx=10, pady=2)

    # ═══ 设置页 ═══════════════════════════════════════
    def _build_settings_page(self):
        page = ctk.CTkFrame(self.content_area, fg_color="transparent")
        self.pages["settings"] = page

        container = ctk.CTkFrame(page)
        container.pack(fill="x", padx=30, pady=30)

        # 语言
        ctk.CTkLabel(container, text="语言 / Language",
                     font=ctk.CTkFont(size=15, weight="bold")).pack(anchor="w", padx=20, pady=(20, 8))
        self.lang_menu = ctk.CTkOptionMenu(container, values=["中文", "English"], width=200,
                                           command=self._on_lang_change)
        self.lang_menu.pack(anchor="w", padx=20, pady=(0, 10))
        self.lang_menu.set("中文" if self.lang == "zh" else "English")

        # 外观
        ctk.CTkLabel(container, text="外观 / Theme",
                     font=ctk.CTkFont(size=15, weight="bold")).pack(anchor="w", padx=20, pady=(10, 8))
        self.theme_menu = ctk.CTkOptionMenu(container, values=["跟随系统", "浅色", "深色"], width=200,
                                            command=self._on_theme_change)
        self.theme_menu.pack(anchor="w", padx=20, pady=(0, 10))
        theme_labels = {"System": "跟随系统", "Light": "浅色", "Dark": "深色"}
        saved_appearance = self._config.get("appearance", "System")
        self.theme_menu.set(theme_labels.get(saved_appearance, "跟随系统"))

        # 关于
        ctk.CTkLabel(container, text="关于",
                     font=ctk.CTkFont(size=15, weight="bold")).pack(anchor="w", padx=20, pady=(10, 8))
        ctk.CTkLabel(container, text="当前版本: v3.5",
                     font=ctk.CTkFont(size=14), text_color="gray").pack(anchor="w", padx=20, pady=2)
        self.github_link = ctk.CTkButton(container, text="项目主页: github.com/xuebi0218/welearn-gui",
                                          font=ctk.CTkFont(size=13), fg_color="transparent",
                                          text_color="#3498db", hover_color=("gray80", "gray30"),
                                          anchor="w", height=28, width=320,
                                          command=self._on_open_github)
        self.github_link.pack(anchor="w", padx=15, pady=2)

        # 检查更新
        self.btn_update = ctk.CTkButton(container, text="检查更新", width=150, height=35,
                                        fg_color="#2980b9", hover_color="#1f6fa5",
                                        command=self._on_check_update)
        self.btn_update.pack(anchor="w", padx=20, pady=(15, 20))

    # ═══ 底部状态栏 ═══════════════════════════════════
    def _build_statusbar(self):
        self.status_frame = ctk.CTkFrame(self.root, height=40,
                                          fg_color=("#f1f5f9", "#0f172a"))
        self.status_frame.pack(side="bottom", fill="x", padx=0, pady=0)

        self.status_label = ctk.CTkLabel(self.status_frame, text="● 就绪",
                                          text_color=("#64748b", "#94a3b8"),
                                          font=ctk.CTkFont(size=12))
        self.status_label.pack(side="left", padx=15, pady=8)

        self.btn_stop = ctk.CTkButton(self.status_frame, text="⏹ 停止", width=80, height=30,
                                      fg_color="#ef4444", hover_color="#dc2626",
                                      corner_radius=6, font=ctk.CTkFont(size=12),
                                      command=self._on_stop, state="disabled")
        self.btn_stop.pack(side="right", padx=10, pady=5)

    # ═══ 工具方法 ═════════════════════════════════════
    def _setup_log_tags(self):
        try:
            self.log_text._textbox.tag_config("log_success", foreground="#27ae60")
            self.log_text._textbox.tag_config("log_error", foreground="#e74c3c")
            self.log_text._textbox.tag_config("log_warning", foreground="#f39c12")
        except Exception:
            pass

    def _log(self, text, tag=None):
        self.log_text.configure(state="normal")
        if tag:
            try:
                self.log_text._textbox.insert("end", text + "\n", tag)
            except Exception:
                self.log_text.insert("end", text + "\n")
        else:
            self.log_text.insert("end", text + "\n")
        self.log_text.see("end")
        self.log_text.configure(state="disabled")
        try:
            lines = int(self.log_text.index("end-1c").split(".")[0])
            if lines > 500:
                self.log_text.delete("1.0", f"{lines - 400}.0")
        except Exception:
            pass

    def _clear_log(self):
        self.log_text.configure(state="normal")
        self.log_text.delete("1.0", "end")
        self.log_text.configure(state="disabled")

    def _export_log(self):
        from tkinter import filedialog
        try:
            content = self.log_text.get("1.0", "end-1c")
        except Exception:
            return
        if not content.strip():
            self._log("日志为空，没什么可导出的", "log_warning")
            return
        path = filedialog.asksaveasfilename(
            defaultextension=".txt", filetypes=[("文本文件", "*.txt")],
            initialfile=time.strftime("welearn-log-%Y%m%d-%H%M.txt"))
        if not path:
            return
        try:
            with open(path, "w", encoding="utf-8") as f:
                f.write(content)
            self._log(f"日志已导出：{path}", "log_success")
        except Exception as e:
            self._log(f"导出失败：{e}", "log_error")

    def _set_running(self, running, status_text):
        self.running = running
        state = "disabled" if running else "normal"
        stop_state = "normal" if running else "disabled"
        self.btn_login.configure(state=state)
        self.btn_password_login.configure(state=state)
        self.btn_refresh.configure(state=state)
        self.course_menu.configure(state=state)
        self.unit_menu.configure(state=state)
        self.btn_start_task.configure(state=state)
        self.btn_stop.configure(state=stop_state, text="⏹ 停止")
        color = "#38bdf8" if running else ("#64748b", "#94a3b8")
        self.status_label.configure(text=f"● {status_text}", text_color=color)

    # ═══ 事件处理 ═════════════════════════════════════
    def _on_login_mode_change(self):
        if self.login_mode_var.get() == "cookie":
            self.login_mode = "cookie"
            self.password_panel.pack_forget()
            self.cookie_panel.pack(fill="x", padx=15, pady=(5, 5), before=self.login_status)
        else:
            self.login_mode = "password"
            self.cookie_panel.pack_forget()
            self.password_panel.pack(fill="x", padx=15, pady=(5, 5), before=self.login_status)

    def _on_login(self):
        if self.login_mode == "cookie":
            cookie = self.cookie_entry.get("1.0", "end-1c").strip()
            if not cookie:
                self.login_status.configure(text="请输入Cookie!", text_color="red")
                return
            self.login_cookie = cookie
            self._set_running(True, "正在验证Cookie...")
        else:
            username = self.username_entry.get().strip()
            password = self.password_entry.get().strip()
            if not username or not password:
                self.login_status.configure(text="请输入账号和密码!", text_color="red")
                return
            self.login_username = username
            self.login_password = password
            self._set_running(True, "正在登录...")
        threading.Thread(target=thread_login, args=(self,), daemon=True).start()

    def _on_course_selected(self, choice):
        for c in self.courses:
            if f'{c["per"]:>3}% {c["name"]}' == choice:
                self.selected_cid = str(c['cid'])
                self.uid = None
                self.classid = None
                self.units = []
                self.unit_menu.configure(values=["加载中..."])
                self.unit_menu.set("加载中...")
                threading.Thread(target=thread_fetch_units, args=(self, self.selected_cid), daemon=True).start()
                return

    def _on_unit_selected(self, choice):
        if choice == "0. 按顺序完成全部单元":
            self.selected_unit_idx = 0
        else:
            for idx, u in enumerate(self.units, 1):
                status = "[已开放]" if u.get('visible') == 'true' else "[未开放]"
                if f'{status} {u["unitname"]} {u["name"]}' == choice:
                    self.selected_unit_idx = idx
                    return

    def _on_rate_mode_change(self):
        if self.rate_var.get() == "fixed":
            self.fixed_rate_entry.configure(state="normal")
            self.rand_min_entry.configure(state="disabled")
            self.rand_max_entry.configure(state="disabled")
        else:
            self.fixed_rate_entry.configure(state="disabled")
            self.rand_min_entry.configure(state="normal")
            self.rand_max_entry.configure(state="normal")

    def _on_time_mode_change(self):
        if self.time_var.get() == "fixed":
            self.fixed_time_entry.configure(state="normal")
            self.time_min_entry.configure(state="disabled")
            self.time_max_entry.configure(state="disabled")
        else:
            self.fixed_time_entry.configure(state="disabled")
            self.time_min_entry.configure(state="normal")
            self.time_max_entry.configure(state="normal")

    def _on_refresh(self):
        self._set_running(True, "刷新课程列表...")
        threading.Thread(target=thread_refresh_courses, args=(self,), daemon=True).start()

    def _on_start_task(self):
        if not self.selected_cid or not self.uid:
            self._log("[!] 请先选择课程和单元", "log_error")
            return

        mode = self.task_mode_var.get()  # "curriculum" or "timeonly"

        try:
            # 并发路数：1~8
            try:
                want_threads = int(self.threads_entry.get())
            except (ValueError, AttributeError):
                want_threads = 4
            want_threads = max(1, min(8, want_threads))
            if str(want_threads) != self.threads_entry.get():
                self.threads_entry.delete(0, "end")
                self.threads_entry.insert(0, str(want_threads))

            # 时长参数（两种模式共用）
            if self.time_var.get() == "fixed":
                duration_val = int(self.fixed_time_entry.get())
                if mode == "curriculum":
                    self.curriculum_duration = duration_val
                else:
                    self.time_duration = duration_val
                    self.time_mode = 1
            else:
                lo, hi = int(self.time_min_entry.get()), int(self.time_max_entry.get())
                if lo > hi:
                    self._log("[!] 随机时长范围错误", "log_error")
                    return
                if mode == "curriculum":
                    self.curriculum_duration = [lo, hi]
                else:
                    self.time_duration = [lo, hi]
                    self.time_mode = 2

            # 时长范围校验
            for v in ([duration_val] if self.time_var.get() == "fixed" else [lo, hi]):
                if v < 30:
                    self._log("[!] 单课时时长至少 30 秒（更短必被平台判为异常）", "log_error")
                    return
                if v > 1500:
                    self._log("[!] 单课时时长最多 1500 秒（平台单页上限 30 分钟）", "log_error")
                    return

            # 并发路数（共用）
            max_threads = want_threads
            if max_threads > 4:
                self._log(f"[!] {max_threads} 路并行：完成密度明显高于真人，被平台注意的概率上升",
                          "log_warning")
            if mode == "curriculum":
                self.curriculum_max_threads = max_threads
            else:
                self.time_max_threads = max_threads

            # 正确率（仅刷课模式）
            if mode == "curriculum":
                if self.rate_var.get() == "fixed":
                    r = int(self.fixed_rate_entry.get())
                    if not 50 <= r <= 100:
                        self._log("[!] 正确率需在 50~100 之间", "log_error")
                        return
                    self.curriculum_rate = r
                    self.curriculum_random = False
                else:
                    lo, hi = int(self.rand_min_entry.get()), int(self.rand_max_entry.get())
                    if lo > hi:
                        self._log("[!] 随机正确率范围错误", "log_error")
                        return
                    self.curriculum_rate = [lo, hi]
                    self.curriculum_random = True
        except ValueError:
            self._log("[!] 输入格式错误", "log_error")
            return

        # 启动前确认：把"要跑多久"讲清楚
        try:
            if self.time_var.get() == "fixed":
                avg_dur = int(self.fixed_time_entry.get())
            else:
                avg_dur = (int(self.time_min_entry.get()) + int(self.time_max_entry.get())) // 2
        except ValueError:
            avg_dur = 720
        cap = self.daily_lesson_cap
        try:
            lanes = max(1, int(self.threads_entry.get()))
        except (ValueError, AttributeError):
            lanes = 1
        est_h = avg_dur * cap / 3600.0 / lanes
        msg = (f"本次最多处理 {cap} 个课时（单日上限），{lanes} 路并行\n"
               f"单课时按约 {avg_dur // 60} 分钟计算，满负荷约需 {est_h:.1f} 小时。\n\n"
               f"运行期间请保持窗口打开，可以最小化。\n"
               f"如果课时很多，建议分几天完成——一次性刷完更容易被平台隔天复核清掉。\n\n"
               f"现在开始吗？")
        if not messagebox.askyesno("确认开始", msg):
            return

        try:
            if self.time_var.get() == "fixed":
                self._avg_lesson_sec = int(self.fixed_time_entry.get())
            else:
                self._avg_lesson_sec = (int(self.time_min_entry.get()) + int(self.time_max_entry.get())) // 2
        except ValueError:
            self._avg_lesson_sec = 720

        self._log("─" * 55)
        self.stop_requested = False
        self.task_progress_bar.set(0)
        self.task_stats_label.configure(text="")

        if mode == "curriculum":
            dur = self.curriculum_duration
            dur_str = f"{dur}s" if isinstance(dur, int) else f"{dur[0]}~{dur[1]}s"
            rate = self.curriculum_rate
            rate_str = f"{rate}%" if isinstance(rate, int) else f"{rate[0]}~{rate[1]}%"
            self._log(f"📝 刷课并计时 | 正确率={rate_str} | 时长={dur_str} | 线程={max_threads}", "log_warning")
            self._set_running(True, "刷课进行中...")
            threading.Thread(target=thread_curriculum_execute, args=(self,), daemon=True).start()
        else:
            dur = self.time_duration
            dur_str = f"{dur}s" if isinstance(dur, int) else f"{dur[0]}~{dur[1]}s"
            self._log(f"⏱ 仅刷时长 | 时长={dur_str} | 线程={max_threads}", "log_warning")
            self._set_running(True, "刷时长进行中...")
            threading.Thread(target=thread_time_execute, args=(self,), daemon=True).start()

    def _on_close(self):
        """窗口关闭保护：运行中不允许直接关闭"""
        if self.running:
            self._log("[!] 任务运行中，请先点击底部「停止」按钮等待任务结束，再关闭窗口", "log_warning")
            return
        self.root.destroy()

    def _on_stop(self):
        self.stop_requested = True
        self.btn_stop.configure(state="disabled", text="⏳ 停止中...")
        self.status_label.configure(text="正在停止...", text_color="orange")
        mode = "刷课" if self.task_mode_var.get() == "curriculum" else "刷时长"
        self._log(f"[!] ⏹ 用户请求停止{mode}任务，正在等待当前操作完成...", "log_warning")
        self._log("[!] 提示：正在 sleep 的线程需要等待当前分段结束（最多5秒）", "log_warning")

    def _on_lang_change(self, choice):
        if choice == "中文":
            self.lang = "zh"
        else:
            self.lang = "en"
        self._save_prefs()
        self._refresh_labels()

    def _on_theme_change(self, choice):
        theme_map = {"跟随系统": "System", "浅色": "Light", "深色": "Dark"}
        mode = theme_map.get(choice, "System")
        ctk.set_appearance_mode(mode)
        self._save_prefs()

    def _on_open_github(self):
        import webbrowser
        webbrowser.open("https://github.com/xuebi0218/welearn-gui")

    def _on_check_update(self):
        self._log("检查更新中...")
        try:
            resp = requests.get(
                "https://api.github.com/repos/xuebi0218/welearn-gui/releases/latest",
                timeout=10)
            if resp.status_code == 200:
                latest = resp.json()["tag_name"]
                self._log(f"最新版本: {latest}，当前: v3.8")
            else:
                self._log("GitHub 仓库尚未设置，无法检查更新", "log_warning")
        except Exception:
            self._log("GitHub 仓库尚未设置，无法检查更新", "log_warning")

    def _refresh_labels(self):
        # 刷新导航标签（保留图标）
        labels = {"home": ("🏠  主页", "🏠  Home"),
                  "donate": ("☕  赞助", "☕  Donate"),
                  "help": ("📖  帮助", "📖  Help"),
                  "settings": ("⚙️  设置", "⚙️  Settings")}
        for key, (zh, en) in labels.items():
            self.nav_buttons[key].configure(text=zh if self.lang == "zh" else en)
        self.root.title("Welearn 刷课工具 v3.8" if self.lang == "zh" else "Welearn Tool v3.8")

    def _show_disclaimer(self):
        dialog = ctk.CTkToplevel(self.root)
        dialog.title("免责声明")
        dialog.geometry("550x420")
        dialog.resizable(False, False)
        dialog.transient(self.root)
        dialog.grab_set()
        dialog.update_idletasks()
        rx, ry = self.root.winfo_x(), self.root.winfo_y()
        rw, rh = self.root.winfo_width(), self.root.winfo_height()
        dw, dh = 550, 420
        dialog.geometry(f"+{rx + (rw - dw) // 2}+{ry + (rh - dh) // 2}")

        ctk.CTkLabel(dialog, text="Welearn 刷课工具",
                     font=ctk.CTkFont(size=20, weight="bold")).pack(pady=(25, 5))
        ctk.CTkLabel(dialog, text="v3.8 · 免费开源", text_color="gray").pack(pady=(0, 20))
        ctk.CTkFrame(dialog, height=1, fg_color="gray").pack(fill="x", padx=40, pady=(0, 15))

        ctk.CTkLabel(dialog, text="本软件完全免费，仅供学习交流使用。\n\n"
                     "1. 严禁任何形式的倒卖、商用行为\n"
                     "2. 如您通过付费渠道获得本软件，请立即退款并举报\n"
                     "3. 请合理使用本工具，由此产生的一切后果\n    由使用者自行承担\n"
                     "4. 本软件开源，欢迎监督和贡献",
                     font=ctk.CTkFont(size=14), justify="left", wraplength=450).pack(pady=(0, 15))

        self.disclaimer_skip = ctk.BooleanVar(value=False)

        def _on_disclaimer_close():
            if self.disclaimer_skip.get():
                self._config["disclaimer_skip"] = True
                _save_config(self._config)
            dialog.destroy()

        ctk.CTkCheckBox(dialog, text="下次不再显示", variable=self.disclaimer_skip,
                        font=ctk.CTkFont(size=12)).pack(pady=(0, 15))
        ctk.CTkButton(dialog, text="同意并继续", height=38, width=200,
                      fg_color="#27ae60", hover_color="#1e8449",
                      command=_on_disclaimer_close).pack(pady=(0, 10))
        self.root.wait_window(dialog)

    # ═══ 消息处理 ═════════════════════════════════════
    def _poll_queue(self):
        try:
            while True:
                try:
                    msg = self.message_queue.get_nowait()
                except queue.Empty:
                    break
                try:
                    self._handle_message(msg)
                except Exception as e:      # 单条消息出错不影响后续消息
                    try:
                        self._log(f"[界面] 消息处理异常: {e}", "log_error")
                    except Exception:
                        pass
        finally:
            self.root.after(100, self._poll_queue)

    def _handle_message(self, msg):
        t = msg["type"]
        if t in ("log", "log_success", "log_error", "log_warning"):
            self._log(msg["text"], t if t != "log" else None)
        elif t == "login_success":
            self.courses = msg["courses"]
            self._populate_course_menu()
            self.login_status.configure(text=f"登录成功 - {len(self.courses)}门课程", text_color="#27ae60")
            self._log(f"登录成功！共 {len(self.courses)} 门课程")
            self.course_frame.pack(fill="x", padx=10, pady=5, after=self.login_frame)
            self.btn_refresh.configure(state="normal")
            self._set_running(False, "就绪")
        elif t == "refresh_fail":
            self._log(f"刷新失败: {msg.get('error', '')}", "log_error")
            self._set_running(False, "就绪")
        elif t == "login_fail":
            self.login_status.configure(text=f"登录失败: {msg['error']}", text_color="#e74c3c")
            self._log(f"登录失败: {msg['error']}", "log_error")
            self._set_running(False, "就绪")
        elif t == "units_loaded":
            self.uid, self.classid, self.units = msg["uid"], msg["classid"], msg["units"]
            self._populate_unit_menu()
            self._log(f"获取单元成功，共 {len(self.units)} 个单元")
        elif t == "progress":
            current, total = msg["current"], msg["total"]
            remaining = total - current
            ratio = current / total if total > 0 else 0
            self.task_progress_bar.set(ratio)
            if ratio >= 1.0:
                self.task_progress_label.configure(text=f"✅ 全部完成！共 {total} 个课时已处理", text_color="#27ae60")
            elif ratio > 0:
                avg = getattr(self, "_avg_lesson_sec", 720)
                eta_min = int(remaining * avg / 60)
                eta = f"{eta_min} 分钟" if eta_min < 90 else f"{eta_min/60:.1f} 小时"
                self.task_progress_label.configure(
                    text=f"⏳ 进度: {current}/{total} | 剩余 {remaining} 个 | 预计还需约 {eta}",
                    text_color="#38bdf8")
            else:
                self.task_progress_label.configure(text=f"📊 进度: {current}/{total} | 待处理 {remaining} 个")
        elif t == "curriculum_complete":
            total = msg['way1_ok'] + msg['way1_fail']
            self.task_stats_label.configure(
                text=f"共 {total} 节 | 方式1 成功:{msg['way1_ok']} 失败:{msg['way1_fail']} | "
                     f"方式2 成功:{msg['way2_ok']} 失败:{msg['way2_fail']}")
            if msg["stopped"]:
                self._log(f"⚠️ 刷课已停止 | 已完成 {msg['way1_ok']+msg['way2_ok']} 次提交", "log_warning")
            else:
                self._log("─" * 55)
                self._log(f"🎉 刷课全部完成！共 {total} 节 | 成功 {msg['way1_ok']+msg['way2_ok']} 次", "log_success")
            self._set_running(False, "就绪")
        elif t == "task_finished":
            # 无论成功/异常，线程都发这个，保证控件不会永久灰掉
            if self.running:
                self._set_running(False, "就绪")
        elif t == "time_complete":
            self.task_stats_label.configure(text=f"完成 | 错误: {msg['errors']} 个")
            if msg["stopped"]:
                self._log(f"⚠️ 刷时长已停止 | 错误 {msg['errors']} 个", "log_warning")
            else:
                self._log("─" * 55)
                self._log(f"🎉 刷时长全部完成！错误 {msg['errors']} 个", "log_success")
            self._set_running(False, "就绪")

    def _populate_course_menu(self):
        values = [f'{c["per"]:>3}% {c["name"]}' for c in self.courses]
        self.course_menu.configure(values=values)
        if values:
            self.course_menu.set(values[0])
            self._on_course_selected(values[0])

    def _populate_unit_menu(self):
        values = ["0. 按顺序完成全部单元"]
        for u in self.units:
            status = "[已开放]" if u.get('visible') == 'true' else "[未开放]"
            values.append(f'{status} {u["unitname"]} {u["name"]}')
        self.unit_menu.configure(values=values)
        self.unit_menu.set(values[0])
        self.selected_unit_idx = 0

    def run(self):
        self.root.mainloop()


# ── 入口 ───────────────────────────────────────────────
if __name__ == "__main__":
    app = WelearnApp()
    app.run()
