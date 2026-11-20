# -*- coding: utf-8 -*-
"""v3.6 补丁 4：平台两道闸门（isPausing / checkNoCaptcha）+ 心跳详情。"""
import re
import sys

P = "src/welearn_gui.py"
src = open(P, encoding="utf-8").read()

GATES = r'''
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
        body = _text(r).strip()
        js = json.loads(body) if body.startswith("{") else {}
        if js.get("isPausing"):
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
        body = _text(r).strip()
        js = json.loads(body) if body.startswith("{") else {}
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
                                  'timelitsec': timelitsec, 'endcaltime': endcaltime,
                                  'nocache': random.random()},
                            headers=_build_headers('https://welearn.sflep.com/student/StudyCourse.aspx'),
                            timeout=20)
        body = _text(resp)
        idx = body.rfind('{"ret"')
        js = {}
        if idx >= 0:
            try:
                js = json.loads(body[idx:])
            except ValueError:
                js = {}
        out["ok"] = (js.get("ret") == 0)
        out["seconds"] = int(js.get("seconds") or 0)
        out["ticket"] = js.get("ticket") or ""
        out["endcaltime"] = bool(js.get("endcaltime"))
    except Exception:
        pass
    return out

'''

# 插到 welearn_time_heartbeat 前面
anchor = "def welearn_time_heartbeat("
if anchor not in src:
    print("anchor missing")
    sys.exit(1)
if "def welearn_check_gates(" not in src:
    src = src.replace(anchor, GATES.lstrip("\n") + "\n" + anchor, 1)

# 心跳包内部改为复用详情版，保证行为一致
old_hb = re.search(r"def welearn_time_heartbeat\(.*?\n    return '\"ret\":0' in _text\(resp\)\n",
                   src, re.S)
if not old_hb:
    print("heartbeat body not matched")
    sys.exit(1)
new_hb = '''def welearn_time_heartbeat(session, cid, uid, scoid, session_time, total_time,
                           timelitsec=0, endcaltime="false"):
    """刷时长模式：发送心跳包保持在线（薄封装，返回是否成功）"""
    return welearn_heartbeat_full(session, cid, uid, scoid, session_time, total_time,
                                  timelitsec=timelitsec, endcaltime=endcaltime)["ok"]
'''
src = src[:old_hb.start()] + new_hb + src[old_hb.end():]

# 在刷课流程里插入闸门检查
old = '''        try:
            crate = random.randint(mycrate[0], mycrate[1]) if randommode else int(mycrate)'''
new = '''        try:
            blocked, why = welearn_check_gates(app.session, uid, cid)
            if blocked:
                app.message_queue.put({"type": "log_error", "text": f"🛑 {why}"})
                app.stop_requested = True
                return
            crate = random.randint(mycrate[0], mycrate[1]) if randommode else int(mycrate)'''
assert src.count(old) == 1, src.count(old)
src = src.replace(old, new)

# 刷时长流程同样检查
old2 = '''    app.message_queue.put({"type": "log", "text": f'[刷时长] {loc} → +{learntime}s 开始...'})
    try:'''
new2 = '''    app.message_queue.put({"type": "log", "text": f'[刷时长] {loc} → +{learntime}s 开始...'})
    try:
        blocked, why = welearn_check_gates(app.session, uid, cid)
        if blocked:
            app.message_queue.put({"type": "log_error", "text": f"🛑 {why}"})
            app.stop_requested = True
            return'''
assert src.count(old2) == 1
src = src.replace(old2, new2)

open(P, "w", encoding="utf-8").write(src)
print("patch4 ok")
