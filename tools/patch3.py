# -*- coding: utf-8 -*-
"""v3.6 补丁 3：提交/心跳/线程核心重写（自适应时长 + 心跳 + 回读校验 + 防护）。"""
import re
import sys

P = "src/welearn_gui.py"
src = open(P, encoding="utf-8").read()


def replace_func(src, name, new):
    m = re.search(r"^def %s\(" % re.escape(name), src, re.M)
    if not m:
        print("NOT FOUND:", name)
        sys.exit(1)
    nxt = re.search(r"^def [A-Za-z_]", src[m.end():], re.M)
    end = m.end() + nxt.start() if nxt else len(src)
    return src[:m.start()] + new.rstrip() + "\n\n\n" + src[end:]


CUR = r'''
# ── 时长策略 ─────────────────────────────────────────
# 平台每个课时都带 timelitsec（要求学习的秒数，实测常见 1080s = 18min），
# 并回传 useSeconds（该课时已累计的有效时长）。脚本按"缺口"补齐，而不是固定 60~120s，
# 这样既不会因为"90 秒干完 18 分钟的活"被时钟流速校验命中，也不浪费多余时间。
HEARTBEAT_MIN = 20      # 心跳间隔下限（秒），平台硬上限 60s
HEARTBEAT_MAX = 32      # 心跳间隔上限（秒）
DURATION_CAP = 1500     # 单课时最多等待（秒），平台单页上限 30min，留余量


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
        body = _text(resp).strip()
        idx = body.find('{"ret"')
        if idx > 0:
            body = body[idx:]
        js = json.loads(body) if body.startswith("{") else {}
        out["ok"] = js.get("ret") == 0
        out["timelitsec"] = int(js.get("timelitsec") or 0)
        out["use_seconds"] = int(js.get("useSeconds") or 0)
        out["review"] = (js.get("enableview") == "true")
    except Exception as e:
        out["error"] = str(e)
    return out


def welearn_verify_learntime(session, cid, uid, classid, unitidx, scoid):
    """提交后回读：返回该课时当前的累计学习秒数（失败返回 None）。"""
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
              "timelitsec": 0, "verified": None, "stopped": False, "note": ""}

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

    # ── 2. 等时长 + 心跳（真实浏览器每 60s 一次，这里 20~32s 更稳）──
    base_total = req["use_seconds"]
    elapsed = 0.0
    next_hb = random.randint(HEARTBEAT_MIN, HEARTBEAT_MAX)
    while elapsed < target:
        if stop_check and stop_check():
            result["stopped"] = True
            result["note"] = "用户停止"
            return result
        step = min(1.0, target - elapsed)
        time.sleep(step * random.uniform(0.92, 1.08))
        elapsed += step
        if elapsed >= next_hb:
            welearn_time_heartbeat(session, cid, uid, scoid,
                                   str(int(elapsed)), str(base_total + int(elapsed)),
                                   timelitsec=req["timelitsec"])
            next_hb = elapsed + random.randint(HEARTBEAT_MIN, HEARTBEAT_MAX)

    if stop_check and stop_check():
        result["stopped"] = True
        result["note"] = "用户停止"
        return result

    # 结束时补一次心跳，把最后一段时长落库
    welearn_time_heartbeat(session, cid, uid, scoid,
                           str(int(elapsed)), str(base_total + int(elapsed)),
                           timelitsec=req["timelitsec"])

    # ── 3. 提交 SCORM 数据 ──
    now_utc = time.strftime("%Y-%m-%dT%H:%M:%S", time.gmtime())
    data_obj = {
        "cmi": {
            "completion_status": "completed",
            "interactions": interactions_json,
            "launch_data": "",
            "location": "",
            "exit": "",
            "progress_measure": "1",
            "score": {"scaled": str(crate_int), "raw": str(crate_int), "min": "0", "max": "100"},
            "session_time": str(int(elapsed)),
            "success_status": "unknown",
            "total_time": str(base_total + int(elapsed)),
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
    full_data = json.dumps(data_obj, ensure_ascii=False) + '[INTERACTIONINFO]' + interactions_info

    resp1 = session.post(AJAX_SCO_URL,
                         data={"action": "setscoinfo", "cid": cid, "scoid": scoid,
                               "uid": uid, "data": full_data, "isend": "False"},
                         headers=_build_headers(referer), timeout=20)
    result["way1"] = '"ret":0' in _text(resp1)

    time.sleep(_rand_delay(0.3, 0.5))

    resp2 = session.post(AJAX_SCO_URL,
                         data={"action": "savescoinfo160928", "cid": cid, "scoid": scoid,
                               "uid": uid, "progress": "100", "crate": str(crate_int),
                               "status": "unknown", "cstatus": "completed", "trycount": "0",
                               "session_time": str(int(elapsed)),
                               "total_time": str(base_total + int(elapsed)),
                               "endcaltime": "true", "nocache": random.random()},
                         headers=_build_headers(referer), timeout=20)
    result["way2"] = '"ret":0' in _text(resp2)

    # ── 4. 回读校验：平台是否真的把时长记上了 ──
    result["verified"] = welearn_verify_learntime(session, cid, uid, classid, unitidx, scoid)
    return result
'''

HB = r'''
def welearn_time_heartbeat(session, cid, uid, scoid, session_time, total_time,
                           timelitsec=0, endcaltime="false"):
    """刷时长模式：发送心跳包保持在线。

    平台按两次心跳的墙钟差累计时长，并回传 seconds（服务端权威增量）；
    漏发心跳这段时长会被直接丢弃，所以间隔必须明显小于 60s。
    """
    resp = session.post(AJAX_SCO_URL,
                        data={'action': 'keepsco_with_getticket_with_updatecmitime',
                              'uid': uid, 'cid': cid, 'scoid': scoid,
                              'session_time': session_time, 'total_time': total_time,
                              'timelitsec': timelitsec, 'endcaltime': endcaltime,
                              'nocache': random.random()},
                        headers=_build_headers('https://welearn.sflep.com/student/StudyCourse.aspx'),
                        timeout=20)
    return '"ret":0' in _text(resp)
'''

CUR_THREAD = r'''
def _collect_lessons(app, only_unfinished):
    """收集课时列表；返回 ([(unit_i, course), ...], error)"""
    cid, uid, classid = app.selected_cid, app.uid, app.classid
    unitidx = app.selected_unit_idx
    if unitidx == 0:
        unit_start, unit_end = 0, 999
    else:
        unit_start, unit_end = unitidx - 1, unitidx
    out = []
    for i in range(unit_start, unit_end):
        if app.stop_requested:
            break
        lessons = welearn_get_lessons(app.session, cid, uid, i, classid)
        if lessons is None:
            return out, f"单元 {i} 的课时列表读取失败（会话可能已过期）"
        for c in lessons:
            visible = str(c.get('isvisible', 'true')).lower() != 'false'
            done = ("已" in c.get('iscomplete', '')) and ("未" not in c.get('iscomplete', ''))
            if not visible:
                continue
            if only_unfinished and done:
                continue
            out.append((i, c))
    return out, None


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
    max_threads = _clamp(int(getattr(app, 'curriculum_max_threads', 1) or 1), 1, 3)

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

    def process_one(unit_i, course):
        if app.stop_requested:
            return
        loc = course.get("location", "?")
        scoid = course.get("id")
        try:
            crate = random.randint(mycrate[0], mycrate[1]) if randommode else int(mycrate)
            dur = random.randint(duration[0], duration[1]) if random_duration else int(duration)
            app.message_queue.put({"type": "log",
                                   "text": f'[刷课] {loc} → 目标正确率 {crate}%，至少学 {dur}s'})
            r = welearn_curriculum_submit(app.session, cid, uid, classid, scoid, crate,
                                          learntime=dur, stop_check=lambda: app.stop_requested,
                                          unitidx=unit_i)
            with stats_lock:
                counters["way1_ok" if r["way1"] else "way1_fail"] += 1
                counters["way2_ok" if r["way2"] else "way2_fail"] += 1

            if r["stopped"]:
                app.message_queue.put({"type": "log_warning", "text": f'  ⏹ {loc} 已停止'})
                return

            detail = f'目标{r["target"]}s'
            if r["timelitsec"]:
                detail += f' / 平台要求{r["timelitsec"]}s'
            if r["verified"] is not None:
                detail += f' / 回读{r["verified"]}s'
            tag = "log_success" if (r["way1"] and r["way2"]) else "log_error"
            ok_txt = "答题记录✓" if r["way1"] else "答题记录✗"
            sv_txt = "进度保存✓" if r["way2"] else "进度保存✗"
            app.message_queue.put({"type": tag, "text": f'  {ok_txt} {sv_txt}｜{detail}'})
            if r["timelitsec"] and (r["verified"] or 0) < r["timelitsec"]:
                app.message_queue.put({"type": "log_warning",
                                       "text": f'  ⚠ 该课时时长仍未达标，再跑一次会自动补齐剩余部分'})
        except Exception as e:
            app.message_queue.put({"type": "log_error", "text": f'  ✗ [异常] {loc} - {e}'})
            with stats_lock:
                counters["way1_fail"] += 1
                counters["way2_fail"] += 1
        finally:
            with stats_lock:
                processed[0] += 1
                cur = processed[0]
            app.message_queue.put({"type": "progress", "current": cur, "total": total})

    for start in range(0, total, max_threads):
        if app.stop_requested:
            app.message_queue.put({"type": "log_warning", "text": "⚠️ 用户停止了任务"})
            break
        batch = all_lessons[start:start + max_threads]
        threads = []
        for unit_i, course in batch:
            t = threading.Thread(target=process_one, args=(unit_i, course), daemon=True)
            t.start()
            threads.append(t)
            time.sleep(_rand_delay(0.4, 1.2))
        for t in threads:
            while t.is_alive():
                t.join(timeout=1.0)
        app.message_queue.put({"type": "log",
                               "text": f'✅ 进度 {processed[0]}/{total}｜剩余 {total - processed[0]} 个'})
        # 冷却：每完成若干节休息一段时间，模拟真人节奏
        if cooldown_every and processed[0] < total and processed[0] % cooldown_every == 0:
            rest = random.randint(cooldown_range[0], cooldown_range[1])
            app.message_queue.put({"type": "log",
                                   "text": f'☕ 休息 {rest}s 再继续（降低集中完成特征）'})
            waited = 0
            while waited < rest and not app.stop_requested:
                time.sleep(1.0)
                waited += 1

    app.message_queue.put({"type": "curriculum_complete",
                           "way1_ok": counters["way1_ok"], "way1_fail": counters["way1_fail"],
                           "way2_ok": counters["way2_ok"], "way2_fail": counters["way2_fail"],
                           "stopped": app.stop_requested})
'''

TIME_THREAD = r'''
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
    max_threads = _clamp(int(getattr(app, 'time_max_threads', 1) or 1), 1, 3)

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

    for idx in range(0, total, max_threads):
        if app.stop_requested:
            app.message_queue.put({"type": "log_warning", "text": f"⚠️ 已停止 | 进度 {processed}/{total}"})
            break
        batch = all_lessons[idx:idx + max_threads]
        threads = []
        for unit_i, course in batch:
            learn = random.randint(inputtime[0], inputtime[1]) if mode == 2 else int(inputtime)
            t = threading.Thread(target=_time_one, args=(app, cid, uid, classid, unit_i, course,
                                                         learn, errors, lambda: processed),
                                 daemon=True)
            t.start()
            threads.append(t)
            time.sleep(_rand_delay(0.4, 1.2))
        for t in threads:
            while t.is_alive():
                t.join(timeout=1.0)
        processed += len(batch)
        app.message_queue.put({"type": "progress", "current": processed, "total": total})
        app.message_queue.put({"type": "log",
                               "text": f'✅ 进度 {processed}/{total}｜剩余 {total - processed} 个'})

    app.message_queue.put({"type": "time_complete", "errors": len(errors),
                           "stopped": app.stop_requested})


def _time_one(app, cid, uid, classid, unit_i, course, learntime, errors, _processed):
    loc = course.get("location", "?")
    scoid = course.get("id")
    app.message_queue.put({"type": "log", "text": f'[刷时长] {loc} → +{learntime}s 开始...'})
    try:
        cmi = welearn_time_init(app.session, cid, uid, scoid)
        if cmi is None:
            app.message_queue.put({"type": "log_error", "text": f'  [失败] {loc} - 初始化学习数据失败'})
            errors.append(loc)
            return
        try:
            init_total = int(cmi.get('total_time') or 0)
        except (TypeError, ValueError):
            init_total = 0

        welearn_time_heartbeat(app.session, cid, uid, scoid, "0", str(init_total))
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
'''

src = replace_func(src, "welearn_time_heartbeat", HB)
src = replace_func(src, "welearn_curriculum_submit", CUR)
src = replace_func(src, "thread_curriculum_execute", CUR_THREAD)
src = replace_func(src, "thread_time_execute", TIME_THREAD)
open(P, "w", encoding="utf-8").write(src)
print("patch3 ok")
