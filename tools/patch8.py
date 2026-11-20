# -*- coding: utf-8 -*-
"""v3.6.1 补丁：修 AUDIT_v36 的 blocker/high。"""
import re
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


# ── B1: CONFIG_PATH 未定义（配置永不落盘）──
rep('''MASCOT_NAME = "大肥鱼鲸鱼娘"''',
    '''MASCOT_NAME = "大肥鱼鲸鱼娘"

# 用户配置（主题/语言/免责声明跳过等）
CONFIG_PATH = _os.path.join(_os.path.expanduser("~"), ".welearn_config.json")''')

# 配置写盘改原子写 + 失败可见
rep('''        with open(CONFIG_PATH, 'w', encoding='utf-8') as f:''',
    '''        tmp = CONFIG_PATH + ".tmp"
        with open(tmp, 'w', encoding='utf-8') as f:''')
src = src.replace('''            json.dump(cfg, f, ensure_ascii=False, indent=2)''',
                  '''            json.dump(cfg, f, ensure_ascii=False, indent=2)
        _os.replace(tmp, CONFIG_PATH)''', 1)

# ── H1: 响应可能是两段 JSON 拼接，统一取最后一段 ──
rep('''def _clamp(v, lo, hi):''',
    '''def _last_json(body):
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


def _clamp(v, lo, hi):''')

rep('''        body = _text(resp).strip()
        idx = body.find('{"ret"')
        if idx > 0:
            body = body[idx:]
        js = json.loads(body) if body.startswith("{") else {}
        out["ok"] = js.get("ret") == 0''',
    '''        js = _last_json(_text(resp))
        out["ok"] = js.get("ret") == 0''')

# 心跳详情里也用统一解析 + 布尔归一
rep('''        body = _text(resp)
        idx = body.rfind('{"ret"')
        js = {}
        if idx >= 0:
            try:
                js = json.loads(body[idx:])
            except ValueError:
                js = {}
        out["ok"] = (js.get("ret") == 0)''',
    '''        js = _last_json(_text(resp))
        out["ok"] = (js.get("ret") == 0)''')
rep('''        out["endcaltime"] = bool(js.get("endcaltime"))''',
    '''        out["endcaltime"] = _as_bool(js.get("endcaltime"))''')

# 闸门：布尔归一（"false" 字符串曾被判真，导致整任务误停）
rep('''        body = _text(r).strip()
        js = json.loads(body) if body.startswith("{") else {}
        if js.get("isPausing"):''',
    '''        js = _last_json(_text(r))
        if _as_bool(js.get("isPausing")):''')
rep('''        body = _text(r).strip()
        js = json.loads(body) if body.startswith("{") else {}
        if js.get("status") == 0:''',
    '''        js = _last_json(_text(r))
        if js.get("status") == 0:''')

# ── B2: 停止也要收尾（否则已等的时长一秒不入账）──
rep('''    while elapsed < target and not reached:
        if stop_check and stop_check():
            result["stopped"] = True
            result["note"] = "用户停止"
            return result''',
    '''    while elapsed < target and not reached:
        if stop_check and stop_check():
            result["stopped"] = True
            result["note"] = "用户停止"
            break''')
rep('''    if stop_check and stop_check():
        result["stopped"] = True
        result["note"] = "用户停止"
        return result

    # 结束时补一次心跳，把最后一段时长落库''',
    '''    if stop_check and stop_check():
        result["stopped"] = True
        result["note"] = "用户停止"

    # 结束时补一次心跳，把最后一段时长落库（停止时也要落库，已学的时间不能白等）''')

# ── H3: 没有题目就不要拼 [INTERACTIONINFO] ──
rep('''    full_data = json.dumps(data_obj, ensure_ascii=False) + '[INTERACTIONINFO]' + interactions_info''',
    '''    full_data = json.dumps(data_obj, ensure_ascii=False)
    if interactions_info:
        full_data += '[INTERACTIONINFO]' + interactions_info''')

# ── H5/H6: 计数顺序（先判 stopped）──
rep('''            with stats_lock:
                counters["way1_ok" if r["way1"] else "way1_fail"] += 1
                counters["way2_ok" if r["way2"] else "way2_fail"] += 1

            if r["stopped"]:
                app.message_queue.put({"type": "log_warning", "text": f'  ⏹ {loc} 已停止'})
                return''',
    '''            if r["stopped"]:
                app.message_queue.put({"type": "log_warning",
                                       "text": f'  ⏹ {loc} 已停止（已学 {r["target"]}s 已落库）'})
                return
            with stats_lock:
                counters["way1_ok" if r["way1"] else "way1_fail"] += 1
                counters["way2_ok" if r["way2"] else "way2_fail"] += 1''')

# ── H4: 单元不再盲扫 999；单个单元失败不中止全部 ──
rep('''    if unitidx == 0:
        unit_start, unit_end = 0, 999
    else:
        unit_start, unit_end = unitidx - 1, unitidx
    out = []
    for i in range(unit_start, unit_end):
        if app.stop_requested:
            break
        lessons = welearn_get_lessons(app.session, cid, uid, i, classid)
        if lessons is None:
            return out, f"单元 {i} 的课时列表读取失败（会话可能已过期）"''',
    '''    unit_count = len(getattr(app, "units", []) or [])
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
            continue''')
rep('''            if only_unfinished and done:
                continue
            out.append((i, c))
    return out, None''',
    '''            if only_unfinished and done:
                continue
            out.append((i, c))
    err = ("部分单元课时读取失败：%s（会话可能已过期）" % failed_units) if failed_units else None
    return out, err''')

# ── H7: 刷时长 finalize 带 endcaltime ──
rep('''def welearn_time_finalize(session, cid, uid, scoid, progress, crate, cstatus,
                          session_time, total_time):
    """刷时长模式：保存最终学习数据（含累加后的学习时间）"""
    resp = session.post(AJAX_SCO_URL,
                        data={'action': 'savescoinfo160928', 'cid': cid, 'scoid': scoid,
                              'uid': uid, 'progress': progress, 'crate': crate,
                              'status': 'unknown', 'cstatus': cstatus, 'trycount': '0',
                              'session_time': session_time, 'total_time': total_time},''',
    '''def welearn_time_finalize(session, cid, uid, scoid, progress, crate, cstatus,
                          session_time, total_time, endcaltime="true"):
    """刷时长模式：保存最终学习数据（含累加后的学习时间）"""
    resp = session.post(AJAX_SCO_URL,
                        data={'action': 'savescoinfo160928', 'cid': cid, 'scoid': scoid,
                              'uid': uid, 'progress': progress, 'crate': crate,
                              'status': 'unknown', 'cstatus': cstatus, 'trycount': '0',
                              'session_time': session_time, 'total_time': total_time,
                              'endcaltime': endcaltime, 'nocache': random.random()},''')

# ── H8: 单课时上限跟平台要求对齐（timelitsec 是硬上限）──
rep('''DURATION_CAP = 1500     # 单课时最多等待（秒），平台单页上限 30min''',
    '''DURATION_CAP = 1800     # 单课时最多等待（秒），平台单页上限 30min
# 注：实际目标还会被 startsco 返回的 timelitsec 截断（达标即停表），所以这里只是保险上限''')

# 刷时长模式也按 timelitsec 截断，避免空等
rep('''        welearn_time_heartbeat(app.session, cid, uid, scoid, "0", str(init_total))
        elapsed = 0
        hb_count = 0''',
    '''        req = welearn_sco_requirements(app.session, cid, uid, classid, scoid)
        if req.get("timelitsec"):
            deficit = max(0, req["timelitsec"] - req["use_seconds"])
            if deficit and deficit < learntime:
                learntime = deficit  # 只需补齐差额，不空等
            if req["use_seconds"] >= req["timelitsec"]:
                app.message_queue.put({"type": "log",
                                       "text": f'  [跳过] {loc} 已满足平台要求 {req["timelitsec"]}s'})
                return

        welearn_time_heartbeat(app.session, cid, uid, scoid, "0", str(init_total))
        elapsed = 0
        hb_count = 0''')

# ── B3: 消息泵逐条 try，单条异常不打死整个队列 ──
rep('''    def _poll_queue(self):
        try:
            while True:
                self._handle_message(self.message_queue.get_nowait())
        except queue.Empty:
            pass
        self.root.after(100, self._poll_queue)''',
    '''    def _poll_queue(self):
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
            self.root.after(100, self._poll_queue)''')

open(P, "w", encoding="utf-8").write(src)
print("patch8 ok")
