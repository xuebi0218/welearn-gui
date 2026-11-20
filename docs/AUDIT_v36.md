# Welearn GUI v3.6 代码审计报告

- **审计对象**：`src/welearn_gui.py`（2289 行，Python 3.13 / CustomTkinter 5.2.2 / requests）
- **审计方式**：只读。先 `ast.parse` + `py_compile` 通过（见下），再静态通读全部改动区与调用链；核对 `WelearnGUI.spec`、`build_welearn_gui.bat`、`src/` 资源清单、`docs/RISK_ANALYSIS.md`、`docs/PROTOCOL_FORENSICS.md`、`docs/AUDIT_v35.md`。**未运行任何会登录外站的请求**，未修改源码。
- **语法校验**：
  ```
  python -c "import ast;ast.parse(open('src/welearn_gui.py',encoding='utf-8').read())"   -> OK
  python -m py_compile src/welearn_gui.py                                               -> OK
  ```
  另用 AST 扫全局名：唯一未定义全局是 `CONFIG_PATH`（见 B1）。
- **统计**：blocker 3 / high 8 / medium 10 / low 10（共 31 条）。含"已核查无问题"清单（第 6 节），把用户点名的若干疑点逐条排除，避免下次重复排查。

> 行号均对应当前 `src/welearn_gui.py`（2289 行）。本报告只给结论与修法，不改源码。

---

## 0. 结论速览

| 级别 | 数量 | 分布 |
|---|---|---|
| blocker | 3 | 配置永不落盘（回归）、刷课模式停止不 finalize、消息泵无兜底 |
| high | 8 | 两段 JSON 解析用 find、回读用 startsco 副作用、空 INTERACTIONINFO、999 盲扫、字符串布尔、停止计入失败、finalize 缺 endcaltime、上限 1500>1080 |
| medium | 10 | seconds 丢弃、子串判 ret、time_init 裸 JSON、正确率范围校验缺失、主线程网络、估值控件错位、硬编码索引、版本号、spec 双份、timeonly 限额文案 |
| low | 10 | 重复函数/未用 import、浮点累加、死代码、未引用资源、文案双计等 |

**最该先修的 3 件事**

1. **补回 `CONFIG_PATH`**（B1）：v3.6 重写时丢了定义，`_load_config`/`_save_config` 双双 `except: pass`，配置永久不落盘。
2. **`welearn_curriculum_submit` 的 stop 分支必须走 finalize**（B2）：现在按停止就 `return`，已学时长全丢、服务端会话残留，与刷时长模式行为不一致。
3. **`welearn_sco_requirements` 改 `rfind`**（H1）：平台心跳响应是 `{"ret":-1}{"ret":0,...}` 两段拼接，`find` 取到第一段必然 `json.loads` 抛错，adaptive 与"达标停表"整条链路静默失效。

---

# 1. blocker

## B1 · blocker · `CONFIG_PATH` 未定义 → 全部偏好永不落盘（v3.6 重写回归）

**位置**：`src/welearn_gui.py:1174`、`src/welearn_gui.py:1175`、`src/welearn_gui.py:1184`（使用处）；对照 v3.4 备份 `src/welearn_gui_v3.4_backup_20260703.py:1041` 原本有定义。

**问题**：全文件搜不到 `CONFIG_PATH =`，只有使用：

```python
1174:        if _os.path.exists(CONFIG_PATH):
1175:            with open(CONFIG_PATH, 'r', encoding='utf-8') as f:
1184:        with open(CONFIG_PATH, 'w', encoding='utf-8') as f:
```

而两个函数都把异常吞掉：

```python
1171:def _load_config():
1172:    """加载持久化配置"""
1173:    try:
...
1177:    except Exception:
1178:        pass
1179:    return {}
1181:def _save_config(cfg):
1183:    try:
...
1186:    except Exception:
1187:        pass
```

**影响**：
- 启动不崩（`NameError` 被 `except Exception` 吃掉），但**任何配置都读不到、也写不进**。
- 具体后果：`disclaimer_skip` 永远 False → 每次启动都弹免责声明（`__init__:1254`）；`appearance` 永远是 System；`lang` 永远是 `zh`。用户改过的开关重启后全丢。
- 这类"静默吞异常 + 名字未定义"的组合最难靠使用发现，日志里一个字都不会有。

**修复建议**：

```python
# 放在 import 之后、常量区（约 31-40 行）
import os as _os
CONFIG_PATH = _os.path.join(_os.path.expanduser("~"), ".welearn_config.json")
```

并把两处 `except Exception: pass` 至少降级成可观测（否则下次同样问题还是无声）：

```python
def _save_config(cfg):
    try:
        tmp = CONFIG_PATH + ".tmp"
        with open(tmp, 'w', encoding='utf-8') as f:
            json.dump(cfg, f, ensure_ascii=False, indent=2)
        _os.replace(tmp, CONFIG_PATH)      # 原子写，避免半截文件
    except Exception as e:
        print(f"[config] save failed: {e}")   # 或塞进 message_queue
```

> 附带提醒：现有写法 `open(CONFIG_PATH,'w')` 直接截断原文件，写到一半崩溃会留下空文件；上面的 tmp+replace 顺手解决。

---

## B2 · blocker · 刷课模式"停止"提前 return，不做 finalize → 时长全丢 + 服务端残留会话

**位置**：`src/welearn_gui.py:490-494`（循环内）、`src/welearn_gui.py:507-510`（循环后二次检查）

**问题**：

```python
490:    while elapsed < target and not reached:
491:        if stop_check and stop_check():
492:            result["stopped"] = True
493:            result["note"] = "用户停止"
494:            return result          # ← 直接返回，没有 savescoinfo160928
...
507:    if stop_check and stop_check():
508:        result["stopped"] = True
509:        result["note"] = "用户停止"
510:        return result              # ← 同上
```

这两条路径都**跳过了** `551` 之后的 `setscoinfo`/`savescoinfo160928`（含 `endcaltime: "true"`），也跳过了 `514` 的收尾心跳。

**影响**（按 `docs/RISK_ANALYSIS.md:27`、`docs/PROTOCOL_FORENSICS.md:100` 的结论：服务端 learntime = `startsco` → `savescoinfo` 的墙钟差）：
1. 本节已等待的时长（可能长达 10~15 分钟）**一秒都不入账**；
2. 服务端仍认为该 SCO 处于"学习中"，会话不关闭——下一个 `startsco` 换票、心跳可能被拒或 `ret:1` 复位（`PROTOCOL_FORENSICS.md:140`），多次停止会累积出多份脏会话；
3. 与刷时长模式行为不一致：`_time_one` 在 stop 后仍然走 `1153-1159` 的收尾心跳 + `finalize`，只有刷课模式丢数据。v3.5 审计 A13（`docs/AUDIT_v35.md:405`）已判 high，v3.6 未修。

**修复建议**：把"停止"从 `return` 改成"置标志 + break"，让控制流走到统一的收尾段：

```python
    elapsed = 0.0
    next_hb = random.randint(HEARTBEAT_MIN, HEARTBEAT_MAX)
    reached = timer_target > 0 and base_total >= timer_target
    stopped_by_user = False
    while elapsed < target and not reached:
        if stop_check and stop_check():
            stopped_by_user = True
            break
        step = min(1.0, target - elapsed)
        time.sleep(step * random.uniform(0.92, 1.08))
        elapsed = min(float(target), elapsed + step)
        ...

    result["stopped"] = stopped_by_user
    if stopped_by_user:
        result["note"] = "用户停止"

    # 无论如何都要把已累计时长落库并关闭会话
    final_reached = bool(timer_target) and (base_total + elapsed) >= timer_target * 0.99
    welearn_time_heartbeat(session, cid, uid, scoid,
                           str(int(elapsed)), str(base_total + int(elapsed)),
                           timelitsec=timer_target, endcaltime="true")
    ...
    # setscoinfo / savescoinfo160928 照常执行（进度数字仍按已完成算，时长按实际 elapsed）
    ...
    if stopped_by_user:
        return result          # 提交之后再返回，只在"用户要求立即中止"这种极端场景才跳过提交
```

**验收**：跑到一半按停止 → 服务端 `getscoinfo_v7` 的 `total_time` 应等于 stop 时的 `base_total+elapsed`（±几秒），且一个多余会话都不留。

---

## B3 · blocker · `_poll_queue` 无逐条保护、无 `finally` 重排：一次消息处理异常 = 消息泵永久停摆

**位置**：`src/welearn_gui.py:2200-2206`、`src/welearn_gui.py:2208-2264`

**问题**：

```python
2200:    def _poll_queue(self):
2201:        try:
2202:            while True:
2203:                self._handle_message(self.message_queue.get_nowait())
2204:        except queue.Empty:
2205:            pass
2206:        self.root.after(100, self._poll_queue)   # ← 只有正常走到这里才会重排
```

`_handle_message` 里大量无保护取值与控件操作：`msg["courses"]`(2213)、`msg["uid"]`/`msg["classid"]`/`msg["units"]`(2228)、`msg["way1_ok"]`(2243)、`msg["text"]`(2211)、`_set_running` 里的一串 `configure`（窗口已销毁时抛 `TclError`）。

**影响**：`2206` 的 `after` 不会执行 → **消息泵永久停摆**。表象：进度条冻结、`_set_running(False)` 永不执行 → 所有控件永久灰、`_on_close`(2102-2107) 因 `self.running` 拒绝关闭，用户只能杀进程。v3.6 加 `task_finished` 的初衷（不让控件永久灰）恰好被这一层抵消。

**修复建议**：单条 try + `finally` 重排，任何一条坏消息都不许影响后续：

```python
    def _poll_queue(self):
        try:
            for _ in range(200):                     # 顺便给单次排空设上限，避免 UI 饿死
                try:
                    msg = self.message_queue.get_nowait()
                except queue.Empty:
                    break
                try:
                    self._handle_message(msg)
                except Exception as e:
                    self._log(f"[UI] 消息处理失败 {msg.get('type')}: {e}", "log_error")
        finally:
            self.root.after(100, self._poll_queue)
```

`_handle_message` 顶部也可加类型守卫：`if not isinstance(msg, dict) or "type" not in msg: return`。

---

# 2. high

## H1 · high · `welearn_sco_requirements` 用 `find` 而非 `rfind`：两段 JSON 拼接时必然解析失败

**位置**：`src/welearn_gui.py:398-401`；对照正确写法 `src/welearn_gui.py:673`

**问题**：

```python
397:        body = _text(resp).strip()
398:        idx = body.find('{"ret"')
399:        if idx > 0:
400:            body = body[idx:]
401:        js = json.loads(body) if body.startswith("{") else {}
```

`docs/RISK_ANALYSIS.md:39` 实证响应形如：

```
{"ret":-1}{"ret":0,"seconds":30,"endcaltime":false,"ticket":"..."}
```

`find` 取第一个 `{"ret"` 后剩下的仍是两段 → `json.loads` 抛 `JSONDecodeError: Extra data` → 被 `406: except Exception` 吞 → `ok=False, timelitsec=0, use_seconds=0`。

**影响**（雪崩式）：
- `474` `req` 失败 → `477` adaptive 分支不生效（`target` 只用用户设的时长）；
- `486` `timer_target=0` → `489` `reached` 恒 False、`500` 永不发 `endcaltime=true` 心跳 → 达标停表失效，多等；
- `573` 回读校验条件 `if timer_target and ...` 恒 False → **回读校验整段被跳过**，`verified` 随之为空，`process_one:1008` 的"时长未达标"告警也不会出现。
- 也就是说：只要平台返回拼接体，v3.6 新增的"自适应 + 回读校验"两大特性全部静默失效，且日志里毫无痕迹。

**修复建议**：与 `673` 保持一致，用 `rfind`，并且只取到最后一个完整对象：

```python
def _last_json(body: str) -> dict:
    """平台常返回 {a}{b} 拼接体，取最后一个 {"ret"...} 起点解析。"""
    idx = body.rfind('{"ret"')
    if idx < 0:
        return {}
    try:
        obj, _end = json.JSONDecoder().raw_decode(body[idx:])   # 容忍尾部杂质
        return obj if isinstance(obj, dict) else {}
    except ValueError:
        return {}

# 398-401 替换为
        js = _last_json(_text(resp).strip())
```

`welearn_check_gates`(630)、`646` 同样建议换成 `_last_json`（见 H5）。

**验收**：构造 `{"ret":-1}{"ret":0,"timelitsec":1080,"useSeconds":60}` 喂给函数，应得到 `ok=True, timelitsec=1080, use_seconds=60`。

---

## H2 · high · `welearn_verify_learntime` 用 `startsco` 回读：会重开会话、改计时起点，且提交后留下 2 个未关闭会话

**位置**：`src/welearn_gui.py:411-430`（函数体）、`src/welearn_gui.py:572-577`（调用）

**问题**：

```python
417:    try:
418:        req = welearn_sco_requirements(session, cid, uid, classid, scoid)   # ← 内部 POST action=startsco160928
419:        if req.get("ok"):
420:            return req["use_seconds"]
```

`docs/PROTOCOL_FORENSICS.md:195` / `:139`：`startsco160928` 是**开课**动作，会重开 SCO 会话、换 `studyTicket`、重置计时起点。把它当"只读查询"用，等于每次校验都真实开一次课。

**影响**：
1. `572` 与 `575` 各调一次（中间 `sleep(3)`），即**每提交一节就额外开 1~2 个 SCO 会话且不关闭**——服务端会话堆积，且这些会话的墙钟时间在后续被计入/复位（`ret:1`），产生脏学时；
2. 刚 `savescoinfo` 完就 `startsco`，会让服务端"完成态"重新变"学习中"（进度回退风险），下次列表里可能又出现"未完成"；
3. 若 `startsco` 返回非 0，函数回落到 `welearn_get_lessons`(424)——那是列表接口，`learntime` 有明显延迟（函数 docstring 自己也写了"实测刚提交完仍是旧值"），于是**必然**再次触发 `574` 的 3 秒重试，白白多开一次会话；
4. 返回 `None` 时 `573` 的 `(result["verified"] or 0)` 当 0 处理，会额外多跑一轮，最终仍是 `None`，失败无法回滚。

**修复建议**：改用真正只读的接口，把 `startsco` 的选择性下发留给唯一的开课点（`474`）：

```python
def welearn_verify_learntime(session, cid, uid, classid, unitidx, scoid):
    """只读回读：优先 getscoinfo_v7（不改变会话），其次课时列表。"""
    ref = 'https://welearn.sflep.com/student/StudyCourse.aspx'
    try:
        r = session.post(AJAX_SCO_URL,
                         data={'action': 'getscoinfo_v7', 'uid': uid, 'cid': cid, 'scoid': scoid},
                         headers=_build_headers(ref), timeout=15)
        body = _text(r)
        if '学习数据不正确' not in body:
            back = json.loads(body).get('comment') or ''
            if 'cmi' in back:
                total = json.loads(back)['cmi'].get('total_time', '0')
                sec = _parse_hms(total) if ':' in str(total) else int(float(total or 0))
                if sec is not None:
                    return sec
    except Exception:
        pass
    try:
        lessons = welearn_get_lessons(session, cid, uid, unitidx, classid) or []
        for c in lessons:
            if str(c.get('id')) == str(scoid):
                return _parse_hms(c.get('learntime'))
    except Exception:
        pass
    return None
```

顺带把 `573-577` 的重试次数收敛为 1 次、间隔拉到 5s 以上（入账延迟通常 3~10s），避免连打。

---

## H3 · high · 无题目时仍拼接 `[INTERACTIONINFO]`，产生"完成态在、答题记录空"的异常组合

**位置**：`src/welearn_gui.py:468-471`、`src/welearn_gui.py:551`

**问题**：

```python
468:    if questions:
469:        interactions_json, interactions_info = generate_interactions(questions, crate_int)
470:    else:
471:        interactions_json, interactions_info = [], ""
...
551:    full_data = json.dumps(data_obj, ensure_ascii=False) + '[INTERACTIONINFO]' + interactions_info
```

`551` 无条件拼接；`interactions_info` 为空时载荷尾部是一个空的 `[INTERACTIONINFO]`。

**影响**：`docs/PROTOCOL_FORENSICS.md:634` 记录了实测行为——空后半段仍返回 `ret:0`，但**不生成答题记录**。于是 `result["way1"]` 判成功、`completion_status=completed` 落库，答题记录却为空；平台若按"完成但无 interaction"做一致性检查，就是最容易被隔天复核挑出来的样本（同时 `score.scaled=88` 却没有任何 interaction 记录，自相矛盾）。v3.5 审计 A12（`docs/AUDIT_v35.md:383`）已判 high 并给了同样的修法，v3.6 未修。

**修复建议**：

```python
    full_data = json.dumps(data_obj, ensure_ascii=False)
    if interactions_info:
        full_data += '[INTERACTIONINFO]' + interactions_info
    elif result["questions"] == 0:
        # 课件本身无题：不谎报正确率
        data_obj["cmi"]["score"] = {"scaled": "", "raw": ""}
        data_obj["cmi"]["completion_status"] = "completed"
        full_data = json.dumps(data_obj, ensure_ascii=False)
```

（`score` 必须在 `json.dumps` 之前改，上面写法示意"二选一"，落地时把 `score` 的决策提到 `521` 的 dict 构造处。）

---

## H4 · high · `_collect_lessons` 硬编码盲扫 999 个单元；`lessons is None` 直接中止整个收集

**位置**：`src/welearn_gui.py:896-906`

**问题**：

```python
896:    if unitidx == 0:
897:        unit_start, unit_end = 0, 999      # ← 魔法上界
899:        unit_start, unit_end = unitidx - 1, unitidx
901:    for i in range(unit_start, unit_end):
...
904:        lessons = welearn_get_lessons(app.session, cid, uid, i, classid)
905:        if lessons is None:
906:            return out, f"单元 {i} 的课时列表读取失败（会话可能已过期）"   # ← 全盘中止
```

**影响**：
1. 默认"全部单元"要么盲扫 999 次（越界单元若返回 `[]` 而非 404，就是几百个无用请求，直接撞风控）；要么在真实单元结束后立刻拿到 `None`，触发第 2 条。
2. `welearn_get_lessons`(343-359) 在响应含 `"异常"`/`"出错了"` 或网络抖动时返回 `None`：一个单元抖动 → **后续所有单元全丢**，日志只有一句"会话可能已过期"，用户会误以为 session 失效而重登。v3.5 A6（`docs/AUDIT_v35.md:216`）同类问题，v3.6 从 `break` 改成了 `return`（更彻底的中止）。

**修复建议**：用真实单元数 + 单单元失败不致命 + 连续失败才中止：

```python
def _collect_lessons(app, only_unfinished):
    cid, uid, classid = app.selected_cid, app.uid, app.classid
    unitidx = app.selected_unit_idx

    if unitidx == 0:
        units = app.units or welearn_get_units(app.session, cid, uid) or []
        unit_range = range(0, max(1, len(units)))
    else:
        unit_range = range(unitidx - 1, unitidx)

    out, fails = [], 0
    for i in unit_range:
        if app.stop_requested:
            break
        lessons = welearn_get_lessons(app.session, cid, uid, i, classid)
        if lessons is None:
            fails += 1
            app.message_queue.put({"type": "log_warning",
                                   "text": f"单元 {i} 课时列表读取失败，跳过（连续失败 {fails}）"})
            if fails >= 3:
                return out, "连续 3 个单元读取失败，会话可能已过期，请重新登录"
            continue
        fails = 0
        for c in lessons:
            ...
    return out, (None if out else "未取到任何课时，请确认课程/单元选择")
```

**验收**：课程有 8 个单元时，`welearn_get_lessons` 的请求次数应为 8（±0），不是 999。

---

## H5 · high · 布尔字段未做字符串归一：`"false"` 被判为真（平台闸门 + endcaltime）

**位置**：`src/welearn_gui.py:631`（`isPausing`）、`src/welearn_gui.py:683`（`endcaltime`）

**问题**：

```python
630:        js = json.loads(body) if body.startswith("{") else {}
631:        if js.get("isPausing"):
...
683:        out["endcaltime"] = bool(js.get("endcaltime"))
```

同一文件 `405` 行对 `enableview` 用的是 `js.get("enableview") == "true"`——**证明这个 API 家族确实下发字符串布尔**。反过来推：`isPausing` 很可能也是 `"false"` / `"true"` 字符串。

**影响**：
- `631`：若返回 `"false"`（非空字符串 → 真值）→ `check_gates` 返回 `blocked=True` → `process_one:982` / `_time_one:1124` 把 `app.stop_requested = True` → **整个任务被一句"平台判定存在刷课行为"误停**，用户完全无从判断真假。
- `683`：`"false"` → `True`，该字段虽暂未被消费（见 M1），但一旦有人用它判断"是否已达标结束"，就会全线误判。

**修复建议**：加一个归一函数，全文件统一用：

```python
def _as_bool(v, default=False):
    if isinstance(v, bool):
        return v
    if isinstance(v, (int, float)):
        return v != 0
    if isinstance(v, str):
        return v.strip().lower() in ("true", "1", "yes", "y")
    return default

# 631
    if _as_bool(js.get("isPausing")):
# 683
    out["endcaltime"] = _as_bool(js.get("endcaltime"))
# 405 同一并把字符串/布尔两种都收掉
    out["review"] = _as_bool(js.get("enableview"))
```

**验收**：`{"ret":0,"isPausing":"false"}` → `blocked=False`。

---

## H6 · high · 被停止的课时先计入 `way1_fail`/`way2_fail`，再把统计污染到底部文案

**位置**：`src/welearn_gui.py:991-997`；污染下游 `src/welearn_gui.py:2243-2251`

**问题**：

```python
991:            with stats_lock:
992:                counters["way1_ok" if r["way1"] else "way1_fail"] += 1
993:                counters["way2_ok" if r["way2"] else "way2_fail"] += 1
994:
995:            if r["stopped"]:
996:                app.message_queue.put({"type": "log_warning", "text": f'  ⏹ {loc} 已停止'})
997:                return
```

停止时 `r["way1"]=r["way2"]=False`（因为提前 return，根本没提交），于是先记两笔 fail，之后才判 `stopped`。

**影响**：按一次停止 → 底部统计显示"失败:2"，`curriculum_complete` 的 `stopped` 分支文案(2248)又会把 `way1_ok+way2_ok` 当"已完成提交次数"——两个数字都不代表真实情况。用户看到"失败"会以为提交被平台拒了，误判任务健康度。

**修复建议**：先判 stopped，再记账；并区分"未提交"：

```python
            if r["stopped"]:
                with stats_lock:
                    processed[0] += 0        # 由 finally 统一 +1
                app.message_queue.put({"type": "log_warning",
                                       "text": f'  ⏹ {loc} 已停止（已落库部分时长）'})
                return
            with stats_lock:
                counters["way1_ok" if r["way1"] else "way1_fail"] += 1
                counters["way2_ok" if r["way2"] else "way2_fail"] += 1
```

---

## H7 · high · 刷时长模式 finalize 缺 `endcaltime`：会话不显式结束

**位置**：`src/welearn_gui.py:696-706`（`welearn_time_finalize`）、调用处 `src/welearn_gui.py:1156-1159`

**问题**：

```python
699:    resp = session.post(AJAX_SCO_URL,
700:                        data={'action': 'savescoinfo160928', 'cid': cid, 'scoid': scoid,
701:                              'uid': uid, 'progress': progress, 'crate': crate,
702:                              'status': 'unknown', 'cstatus': cstatus, 'trycount': '0',
703:                              'session_time': session_time, 'total_time': total_time},
704:                        headers=_build_headers(...), timeout=15)
```

对照刷课模式的同一个 action（`561-567`）——那里是带 `'endcaltime': 'true'` 的。同一 action 两种载荷，说明该参数由客户端显式下发才生效。

**影响**：刷时长模式每节结束时没有显式 close，服务端 SCO 可能长期停留在"学习中"。下次 `getscoinfo_v7` 拿到的是"上次未正常结束"的状态（也正是 `592` 那段"学习数据不正确 → 补 startsco"补丁存在的原因），并可能让墙钟继续累计、产生超长 `total_time`（反而更容易被"时钟流速"校验命中）。

**修复建议**：

```python
def welearn_time_finalize(session, cid, uid, scoid, progress, crate, cstatus,
                          session_time, total_time, endcaltime="true"):
    resp = session.post(AJAX_SCO_URL,
                        data={'action': 'savescoinfo160928', 'cid': cid, 'scoid': scoid,
                              'uid': uid, 'progress': progress, 'crate': crate,
                              'status': 'unknown', 'cstatus': cstatus, 'trycount': '0',
                              'session_time': session_time, 'total_time': total_time,
                              'endcaltime': endcaltime, 'nocache': random.random()},
                        headers=_build_headers(...), timeout=15)
    return '"ret":0' in _text(resp)
```

> 注意：这里同时把裸 `resp.text` 换成 `_text(resp)`（见 M2/M3 的同类问题）。

---

## H8 · high · 时长上限 1500s 高于平台实测 1080s；刷时长模式完全忽略 `timelitsec`

**位置**：`src/welearn_gui.py:367-369`（常量）、`src/welearn_gui.py:481`（clamp）、`src/welearn_gui.py:1126-1140`（`_time_one` 等待循环）

**问题**：`DURATION_CAP = 1500`，而 `docs/PROTOCOL_FORENSICS.md:618` 记录单 SCO 封顶 1080s（`timelitsec` 实测值）。刷课模式 `481` 把 target clamp 到 1500，刷时长模式更彻底——`1126` `welearn_time_init` 只取 `cstatus/progress/session_time/total_time/crate`，**从不读 `timelitsec`**，`1097` 直接按用户输入 `learn` 秒硬等。

**影响**：
- 用户设 1500 或"极速"预设外的自定义长时长 → 多等 7 分钟，服务端一秒都不多记（`REACHED` 由 `timelitsec` 卡死）；
- 刷时长模式完全不自适应：课时只要 300s，也会硬睡 900s；课时要 1080s，设 600s 就永远学不满 → 反复"未达标"；
- 反过来 `_time_one` 也永远发现不了"平台其实早就够了"。

**修复建议**：

```python
# 1) 常量给出平台上限，clamp 用它
PLATFORM_SCO_CAP = 1080          # 实测单 SCO timelitsec 上限
DURATION_CAP = PLATFORM_SCO_CAP  # 367-369 处直接对齐，别再多等 420s

# 2) welearn_time_init 顺带回传 timelitsec
def welearn_time_init(...):
    ...
    req = welearn_sco_requirements(session, cid, uid, classid, scoid)   # 注意：H2 修完后再复用
    # 或直接解析 startsco 响应里的 timelitsec/useSeconds

# 3) _time_one 里按缺口收敛
    need = max(0, (cmi.get('timelitsec') or 0) - init_total)
    learntime = min(learntime, PLATFORM_SCO_CAP)
    if need:
        learntime = max(need, min(learntime, PLATFORM_SCO_CAP))
```

**验收**：课时 `timelitsec=1080` 时，设 600s 也应学到 1080（或至少提示"平台要求 1080s，当前设置不足"），而不是学 600s 就报"保存成功但未达标"。

---

# 3. medium

## M1 · medium · `heartbeat_full` 返回的 `seconds`/`ret==1` 被全链路丢弃

**位置**：`src/welearn_gui.py:661-693`

**问题**：`661` 精心返回 `{"ok","seconds","ticket","endcaltime"}`，`681` 取到服务端权威增量；但 `689-693` 的 `welearn_time_heartbeat` 只回传 `["ok"]`：

```python
692:    return welearn_heartbeat_full(...)["ok"]
```

`docs/PROTOCOL_FORENSICS.md:140`：`ret==1` 表示**计时被复位**（本次会话时长作废）。现在 `ret==1` 与 `ret==-1`、网络失败一样只表现为 `ok=False`，所有调用方（`501`、`514`、`1136`、`1148`、`1153`）都不看返回值。

**影响**：`elapsed` 是本地自增的时钟，与"服务端认账的时长"可以完全脱钩。心跳被复位十次，本地照样报"完成 +900s"，用户看到的成功是假的。

**修复建议**：

```python
def welearn_time_heartbeat(session, cid, uid, scoid, session_time, total_time,
                           timelitsec=0, endcaltime="false"):
    return welearn_heartbeat_full(...)          # 直接返回 dict

# 调用方
hb = welearn_time_heartbeat(session, cid, uid, scoid, str(elapsed), str(base_total+int(elapsed)),
                            timelitsec=timer_target,
                            endcaltime="true" if reached else "false")
if hb["seconds"]:
    base_total_srv = hb["seconds"]          # 以服务端增量校准
if not hb["ok"]:
    hb_fail += 1
    if hb_fail >= 3:
        result["note"] = "连续心跳失败，已提前结束本节"
        break
```

## M2 · medium · `'"ret":0' in text` 子串判成功（三处）

**位置**：`src/welearn_gui.py:557`、`src/welearn_gui.py:569`、`src/welearn_gui.py:706`

**问题**：`result["way1"] = '"ret":0' in _text(resp1)`。平台错误响应里也常带 `"ret":0`（如 `{"ret":-1,"msg":"...ret:0..."}`），而 `{"ret": 0}`（带空格）反而判失败。`rfind('{"ret"')` 那套解析已经有现成实现，两条路径判定口径不一致。

**修复**：统一用 `_last_json` + `_as_bool`：

```python
def _ret_ok(resp):
    return _last_json(_text(resp)).get("ret") == 0
```
三处替换为 `_ret_ok(resp1)` / `_ret_ok(resp2)` / `_ret_ok(resp)`。

## M3 · medium · `welearn_time_init` 仍在裸用 `resp.text` + 裸 `json.loads(...)['comment']`

**位置**：`src/welearn_gui.py:592`、`src/welearn_gui.py:599`、`src/welearn_gui.py:602-604`

**问题**：

```python
592:    if '学习数据不正确' in resp.text:
602:    back = json.loads(resp.text)['comment']
```

没有 `_text(resp)`（`102-110` 的解码修复），也没有 `KeyError`/`JSONDecodeError` 兜底。GBK/UTF-8 混编码时 `592` 的判定会失效；`602` 一旦缺 `comment` 就抛异常，被 `_time_one:1166` 记成 `[异常]` 并计入 `errors`。v3.5 A15（`docs/AUDIT_v35.md:457`）已提，v3.6 未修。

**修复建议**：

```python
    body = _text(resp)
    if '学习数据不正确' in body:
        ...
    try:
        back = _last_json(body).get('comment', '') or ''
        if 'cmi' in back:
            cmi = json.loads(back)['cmi']
            ...
    except (ValueError, KeyError, TypeError):
        return None
```

## M4 · medium · 正确率"固定值"校验了 50~100，"随机范围"没校验

**位置**：`src/welearn_gui.py:2046-2059`

**问题**：

```python
2046:                if self.rate_var.get() == "fixed":
2047:                    r = int(self.fixed_rate_entry.get())
2048:                    if not 50 <= r <= 100:          # ← fixed 有下限
...
2053:                else:
2054:                    lo, hi = int(self.rand_min_entry.get()), int(self.rand_max_entry.get())
2055:                    if lo > hi:                     # ← random 只查顺序
2058:                    self.curriculum_rate = [lo, hi]
```

**影响**：随机范围填 `10~20` 能通过校验 → 每节正确率 10~20% → 平台侧"完成但极低分"，是最显眼的异常特征。两条分支校验口径必须一致。

**修复**：

```python
                    if not (50 <= lo <= hi <= 100):
                        self._log("[!] 随机正确率需在 50~100 之间且下限≤上限", "log_error")
                        return
```

## M5 · medium · `_on_check_update` 在 UI 线程同步发请求

**位置**：`src/welearn_gui.py:2135-2147`

**问题**：`requests.get(..., timeout=10)` 直接在按钮回调里执行。断网/慢网 → 整个窗口冻结最长 12s，Windows 会给标题栏挂"未响应"。v3.5 A19（`docs/AUDIT_v35.md:556`）已提，未修。

**修复**：丢到线程 + 队列：

```python
    def _on_check_update(self):
        self._log("正在检查更新...")
        def work():
            try:
                r = requests.get("https://api.github.com/repos/xuebi0218/welearn-gui/releases/latest", timeout=10)
                tag = (r.json().get("tag_name") or "?").lstrip("v")
                self.message_queue.put({"type": "log", "text": f"最新版本: {tag}（当前: v3.6）"})
            except Exception as e:
                self.message_queue.put({"type": "log_error", "text": f"检查更新失败: {e}"})
        threading.Thread(target=work, daemon=True).start()
```

## M6 · medium · `_update_estimate` 忽略当前时长模式，且只在预设切换/建页时刷新

**位置**：`src/welearn_gui.py:1648-1663`；`src/welearn_gui.py:2029-2035`（同样的 `time_var` 判定已有正确写法可参考）

**问题**：`1650-1651` 无条件读 `time_min_entry`/`time_max_entry`。当 `time_var == "fixed"` 时，估算文案仍按随机框里的数字算；手动改输入框也不会重算（只在 `_on_preset_change:1646` 与 `_build_home_page:1596` 调用）。

**影响**：确认框(2074)、估算标签、实际执行三者数字不一致，用户对"要跑多久"的预期失真。

**修复**：

```python
    def _update_estimate(self):
        try:
            if self.time_var.get() == "fixed":
                lo = hi = int(self.fixed_time_entry.get())
            else:
                lo = int(self.time_min_entry.get())
                hi = int(self.time_max_entry.get())
        except (ValueError, AttributeError):
            lo, hi = 600, 900
```
并把 `_update_estimate` 挂到两个 entry 的 `<KeyRelease>` / `_on_time_mode_change` 末尾。

## M7 · medium · `_on_task_mode_change` 依赖 `winfo_children()[-4]` 硬编码索引

**位置**：`src/welearn_gui.py:1665-1671`

```python
1669:                                before=self.task_frame.winfo_children()[-4])
```

**影响**：当前 `task_frame` 子控件顺序恰好让 `[-4]` 命中第二个分隔线，功能正常；但只要有人往这个 frame 加一个控件（哪怕是个 hint label），`rate_panel` 就会插错位置或抛 `TclError`（消息路径里抛错 → 见 B3，会连带冻结 UI）。这类"靠兄弟数量定位"的写法是典型的定时炸弹。

**修复**：给锚点控件存引用：

```python
# _build_curriculum_tab 里创建分隔线时
        self.rate_anchor = sep2          # 命名保存
# 使用处
            self.rate_panel.pack(fill="x", padx=15, pady=(6, 0), before=self.rate_anchor)
```

## M8 · medium · 版本号残留 v3.5（三处）

**位置**：
- `src/welearn_gui.py:3` 文件 docstring 首行仍是 `Welearn 刷课工具 GUI v3.5`（`8` 行 v3.5 条目 + `9-10` 行 v3.6 条目共存，首行没改）
- `src/welearn_gui.py:1842` 设置页 `"当前版本: v3.5"`
- `src/welearn_gui.py:2157` 英文标题 `"Welearn Tool v3.5"`

**影响**：与 `1202`（title v3.6）、`1334`（侧栏 `v3.6 · 免费开源`）、`2143`（`当前: v3.6`）自相矛盾。用户报 bug 时会说自己用的是 v3.5，排障直接跑偏；`src/` 里还留着 v3.1~v3.4 四份备份 py，靠 docstring 判断"这份是不是当前版本"也会失效。

**修复**：抽一个常量 `APP_VERSION = "3.6"`，四处全部引用它（顺便解决下次漏改）。

## M9 · medium · 打包脚本第 10 行删除仓库维护的 spec → spec 与 bat 双份维护、必然漂移

**位置**：`build_welearn_gui.bat:10`；`WelearnGUI.spec:4`

**现状核对（用户点名项）**：两边**都正确且一致**——
- `WelearnGUI.spec:4` datas：`donate_qr.jpg`、`help_1.jpg`、`help_2.jpg`、`help_3.jpg`、`mascot.png`、`mascot_classic.png`（统一前缀 `src/`）
- `build_welearn_gui.bat:14` `--add-data`：同一组 6 个文件 + `--collect-data customtkinter` + `--hidden-import queue/PIL/PIL.Image/brotli`
- 两边都**不含** `nobi.png`（已弃用），`help_1~3` 与 `donate_qr` 都在。

**问题**：

```bat
10: if exist WelearnGUI.spec del /q WelearnGUI.spec
14: pyinstaller --clean --onefile --windowed ... src\welearn_gui.py
```

第 10 行把仓库里那份 spec 删掉，第 14 行再用 CLI 参数现场生成一份新的。**仓库里的 `WelearnGUI.spec` 因此永远不参与实际打包**，它的存在只制造"我改了 spec 为什么没生效"的困惑；反过来，谁用 `pyinstaller WelearnGUI.spec` 打包，就会得到一份与 bat 不同的产物（bat 加了 `--clean`）。

**修复（二选一）**：

```bat
:: 方案 A（推荐）：以 spec 为唯一真源
pyinstaller --clean WelearnGUI.spec
:: 并删除第 10 行的 del，spec 里的 datas/hiddenimports 就是权威

:: 方案 B：以 bat 为唯一真源，删掉仓库里的 WelearnGUI.spec 并加进 .gitignore
echo WelearnGUI.spec >> .gitignore
```

## M10 · medium · 仅刷时长模式下，确认框用 `daily_lesson_cap` 估算，但该模式根本不执行上限

**位置**：`src/welearn_gui.py:2072-2078`（文案）、`src/welearn_gui.py:1066-1113`（`_time_worker`，无 cap 逻辑）

**问题**：`2072-2075` 无论哪种模式都写"本次最多处理 {cap} 个课时（单日上限）… 满负荷约需 {est_h:.1f} 小时"。但 `_time_worker` 里没有 `all_lessons = all_lessons[:daily_cap]`——上限只存在于刷课模式（`961-967`）。

**影响**：刷时长模式选 24 节×15min 的课，确认框说"最多 24 节、约 6 小时"，实际会跑完全部 60 节 ≈ 15 小时。用户按确认框安排时间，结果远超预期（半夜还在跑）。

**修复**：文案按模式分支，或给 `_time_worker` 也加上同一套 cap：

```python
        if mode == "curriculum":
            msg_head = f"本次最多处理 {cap} 个课时（单日上限）\n"
        else:
            msg_head = "仅刷时长模式不受单日上限限制，将处理所选范围内的全部课时\n"
```

---

# 4. low

| # | 问题 | 位置 | 影响 | 修复 |
|---|---|---|---|---|
| L1 | `_rand_delay` 重复定义两次，后者覆盖前者；`_random_ua` 无调用；`hashlib`/`base64`/`secrets` 导入后未使用 | `src/welearn_gui.py:33-37` 与 `57-61`；`52-54`；`19`/`20`/`22` | 读者误以为两处行为不同；死导入增加打包体积与静态检查噪音 | 删掉 `33-37` 或 `57-61` 其一（保留带 docstring 的那份）；删 `_random_ua` 及三个未用 import |
| L2 | `elapsed += step` 无上界钳制，理论上末步可能落在 `target` 下方 1 ULP，导致再迭代一次 `sleep(1e-16)` | `src/welearn_gui.py:495-497` | 极端情况下多一次空转（不是死循环，`step>0` 恒成立） | `elapsed = min(float(target), elapsed + step)` |
| L3 | `desc_labels` 五元组列表构建后从未使用 | `src/welearn_gui.py:1684-1690` | 死代码，误导后续维护者以为慷慨页有未完成逻辑 | 删除该列表 |
| L4 | `mascot_classic.png` 被打进 exe 但源码零引用；`nobi.png` 文件仍留在 `src/` | `WelearnGUI.spec:4`、`build_welearn_gui.bat:14`、`src/nobi.png` | 白占体积；`nobi.png` 让"已弃用"的结论需要靠 grep 才能确认 | 从两处打包清单删 `mascot_classic.png`，`git rm src/nobi.png`（或挪进 `legacy/`） |
| L5 | "极速"预设写 120~300s 且注释称"明显快于平台要求时长"，但 `477-481` 的 adaptive 会把 target 顶回 `timelitsec`（实测 1080s），实际一点不快 | `src/welearn_gui.py:1611-1613` | 文案与实际行为相反，用户以为切了"极速"就会快 5 倍 | 文案改成"极速：仅减少冷却与并发间隔，单节仍按平台要求学满" |
| L6 | 完成文案把 `way1_ok + way2_ok` 当"提交次数"（同一次提交算了两次） | `src/welearn_gui.py:2248`、`2251` | 数字翻倍，用户以为刷了 2 倍课时 | 只报 `way1_ok`（或写"答题记录 {way1_ok} / 进度保存 {way2_ok}"） |
| L7 | `processed += len(batch)` 不看线程是否异常/提前 return | `src/welearn_gui.py:1107` | 失败也算进度，进度条 100% 但实际有课没跑 | 改为在 `_time_one` 的 `finally` 里对共享计数 +1（加锁） |
| L8 | `_time_one` 第 9 个参数 `_processed` 从未使用 | `src/welearn_gui.py:1116` | 签名噪音（L7 修完正好用上它） | 修 L7 时启用 |
| L9 | `Image.open(...)` 未 `close()`（一处为 `CTkImage` 直接吃句柄） | `src/welearn_gui.py:1274`、`1758` | onefile 模式下临时目录句柄滞留，极少数环境下删除失败 | `with Image.open(p) as im: im = im.copy()` 后再交给 `CTkImage` |
| L10 | `_build_home_page` 末尾用 `try: ... except Exception: pass` 包住 `_update_estimate()` 与 `preset_label.configure` | `src/welearn_gui.py:1595-1600` | 控件其实都已创建（不构成 AttributeError），但这个宽泛 `pass` 会吞掉估算逻辑里任何真实错误，且与 B1 属同一类"静默失败"模式 | 去掉 try/except，或 `except Exception as e: self._log(f"[UI] 估算初始化失败: {e}", "log_error")` |

---

# 5. 与 v3.5 审计的对账（v3.6 到底修了什么）

**已修（确认）**

| v3.5 编号 | 内容 | 证据 |
|---|---|---|
| A1 | 刷新失败无终态 → 永久锁死 | `thread_refresh_courses:872/877` 发 `refresh_fail`，`_handle_message:2220-2222` 消费（闭） |
| A2 | 工作线程异常逃逸无终态 | `thread_curriculum_execute:918-927`、`thread_time_execute:1055-1063` 双保险 `try/except/finally` + `task_finished`（闭） |
| A4 | 线程数不校验 → 除零/空 range | `_clamp(...,1,3)`（936/1070）+ UI 强制 1（2000-2007） |
| A8 | `processed[0] += 1` 未加锁 | `1017-1019` 在 `stats_lock` 内 |
| A11 | `score.raw` 硬编码 100 与 scaled 不一致 | `529` 两者同源 `crate_int`；且百分数口径与平台一致（见第 6 节） |

**仍未修（本次重新登记）**：A12 → H3；A13 → B2；A14（无重试/退避）→ 仍在（`553`/`561`/`699` 无重试）；A15 → M3；A19 → M5；A21 → B3；A22 → M2。
**新引入**：B1（`CONFIG_PATH` 丢失，纯回归）。

---

# 6. 已核查：用户点名但**不构成问题**的项（不必再查）

1. **`_on_start_task` 的 `lo/hi` 作用域**：`2029` 的 `for v in ([duration_val] if self.time_var.get()=="fixed" else [lo, hi])` —— `fixed` 分支只取 `duration_val`（`2011` 已赋值），`random` 分支只取 `lo/hi`（`2018` 已赋值），**两分支都不会 `UnboundLocalError`**。`2054` 复用 `lo/hi` 存正确率也不影响（时长已在 `2023` 落库）。`except ValueError`(2060) 覆盖 `int()` 失败，`AttributeError` 不会发生（控件必然存在）。**无问题。**
2. **`timer_target == 0`（`486`）**：`reached` 初值 False → 正常按用户时长循环；`513` `final_reached = bool(timer_target) and ...` 短路为 False → `endcaltime=false`，语义正确（"未达平台要求，不算真结束"）。**无问题**（但 `timer_target=0` 往往是 H1 解析失败的症状，需一并修）。
3. **`reached` 提前停表是否死循环**：`step = min(1.0, target - elapsed)` 恒 > 0，`elapsed` 单调增，`while elapsed < target` 必然终止；`reached` 由 `498` 在循环内抬升，`500` 只控制心跳。**不是死循环**（仅 L2 的 1 ULP 洁癖）。
4. **`scaled`/`raw` 用百分数（如 85）符合平台既有行为**：`docs/PROTOCOL_FORENSICS.md:304` 实证平台 `scaled = Math.round(r/e*100).toString()`，即 0~100 的百分数字符串。`529` 的写法与平台一致，**不该改成 0~1**。唯一可优化：真实客户端默认载荷只有 `{"scaled":"","raw":""}`（同文档 `:233`），`"min"/"max"` 是多余字段（无害，可留）。
5. **`_build_home_page` 末尾调 `_update_estimate` 是否 `AttributeError`**：`estimate_label`(1404)、`time_min_entry`(1554)、`time_max_entry`(1558)、`preset_label`(1382) 均在该调用点之前创建；且 `preset_seg.set("安全（推荐）")`(1400) 不触发 `command`（CTkSegmentedButton 的 `set` 不回调），所以 `_on_preset_change` 不会在建页中途提前跑。**无 AttributeError**（问题只是 L10 的静默吞错）。
6. **`messagebox.askyesno` 在无 GUI 环境下崩**：`2079` 在 Tk 主线程调用，是正确用法；若真无 GUI，程序在 `ctk.CTk()`(1201) 就已经失败，走不到这里。**不构成新增风险**（代价是模态阻塞 UI，可接受）。
7. **`_handle_message` 新增分支**：`refresh_fail`(2220-2222)、`task_finished`(2253-2256) 都存在且逻辑正确（`task_finished` 用 `if self.running` 做幂等，避免重复 `_set_running`）。**无问题**（真正的风险在 B3 的外层结构）。
8. **打包资源清单**：`WelearnGUI.spec:4` 与 `build_welearn_gui.bat:14` **都**包含 `mascot.png`、`mascot_classic.png`、`help_1~3.jpg`、`donate_qr.jpg`，且都不含 `nobi.png`。**一致**（问题只在 M9 的双份维护）。
9. **i18n `T` 字典 / `_NOBI_PATH` / nobi 引用**：全文 grep `T = {`、`def _(`、`_NOBI_PATH`、`nobi|NOBI`（含 spec/bat/README）**零命中** —— v3.6 已整体移除 i18n 字典与 nobi 逻辑。残留仅两处：`src/nobi.png` 文件本身（L4）、以及 `self.lang` 现在是"只切导航标签与标题、正文不翻译"的半残开关（若保留该开关，建议在设置页标注"仅界面标题，正文暂不翻译"，或直接下线）。
10. **锁与停止响应**：`counters` 全程 `stats_lock`（991/1013/1017/1048 读也没问题——此时工作线程已 join）；冷却 `1044-1046` 用 1s 步进检查 `stop_requested`，停止响应粒度 1s；`daily_lesson_cap` 截断在 `961-967`（先告警再切片，`total` 同步更新）。**线程模型本身没有竞态**，问题集中在 B2/B3/H6 的语义层面。

---

## 附：建议的修复顺序

1. B1（一行常量，修完立刻验证 `~/.welearn_config.json` 会生成）
2. H1 + H5（`_last_json`/`_as_bool` 两个小工具函数，一次性把 4 处解析收敛）
3. B2 + H7（提交/保存路径统一 finalize，两模式行为对齐）
4. B3 + H6（UI 泵兜底 + 统计口径）
5. H3 + H4（载荷与课时收集）
6. 其余 medium → low
