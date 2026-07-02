# -*- coding: utf-8 -*-
"""
Welearn 刷课工具 GUI v3.5
整合刷课模式和刷时长模式，使用 CustomTkinter 构建界面。
v3.2: 新增题目解析和答题记录提交功能。
v3.3: 修复章节学习时长为0的bug，刷课模式支持多线程并发+真实学习时长。
v3.4: 修复刷时长模式心跳未触发导致时长不增长的bug。
v3.5: 修复最后一项卡住问题(join超时类型错误)、停止按钮即时响应(分段sleep+轮询join)、增强日志输出。
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

# ── 常量 ──────────────────────────────────────────────
# 多 User-Agent 轮换池，降低指纹识别风险
_USER_AGENTS = [
    # Chrome (Windows)
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/129.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/127.0.0.0 Safari/537.36',
    # Edge (Chromium)
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36 Edg/131.0.0.0',
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36 Edg/130.0.0.0',
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/129.0.0.0 Safari/537.36 Edg/129.0.0.0',
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36 Edg/128.0.0.0',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36 Edg/131.0.0.0',
    # Firefox (Windows)
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:134.0) Gecko/20100101 Firefox/134.0',
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:133.0) Gecko/20100101 Firefox/133.0',
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:132.0) Gecko/20100101 Firefox/132.0',
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:128.0) Gecko/20100101 Firefox/128.0',
    # Firefox (macOS)
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:134.0) Gecko/20100101 Firefox/134.0',
    # Safari (macOS)
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.2 Safari/605.1.15',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.1 Safari/605.1.15',
    # Opera (Windows)
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36 OPR/116.0.0.0',
]


def _random_ua():
    """随机返回一个 User-Agent"""
    return _USER_AGENTS[random.randint(0, len(_USER_AGENTS) - 1)]


def _rand_delay(base_sec, jitter_pct=0.3):
    """在 base ± jitter_pct% 范围内随机延迟（秒）"""
    lo = base_sec * (1 - jitter_pct)
    hi = base_sec * (1 + jitter_pct)
    return lo + (hi - lo) * random.random()


def _build_headers(referer=None, extra=None):
    """构建带随机 User-Agent 的请求头，模拟真实浏览器"""
    h = {
        'User-Agent': _random_ua(),
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8',
        'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
        'Accept-Encoding': 'gzip, deflate, br',
        'Cache-Control': 'max-age=0',
        'Sec-Fetch-Dest': 'document',
        'Sec-Fetch-Mode': 'navigate',
        'Sec-Fetch-Site': 'cross-site',
        'Sec-Fetch-User': '?1',
        'Upgrade-Insecure-Requests': '1',
        'sec-ch-ua': '"Google Chrome";v="131", "Chromium";v="131", "Not_A Brand";v="24"',
        'sec-ch-ua-mobile': '?0',
        'sec-ch-ua-platform': '"Windows"',
    }
    if referer:
        h['Referer'] = referer
        ref_host = urlparse(referer).netloc
        h['Sec-Fetch-Site'] = 'same-origin'
    if extra:
        h.update(extra)
    return h


AJAX_SCO_URL = "https://welearn.sflep.com/Ajax/SCO.aspx"
AJAX_STUDYSTAT_URL = "https://welearn.sflep.com/ajax/StudyStat.aspx"
AJAX_AUTHCOURSE_URL = "https://welearn.sflep.com/ajax/authCourse.aspx"
COURSE_INFO_URL = "https://welearn.sflep.com/student/course_info.aspx"

# 图片资源路径（打包后从 exe 内部读取，源码运行从同目录读取）
import os as _os
_SRC_DIR = _os.path.dirname(_os.path.abspath(__file__))
if getattr(sys, 'frozen', False):
    _DONATE_QR_PATH = _os.path.join(sys._MEIPASS, 'src', 'donate_qr.jpg')
    _NOBI_PATH = _os.path.join(sys._MEIPASS, 'src', 'nobi.png')
else:
    _DONATE_QR_PATH = _os.path.join(_SRC_DIR, 'donate_qr.jpg')
    _NOBI_PATH = _os.path.join(_SRC_DIR, 'nobi.png')


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

    if '\"clist\":[]}' in resp.text or '错误' in resp.text:
        return False, "Cookie无效或已过期"

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
        if "我的主页" in resp.text or '/student/' in resp.url:
            return _verify_login(session)

        # 检查是否登录失败还留在 SSO
        if 'sso.sflep.com' in resp.url and 'Account/Login' in resp.url:
            return False, "账号或密码错误，请重试"

        # 兜底验证
        resp = session.get('https://welearn.sflep.com/student/index.aspx',
                          headers=_build_headers(sso_origin), timeout=15)
        if "我的主页" in resp.text:
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
    if '\"clist\":[]}' in resp.text or '错误' in resp.text:
        return False, "登录成功但未找到课程"
    courses = resp.json()["clist"]
    return True, courses


def welearn_get_course_info(session, cid):
    """
    从课程详情页提取 uid 和 classid。
    返回 (uid: str, classid: str)，失败抛出 ValueError。
    """
    resp = session.get(COURSE_INFO_URL + f"?cid={cid}",
                      headers=_build_headers('https://welearn.sflep.com/student/index.aspx'),
                      timeout=15)

    uid_match = re.search(r'"uid":\s*(\d+)', resp.text)
    classid_match = re.search(r'"classid":"(.*?)"', resp.text)
    if not uid_match or not classid_match:
        raise ValueError(f"无法从课程页面提取uid/classid，页面结构可能已更新。\n页面前500字符:\n{resp.text[:500]}")
    return uid_match.group(1), classid_match.group(1)


def welearn_get_units(session, cid, uid):
    """
    获取课程的单元列表。
    返回 [{"unitname":..., "name":..., "visible":...}, ...]
    """
    resp = session.get(AJAX_STUDYSTAT_URL,
                       params={'action': 'courseunits', 'cid': cid, 'uid': uid},
                       headers=_build_headers('https://welearn.sflep.com/student/course_info.aspx'),
                       timeout=15)
    return resp.json()['info']


def welearn_get_lessons(session, cid, uid, unitidx, classid):
    """
    获取某单元下的小节列表（scoLeaves）。
    返回 [{"id":..., "location":..., "isvisible":..., "iscomplete":..., "learntime":...}, ...]
    """
    resp = session.get(AJAX_STUDYSTAT_URL,
                       params={'action': 'scoLeaves', 'cid': cid, 'uid': uid,
                               'unitidx': unitidx, 'classid': classid},
                       headers=_build_headers(COURSE_INFO_URL + f"?cid={cid}"),
                       timeout=15)
    if "异常" in resp.text or "出错了" in resp.text:
        return None
    return resp.json()['info']


def welearn_curriculum_submit(session, cid, uid, classid, scoid, crate, learntime=0, stop_check=None):
    """
    刷课模式：提交一个小节的完成数据（v3.2: 带答题记录）。
    执行 scoAddr → 解析题目 → startsco160928 → sleep(learntime) → setscoinfo → savescoinfo160928
    learntime: 学习时长（秒），0 表示不等待（兼容旧行为）
    stop_check: 可选回调，返回 True 表示用户请求停止，用于分段 sleep 中及时响应
    返回 (way1_success: bool, way2_success: bool, questions_found: int)
    """
    referer = f"https://welearn.sflep.com/Student/StudyCourse.aspx?cid={cid}&classid={classid}&sco={scoid}"

    # ── 0. 尝试获取 SCO 模板并解析题目 ──
    questions = []
    try:
        template_url, err = welearn_get_sco_addr(session, cid, scoid)
        if template_url:
            html = _fetch_sco_template(session, template_url)
            if html:
                questions = parse_sco_questions(html)
    except Exception:
        pass  # 解析失败不影响主流程，退化为空 interactions

    crate_int = int(crate) if crate.isdigit() else 100

    if questions:
        interactions_json, interactions_info = generate_interactions(questions, crate_int)
    else:
        interactions_json, interactions_info = [], ''

    # ── 构造提交数据 ──
    data_obj = {
        "cmi": {
            "completion_status": "completed",
            "interactions": interactions_json,
            "launch_data": "",
            "progress_measure": "1",
            "score": {"scaled": str(crate_int), "raw": "100"},
            "session_time": str(learntime),
            "success_status": "unknown",
            "total_time": str(learntime),
            "mode": "normal"
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
                "play": {"offline_media_id": "9999"}
            },
            "retry_count": "0",
            "submit_time": ""
        }
    }
    data_str = json.dumps(data_obj, ensure_ascii=False)
    full_data = data_str + '[INTERACTIONINFO]' + interactions_info

    # ── 第1步：开始 SCO ──
    session.post(AJAX_SCO_URL,
                 data={"action": "startsco160928", "cid": cid, "scoid": scoid, "uid": uid},
                 headers=_build_headers(referer), timeout=15)

    # ★ 等待学习时长，让服务端计时（v3.3: 修复章节时长为0的问题）
    # v3.5: 分段 sleep，每5秒检查停止请求，避免长时间无法响应
    if learntime > 0:
        chunk = 5  # 每5秒检查一次停止标志
        slept = 0
        while slept < learntime:
            if stop_check and stop_check():
                return False, False, len(questions)  # 用户停止，提前退出
            wait = min(chunk, learntime - slept)
            time.sleep(wait)
            slept += wait
    else:
        time.sleep(_rand_delay(0.2, 0.5))

    # ── 第2步：提交 SCORM 数据（含 interactions） ──
    resp1 = session.post(AJAX_SCO_URL,
                         data={"action": "setscoinfo", "cid": cid, "scoid": scoid,
                               "uid": uid, "data": full_data, "isend": "False"},
                         headers=_build_headers(referer), timeout=15)
    way1_ok = '"ret":0' in resp1.text

    time.sleep(_rand_delay(0.3, 0.4))

    # ── 第3步：保存进度 ──
    resp2 = session.post(AJAX_SCO_URL,
                         data={"action": "savescoinfo160928", "cid": cid, "scoid": scoid,
                               "uid": uid, "progress": "100", "crate": str(crate_int),
                               "status": "unknown", "cstatus": "completed", "trycount": "0",
                               "session_time": str(learntime),
                               "total_time": str(learntime)},
                         headers=_build_headers(referer), timeout=15)
    way2_ok = '"ret":0' in resp2.text

    return way1_ok, way2_ok, len(questions)


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


def welearn_time_heartbeat(session, cid, uid, scoid, session_time, total_time):
    """刷时长模式：发送心跳包保持在线"""
    resp = session.post(AJAX_SCO_URL,
                        data={'action': 'keepsco_with_getticket_with_updatecmitime',
                              'uid': uid, 'cid': cid, 'scoid': scoid,
                              'session_time': session_time, 'total_time': total_time},
                        headers=_build_headers('https://welearn.sflep.com/student/StudyCourse.aspx'),
                        timeout=15)
    return '"ret":0' in resp.text


def welearn_time_finalize(session, cid, uid, scoid, progress, crate, cstatus,
                          session_time, total_time):
    """刷时长模式：保存最终学习数据（含累加后的学习时间）"""
    resp = session.post(AJAX_SCO_URL,
                        data={'action': 'savescoinfo160928', 'cid': cid, 'scoid': scoid,
                              'uid': uid, 'progress': progress, 'crate': crate,
                              'status': 'unknown', 'cstatus': cstatus, 'trycount': '0',
                              'session_time': session_time, 'total_time': total_time},
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
        if '\"clist\":[]}' in resp.text or '错误' in resp.text:
            app.message_queue.put({"type": "log_error", "text": "会话已过期，请重新登录"})
            return
        courses = resp.json()["clist"]
        app.message_queue.put({"type": "login_success", "courses": courses})
    except Exception as e:
        app.message_queue.put({"type": "log_error", "text": f"刷新课程失败: {e}"})


def thread_fetch_units(app, cid):
    """后台线程：获取课程的 uid/classid 和单元列表"""
    try:
        app.message_queue.put({"type": "log", "text": "获取单元信息中..."})
        uid, classid = welearn_get_course_info(app.session, cid)
        units = welearn_get_units(app.session, cid, uid)
        app.message_queue.put({"type": "units_loaded", "uid": uid, "classid": classid, "units": units})
    except Exception as e:
        app.message_queue.put({"type": "log_error", "text": f"获取单元失败: {e}"})


def thread_curriculum_execute(app):
    """后台线程：执行刷课模式（v3.3: 多线程并发 + 真实学习时长）"""
    cid = app.selected_cid
    uid = app.uid
    classid = app.classid
    unitidx = app.selected_unit_idx
    mycrate = app.curriculum_rate
    randommode = app.curriculum_random
    duration = app.curriculum_duration
    random_duration = isinstance(duration, list)
    max_threads = max(1, app.curriculum_max_threads)

    stats_lock = threading.Lock()
    way1_ok = way1_fail = way2_ok = way2_fail = 0

    if unitidx == 0:
        unit_start, unit_end = 0, 999
    else:
        unit_start = unitidx - 1
        unit_end = unitidx

    # 统计总数
    all_lessons = []
    for i in range(unit_start, unit_end):
        if app.stop_requested:
            break
        lessons = welearn_get_lessons(app.session, cid, uid, i, classid)
        if lessons is None:
            break
        for c in lessons:
            if c['isvisible'] != 'false' and "未" in c.get('iscomplete', ''):
                all_lessons.append((i, c))

    total = len(all_lessons)
    app.message_queue.put({"type": "progress", "current": 0, "total": total})
    dur_label = f"{duration[0]}~{duration[1]}s" if random_duration else f"{duration}s"
    app.message_queue.put({"type": "log_warning", "text": f"📝 刷课任务启动 | 共 {total} 个小节待完成 | 时长={dur_label} | 线程={max_threads}"})
    app.message_queue.put({"type": "log_warning", "text": "📌 请耐心等待，不要关闭窗口！"})

    if total == 0:
        app.message_queue.put({"type": "log", "text": "没有需要完成的小节。"})
        app.message_queue.put({"type": "curriculum_complete",
                               "way1_ok": 0, "way1_fail": 0,
                               "way2_ok": 0, "way2_fail": 0,
                               "stopped": False})
        return

    processed = [0]  # 用 list 包装以在闭包中可修改

    # 分批多线程处理
    for batch_start in range(0, total, max_threads):
        if app.stop_requested:
            app.message_queue.put({"type": "log_warning", "text": "⚠️ 用户停止了任务"})
            break

        batch = all_lessons[batch_start:batch_start + max_threads]
        threads_list = []

        def process_one(unit_i, course):
            nonlocal way1_ok, way1_fail, way2_ok, way2_fail
            if app.stop_requested:
                return
            loc = course["location"]
            scoid = course["id"]

            try:
                if randommode:
                    crate = str(random.randint(mycrate[0], mycrate[1]))
                else:
                    crate = str(mycrate)

                if random_duration:
                    dur = random.randint(duration[0], duration[1])
                else:
                    dur = duration

                app.message_queue.put({"type": "log", "text": f'[刷课] {loc} → 正确率{crate}% 时长{dur}s 开始...'})

                w1, w2, q_count = welearn_curriculum_submit(
                    app.session, cid, uid, classid, scoid, crate, learntime=dur,
                    stop_check=lambda: app.stop_requested)

                if not w1 and not w2:
                    app.message_queue.put({"type": "log_warning", "text": f'  [停止] {loc} - 用户中断'})

                if q_count > 0:
                    app.message_queue.put({"type": "log", "text": f'  解析到 {q_count} 道题，已生成答题记录'})

                with stats_lock:
                    if w1:
                        way1_ok += 1
                    else:
                        way1_fail += 1
                    if w2:
                        way2_ok += 1
                    else:
                        way2_fail += 1

                status = f'正确率:{crate:>3}%  方式1:{"成功" if w1 else "失败"}  方式2:{"成功" if w2 else "失败"}'
                tag = "log_success" if (w1 and w2) else "log_error"
                app.message_queue.put({"type": tag, "text": status})

                processed[0] += 1
                app.message_queue.put({"type": "progress", "current": processed[0], "total": total})
            except Exception as e:
                app.message_queue.put({"type": "log_error", "text": f'  ✗ [异常] {loc} - {e}'})
                with stats_lock:
                    way1_fail += 1
                    way2_fail += 1

        # 计算本批次最长时长（用于 join 超时和日志）
        batch_durs = []
        for unit_i, course in batch:
            if random_duration:
                batch_durs.append(random.randint(duration[0], duration[1]))
            else:
                batch_durs.append(duration)
        batch_max_dur = max(batch_durs)

        batch_num = batch_start // max_threads + 1
        total_batches = (total + max_threads - 1) // max_threads
        app.message_queue.put({"type": "log", "text": f'━━━ 批次 {batch_num}/{total_batches} | {len(batch)}个任务 | 最长{batch_max_dur}s ━━━'})

        for idx, (unit_i, course) in enumerate(batch):
            t = threading.Thread(target=process_one, args=(unit_i, course))
            t.daemon = True
            t.start()
            threads_list.append((t, course, batch_durs[idx]))
            time.sleep(_rand_delay(0.1, 0.5))  # 线程启动错开

        # v3.5: 轮询等待，每1秒检查停止标志，可即时响应
        batch_deadline = time.time() + batch_max_dur + 30
        for t, course, dur in threads_list:
            loc = course["location"]
            while t.is_alive():
                if app.stop_requested:
                    app.message_queue.put({"type": "log_warning", "text": f'  ⏹ 停止请求：等待 {loc} 线程结束...'})
                remaining = batch_deadline - time.time()
                if remaining <= 0:
                    app.message_queue.put({"type": "log_warning", "text": f'  ⚠ {loc} 超时（>{batch_max_dur+30}s），跳过等待'})
                    break
                t.join(timeout=min(1.0, remaining))
            else:
                continue  # 线程正常结束
            # 超时：线程仍在运行，跳过
            if t.is_alive():
                app.message_queue.put({"type": "log_error", "text": f'  ✗ {loc} 未在预期时间内完成，已跳过'})

        # 批次完成统计
        remaining = total - processed[0]
        est_sec = remaining * batch_max_dur // max(max_threads, 1) if remaining > 0 else 0
        app.message_queue.put({"type": "log", "text": f'✅ 批次 {batch_num}/{total_batches} 完成 | 进度 {processed[0]}/{total} | 剩余 {remaining} 个 | 预计还需约 {est_sec} 秒'})
        time.sleep(_rand_delay(0.3, 0.5))  # 批次间短暂间隔

    app.message_queue.put({"type": "curriculum_complete",
                           "way1_ok": way1_ok, "way1_fail": way1_fail,
                           "way2_ok": way2_ok, "way2_fail": way2_fail,
                           "stopped": app.stop_requested})


def thread_time_execute(app):
    """后台线程：执行刷时长模式"""
    cid = app.selected_cid
    uid = app.uid
    classid = app.classid
    unitidx = app.selected_unit_idx
    inputtime = app.time_duration
    mode = app.time_mode  # 1=固定, 2=随机
    max_threads = app.time_max_threads

    if unitidx == 0:
        unit_start, unit_end = 0, 999
    else:
        unit_start = unitidx - 1
        unit_end = unitidx

    errors = []
    processed_lessons = 0

    # 第一遍：统计总数（含已完成/未完成统计）
    all_lessons = []
    already_done = 0
    for i in range(unit_start, unit_end):
        if app.stop_requested:
            break
        lessons = welearn_get_lessons(app.session, cid, uid, i, classid)
        if lessons is None:
            break
        for c in lessons:
            if c.get('isvisible', 'true') != 'false':
                all_lessons.append((i, c))
                if "已" in c.get('iscomplete', '') and "未" not in c.get('iscomplete', ''):
                    already_done += 1

    total = len(all_lessons)
    to_do = total - already_done
    app.message_queue.put({"type": "progress", "current": 0, "total": total})
    dur_str = f"{inputtime[0]}~{inputtime[1]}s" if mode == 2 else f"{inputtime}s"
    app.message_queue.put({"type": "log_warning", "text": f"⏱ 刷时长任务启动 | 共 {total} 个课时 | 已完成 {already_done} | 待处理 {to_do}"})
    app.message_queue.put({"type": "log_warning", "text": "📌 请耐心等待，不要关闭窗口！每个课时需要 60~120 秒"})

    for lesson_idx in range(0, len(all_lessons), max_threads):
        if app.stop_requested:
            app.message_queue.put({"type": "log_warning", "text": f"⚠️ 用户停止了任务 | 已处理 {processed_lessons}/{total} | 剩余 {total - processed_lessons} 个未处理"})
            break

        batch = all_lessons[lesson_idx:lesson_idx + max_threads]

        if mode == 2:
            durations = [random.randint(inputtime[0], inputtime[1]) for _ in batch]
        else:
            durations = [inputtime for _ in batch]

        max_duration = max(durations)
        threads_list = []

        def process_one(unit_i, course, learntime):
            if app.stop_requested:
                return
            loc = course["location"]
            scoid = course["id"]
            app.message_queue.put({"type": "log", "text": f'[刷时长] {loc} → +{learntime}秒 开始...'})

            try:
                cmi = welearn_time_init(app.session, cid, uid, scoid)
                if cmi is None:
                    app.message_queue.put({"type": "log_error", "text": f'  [失败] {loc} - 初始化学习数据失败'})
                    errors.append(loc)
                    return

                # 解析历史累计时间（秒），用于累加
                try:
                    init_total = int(cmi['total_time'])
                except (ValueError, TypeError):
                    init_total = 0

                # 1. 初始心跳：注册会话开始，让服务端开始计时（对齐旧版行为）
                welearn_time_heartbeat(app.session, cid, uid, scoid,
                                       "0", str(init_total))

                # 2. 随机化心跳间隔（30~40秒），缩短间隔确保短课时也能触发心跳
                next_heartbeat = random.randint(30, 40)
                elapsed = 0
                heartbeat_count = 0
                for t in range(learntime):
                    if app.stop_requested:
                        app.message_queue.put({"type": "log_warning", "text": f'  [停止] {loc} - 用户中断于 {t}s/{learntime}s'})
                        return
                    time.sleep(_rand_delay(1.0, 0.15))  # 1秒 ± 15% 抖动
                    elapsed = t + 1  # 本次会话已过时间（秒）
                    if elapsed >= next_heartbeat:
                        welearn_time_heartbeat(app.session, cid, uid, scoid,
                                               str(elapsed),
                                               str(init_total + elapsed))
                        heartbeat_count += 1
                        next_heartbeat = elapsed + random.randint(30, 40)

                # 3. 结束前最后一次心跳：告知服务端最终时间
                welearn_time_heartbeat(app.session, cid, uid, scoid,
                                       str(elapsed), str(init_total + elapsed))
                heartbeat_count += 1

                ok = welearn_time_finalize(app.session, cid, uid, scoid,
                                           cmi['progress'], cmi['crate'], cmi['cstatus'],
                                           str(elapsed), str(init_total + elapsed))
                if ok:
                    app.message_queue.put({"type": "log_success", "text": f'  [完成] {loc} (+{elapsed}s, {heartbeat_count}次心跳, 累计{init_total+elapsed}s)'})
                else:
                    app.message_queue.put({"type": "log_error", "text": f'  [失败] {loc} - 保存失败 (+{elapsed}s)'})
                    errors.append(loc)
            except Exception as e:
                app.message_queue.put({"type": "log_error", "text": f'  [异常] {loc} - {e}'})
                errors.append(loc)

        # 启动本批次所有线程（错开启动，避免瞬时并发高峰）
        batch_num = lesson_idx // max_threads + 1
        total_batches = (len(all_lessons) + max_threads - 1) // max_threads
        app.message_queue.put({"type": "log", "text": f'━━━ 批次 {batch_num}/{total_batches} | {len(batch)}个课时 | 最长{max_duration}s ━━━'})

        for idx, (unit_i, course) in enumerate(batch):
            t = threading.Thread(target=process_one, args=(unit_i, course, durations[idx]))
            t.daemon = True
            t.start()
            threads_list.append((t, course))
            time.sleep(_rand_delay(0.1, 0.5))  # 线程启动错开

        # v3.5: 轮询等待，每1秒检查停止标志
        batch_deadline = time.time() + max_duration + 10
        for t, course in threads_list:
            loc = course["location"]
            while t.is_alive():
                if app.stop_requested:
                    app.message_queue.put({"type": "log_warning", "text": f'  ⏹ 停止请求：等待 {loc} 线程结束...'})
                remaining = batch_deadline - time.time()
                if remaining <= 0:
                    app.message_queue.put({"type": "log_warning", "text": f'  ⚠ {loc} 超时（>{max_duration+10}s），跳过等待'})
                    break
                t.join(timeout=min(1.0, remaining))
            else:
                continue  # 线程正常结束
            if t.is_alive():
                app.message_queue.put({"type": "log_error", "text": f'  ✗ {loc} 未在预期时间内完成，已跳过'})

        processed_lessons += len(batch)
        remaining = len(all_lessons) - processed_lessons
        est_sec = remaining * (sum(durations) // len(durations)) // max_threads
        app.message_queue.put({"type": "progress", "current": processed_lessons, "total": len(all_lessons)})
        app.message_queue.put({"type": "log", "text": f"✅ 批次完成 | 进度 {processed_lessons}/{len(all_lessons)} | 剩余 {remaining} 个 | 预计还需约 {est_sec} 秒"})
        time.sleep(_rand_delay(0.5, 0.6))  # 批次间随机间隔

    app.message_queue.put({"type": "time_complete", "errors": len(errors), "stopped": app.stop_requested})


# ── 国际化文本 ────────────────────────────────────────
T = {
    "zh": {
        "app_title": "Welearn 刷课工具 v3.5",
        "nav_home": "主页",
        "nav_donate": "赞助",
        "nav_help": "帮助",
        "nav_settings": "设置",
        "status_ready": "● 就绪",
        "status_stopping": "正在停止...",
        "btn_stop": "停止",
        "btn_donate": "赞赏",
        "disclaimer_title": "免责声明",
        "donate_title": "支持作者",
        "donate_desc": "此程序为免费开源项目\n如果你付了钱，请立刻退款！\n\n如果喜欢本项目\n可以微信赞赏送作者一杯咖啡 ☕\n\n你的支持就是作者开发维护的动力",
        "donate_qr_hint": "微信扫码即可赞赏",
        "donate_later": "下次一定",
        "settings_lang": "语言",
        "settings_theme": "外观",
        "settings_theme_system": "跟随系统",
        "settings_theme_light": "浅色",
        "settings_theme_dark": "深色",
        "settings_about": "关于",
        "settings_version": "当前版本: v3.5",
        "settings_github": "项目主页",
        "settings_update": "检查更新",
        "settings_update_none": "已是最新版本",
        "settings_update_err": "检查更新失败",
        "help_title": "Cookie 获取教程",
        "help_step1": "1. 登录 welearn 网页版，按 F12 打开开发者工具",
        "help_step2": "2. 点击顶部的 Network（网络）选项卡",
        "help_step3": "3. 按 F5 刷新页面",
        "help_step4": "4. 在左侧列表找到第一个请求并点击",
        "help_step5": "5. 在右侧找到 Request Headers 中的 Cookie 字段",
        "help_step6": "6. 复制完整的 Cookie 值，粘贴到软件中",
        "help_note": "注意：Cookie 具有时效性，过期后需重新获取。请勿将 Cookie 泄露给他人。",
        "login_title": "登录方式",
        "login_cookie": "Cookie 登录（推荐）",
        "login_password": "账号密码登录（实验性）",
        "login_cookie_placeholder": "在此粘贴浏览器复制的Cookie字符串...",
        "login_username_placeholder": "账号",
        "login_password_placeholder": "密码",
        "login_btn": "登录",
        "login_status_none": "未登录",
        "select_course": "选择课程:",
        "select_unit": "选择单元:",
        "btn_refresh": "刷新",
        "unit_all": "0. 按顺序完成全部单元",
        "tab_curriculum": "刷课模式",
        "tab_time": "刷时长模式",
        "rate_title": "正确率设置",
        "rate_fixed": "固定正确率:",
        "rate_random": "随机正确率:",
        "time_title": "时长设置",
        "time_fixed": "固定时长:",
        "time_random": "随机时长:",
        "time_threads": "最大线程数:",
        "time_unit_sec": "秒",
        "btn_start_curriculum": "开始刷课",
        "btn_start_time": "开始刷时长",
        "log_title": "运行日志",
        "progress": "进度:",
        "agree_continue": "同意并继续",
        "skip_next": "下次不再显示",
        "disclaimer_body": "本软件完全免费，仅供学习交流使用。\n\n1. 严禁任何形式的倒卖、商用行为\n2. 如您通过付费渠道获得本软件，请立即退款并举报\n3. 请合理使用本工具，由此产生的一切后果\n    由使用者自行承担\n4. 本软件开源，欢迎监督和贡献",
    },
    "en": {
        "app_title": "Welearn Tool v3.5",
        "nav_home": "Home",
        "nav_donate": "Donate",
        "nav_help": "Help",
        "nav_settings": "Settings",
        "status_ready": "● Ready",
        "status_stopping": "Stopping...",
        "btn_stop": "Stop",
        "btn_donate": "Donate",
        "disclaimer_title": "Disclaimer",
        "donate_title": "Support Author",
        "donate_desc": "This program is free and open source.\nIf you paid for it, please request a refund!\n\nIf you like this project,\nsupport the author with a coffee ☕\n\nYour support motivates continued development",
        "donate_qr_hint": "Scan QR code with WeChat",
        "donate_later": "Maybe Later",
        "settings_lang": "Language",
        "settings_theme": "Theme",
        "settings_theme_system": "System",
        "settings_theme_light": "Light",
        "settings_theme_dark": "Dark",
        "settings_about": "About",
        "settings_version": "Version: v3.5",
        "settings_github": "GitHub",
        "settings_update": "Check Update",
        "settings_update_none": "Already up to date",
        "settings_update_err": "Update check failed",
        "help_title": "Cookie Tutorial",
        "help_step1": "1. Login to welearn, press F12 to open DevTools",
        "help_step2": "2. Click the Network tab at top",
        "help_step3": "3. Press F5 to refresh the page",
        "help_step4": "4. Find the first request in the left list and click it",
        "help_step5": "5. Find the Cookie field in Request Headers",
        "help_step6": "6. Copy the full Cookie value and paste into the app",
        "help_note": "Note: Cookies expire after some time. Never share your Cookie with others.",
        "login_title": "Login",
        "login_cookie": "Cookie Login (Recommended)",
        "login_password": "Password Login (Experimental)",
        "login_cookie_placeholder": "Paste browser Cookie string here...",
        "login_username_placeholder": "Username",
        "login_password_placeholder": "Password",
        "login_btn": "Login",
        "login_status_none": "Not logged in",
        "select_course": "Course:",
        "select_unit": "Unit:",
        "btn_refresh": "Refresh",
        "unit_all": "0. Complete all units",
        "tab_curriculum": "Curriculum",
        "tab_time": "Time",
        "rate_title": "Accuracy Settings",
        "rate_fixed": "Fixed:",
        "rate_random": "Random:",
        "time_title": "Duration Settings",
        "time_fixed": "Fixed:",
        "time_random": "Random:",
        "time_threads": "Max Threads:",
        "time_unit_sec": "s",
        "btn_start_curriculum": "Start Curriculum",
        "btn_start_time": "Start Time",
        "log_title": "Log",
        "progress": "Progress:",
        "agree_continue": "Agree & Continue",
        "skip_next": "Don't show again",
        "disclaimer_body": "This software is completely free for educational use only.\n\n1. Reselling or commercial use is strictly prohibited\n2. If you paid for this software, request a refund and report\n3. Users are solely responsible for any consequences\n4. Open source - contributions welcome",
    }
}
_ = lambda app, key: T.get(app.lang, T["zh"]).get(key, key)


# ── 配置持久化 ──────────────────────────────────────
CONFIG_PATH = _os.path.join(_os.path.expanduser("~"), ".welearn_config.json")

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
        with open(CONFIG_PATH, 'w', encoding='utf-8') as f:
            json.dump(cfg, f, ensure_ascii=False, indent=2)
    except Exception:
        pass


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
        self.root.title("Welearn 刷课工具 v3.5")
        self.root.geometry("1120x720")
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

        # 刷课参数
        self.curriculum_rate = 100
        self.curriculum_random = False
        self.curriculum_duration = [60, 120]
        self.curriculum_max_threads = 10

        # 刷时长参数
        self.time_duration = [60, 120]
        self.time_mode = 2
        self.time_max_threads = 10

        self._build_sidebar()
        self._build_content()
        self._build_statusbar()
        self._show_page("home")
        self.root.after(100, self._poll_queue)
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)

        # 免责声明（从配置检查是否跳过）
        if not self._config.get("disclaimer_skip", False):
            self.root.after(300, self._show_disclaimer)

    def _save_prefs(self):
        """保存当前偏好到配置文件"""
        self._config["lang"] = self.lang
        self._config["appearance"] = ctk.get_appearance_mode()
        _save_config(self._config)

    # ═══ 侧边栏 ═══════════════════════════════════════
    def _build_sidebar(self):
        self.sidebar = ctk.CTkFrame(self.root, width=300, corner_radius=0,
                                     fg_color=("#1a1a2e", "#0d1117"))
        self.sidebar.pack(side="left", fill="y")
        self.sidebar.pack_propagate(False)

        # ── IP 吉祥物 ──
        mascot_frame = ctk.CTkFrame(self.sidebar, fg_color="transparent")
        mascot_frame.pack(fill="x", padx=20, pady=(18, 2))
        try:
            nobi_img = ctk.CTkImage(Image.open(_NOBI_PATH), size=(54, 54))
            ctk.CTkLabel(mascot_frame, image=nobi_img, text="").pack(anchor="center")
        except Exception:
            ctk.CTkLabel(mascot_frame, text="🐰", font=ctk.CTkFont(size=32)).pack(anchor="center")
        ctk.CTkLabel(mascot_frame, text="Welearn",
                     font=ctk.CTkFont(size=11, weight="bold"),
                     text_color=("#e2e8f0", "#e2e8f0")).pack(anchor="center", pady=(4, 0))
        ctk.CTkLabel(mascot_frame, text="刷课工具",
                     font=ctk.CTkFont(size=9),
                     text_color=("#f0abfc", "#c084fc")).pack(anchor="center", pady=(1, 0))

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
        ctk.CTkLabel(log_header, text="📋 运行日志",
                     font=ctk.CTkFont(size=12, weight="bold"),
                     text_color=("#8b949e", "#8b949e")).pack(anchor="w")

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
        ctk.CTkLabel(bottom_frame, text="v3.5 · 免费开源",
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

        self.rate_var = ctk.StringVar(value="fixed")
        fixed_frame = ctk.CTkFrame(self.rate_panel, fg_color="transparent")
        fixed_frame.pack(fill="x", pady=1)
        ctk.CTkRadioButton(fixed_frame, text="固定:", variable=self.rate_var, value="fixed",
                           command=self._on_rate_mode_change).pack(side="left")
        self.fixed_rate_entry = ctk.CTkEntry(fixed_frame, width=65, placeholder_text="100")
        self.fixed_rate_entry.pack(side="left", padx=5)
        self.fixed_rate_entry.insert(0, "100")
        ctk.CTkLabel(fixed_frame, text="%").pack(side="left")

        rand_frame = ctk.CTkFrame(self.rate_panel, fg_color="transparent")
        rand_frame.pack(fill="x", pady=1)
        ctk.CTkRadioButton(rand_frame, text="随机:", variable=self.rate_var, value="random",
                           command=self._on_rate_mode_change).pack(side="left")
        self.rand_min_entry = ctk.CTkEntry(rand_frame, width=55, placeholder_text="70")
        self.rand_min_entry.pack(side="left", padx=5)
        self.rand_min_entry.insert(0, "70")
        ctk.CTkLabel(rand_frame, text="~").pack(side="left")
        self.rand_max_entry = ctk.CTkEntry(rand_frame, width=55, placeholder_text="100")
        self.rand_max_entry.pack(side="left", padx=5)
        self.rand_max_entry.insert(0, "100")
        ctk.CTkLabel(rand_frame, text="%").pack(side="left")
        self._on_rate_mode_change()

        # ── 时长 + 线程（共享） ──
        ctk.CTkFrame(self.task_frame, height=1, fg_color=("#e2e8f0", "#334155")).pack(fill="x", padx=15, pady=(6, 0))

        shared_panel = ctk.CTkFrame(self.task_frame, fg_color="transparent")
        shared_panel.pack(fill="x", padx=15, pady=(10, 5))
        ctk.CTkLabel(shared_panel, text="时长与并发设置",
                     font=ctk.CTkFont(size=13, weight="bold")).pack(anchor="w", pady=(0, 8))

        time_mode_row = ctk.CTkFrame(shared_panel, fg_color="transparent")
        time_mode_row.pack(fill="x", pady=1)
        self.time_var = ctk.StringVar(value="random")
        ctk.CTkRadioButton(time_mode_row, text="固定:", variable=self.time_var, value="fixed",
                           command=self._on_time_mode_change).pack(side="left")
        self.fixed_time_entry = ctk.CTkEntry(time_mode_row, width=65, placeholder_text="30")
        self.fixed_time_entry.pack(side="left", padx=5)
        self.fixed_time_entry.insert(0, "30")
        ctk.CTkLabel(time_mode_row, text="秒/课").pack(side="left")

        rand_time_row = ctk.CTkFrame(shared_panel, fg_color="transparent")
        rand_time_row.pack(fill="x", pady=1)
        ctk.CTkRadioButton(rand_time_row, text="随机:", variable=self.time_var, value="random",
                           command=self._on_time_mode_change).pack(side="left")
        self.time_min_entry = ctk.CTkEntry(rand_time_row, width=55, placeholder_text="60")
        self.time_min_entry.pack(side="left", padx=5)
        self.time_min_entry.insert(0, "60")
        ctk.CTkLabel(rand_time_row, text="~").pack(side="left")
        self.time_max_entry = ctk.CTkEntry(rand_time_row, width=55, placeholder_text="120")
        self.time_max_entry.pack(side="left", padx=5)
        self.time_max_entry.insert(0, "120")
        ctk.CTkLabel(rand_time_row, text="秒/课").pack(side="left")
        self._on_time_mode_change()

        thread_row = ctk.CTkFrame(shared_panel, fg_color="transparent")
        thread_row.pack(fill="x", pady=(8, 0))
        ctk.CTkLabel(thread_row, text="最大线程数:").pack(side="left")
        self.threads_entry = ctk.CTkEntry(thread_row, width=65, placeholder_text="10")
        self.threads_entry.pack(side="left", padx=5)
        self.threads_entry.insert(0, "10")

        # ── 开始按钮 + 进度 ──
        btn_row = ctk.CTkFrame(self.task_frame, fg_color="transparent")
        btn_row.pack(fill="x", padx=15, pady=(12, 5))
        self.btn_start_task = ctk.CTkButton(btn_row, text="🚀 开始运行",
                                            fg_color="#a855f7", hover_color="#9333ea",
                                            height=42, width=180, corner_radius=8,
                                            font=ctk.CTkFont(size=14, weight="bold"),
                                            command=self._on_start_task)
        self.btn_start_task.pack(side="left")

        # 进度条 + 统计
        progress_frame = ctk.CTkFrame(self.task_frame, fg_color="transparent")
        progress_frame.pack(fill="x", padx=15, pady=(0, 10))
        self.task_progress_label = ctk.CTkLabel(progress_frame, text="进度: -/-", font=ctk.CTkFont(size=12))
        self.task_progress_label.pack(anchor="w")
        self.task_progress_bar = ctk.CTkProgressBar(progress_frame, width=500)
        self.task_progress_bar.pack(fill="x", pady=(3, 3))
        self.task_progress_bar.set(0)
        self.task_stats_label = ctk.CTkLabel(progress_frame, text="", font=ctk.CTkFont(size=11),
                                              text_color=("#64748b", "#94a3b8"))
        self.task_stats_label.pack(anchor="w")

        # ── 日志已移至侧边栏 ──

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

            # 线程数（共用）
            max_threads = int(self.threads_entry.get())
            if mode == "curriculum":
                self.curriculum_max_threads = max_threads
            else:
                self.time_max_threads = max_threads

            # 正确率（仅刷课模式）
            if mode == "curriculum":
                if self.rate_var.get() == "fixed":
                    self.curriculum_rate = int(self.fixed_rate_entry.get())
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
                self._log(f"最新版本: {latest}，当前: v3.5")
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
        self.root.title("Welearn 刷课工具 v3.5" if self.lang == "zh" else "Welearn Tool v3.5")

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
        ctk.CTkLabel(dialog, text="v3.5 · 免费开源", text_color="gray").pack(pady=(0, 20))
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
                self._handle_message(self.message_queue.get_nowait())
        except queue.Empty:
            pass
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
                self.task_progress_label.configure(text=f"⏳ 进度: {current}/{total} | 剩余 {remaining} 个 | 请耐心等待...", text_color="#38bdf8")
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
