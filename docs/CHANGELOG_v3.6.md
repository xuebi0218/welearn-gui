# CHANGELOG

## v3.8（2026-11-20）——界面重绘

- 深海色系统一：顶栏渐变装饰条（青 → 靛 → 金）、主按钮与进度条配色替换掉原紫色。
- 侧栏立绘改为 6 帧 idle 动效（运行中加速），不再标注角色名与副标题。
- 窗口默认 1060×700，主页标题与说明重排，长文案拆句避免窄窗口裁切。
- 素材生成脚本 `tools/mkart.py`：从本地开源精灵图裁帧 + 生成装饰条/横幅。
- 隐私：所有测试脚本的账号密码改为环境变量（`WELEARN_USER` / `WELEARN_PASS`），文档脱敏。

## v3.7（2026-11-20）——并行提速

**背景**：v3.6 把「秒完成」改成了「真实学时」，代价是 40 节要跑 2~3 天。用户要求找回速度。
**实测结论**：`studyTicket` 互踢是浏览器 JS 层的行为（多标签才会弹框 + EndSCO），纯 HTTP 不受约束。

| 实验 | 结果 |
|---|---|
| 4 路并发，各心跳 3×30s（不提交） | 心跳返回 seconds 27~33，但 `useSeconds` 不变 → 光心跳不落库 |
| 2 路并发，各自完整提交 60s | 713→775、606→668，**各 +62s**，墙钟 71s |
| 4 路并发，各自完整提交 60s | 4 个课时全部 **+61s**，墙钟 86s，闸门未触发 |

**结论**：并行有效，且每一路的时长都是服务端按墙钟真实授予的——不是作弊速度，是「同时上 4 节课」。

改动：
- `_clone_session()`：每路一个独立 `requests.Session`（连接池/CookieJar 非线程安全），Cookie + UA 与主会话一致。
- `_curriculum_worker` / `_time_worker`：批处理改为**多路抢队列**（`cursor` + 锁），每路独立会话、独立心跳节奏、错峰启动（0~12s）、按完成数各自冷却。
- 并发上限 3 → **8**，默认 **4**（安全档 3 / 标准 4 / 极速 6）。
- GUI：并发输入框恢复可编辑，文案改为实测结论；预估耗时按路数折算（24 节 × 12 分钟 ÷ 4 ≈ 1.2h）。
- 帮助页订正旧结论：并发互斥只作用于浏览器 JS 层。

风险提示（没变）：并行不改变「每节课要花 18 分钟」这个事实，只改变你**一次能同时上几节**。
6 路以上完成密度明显高于真人，属于「更快被注意到」的区间，GUI 会在 >4 路时警告。

---

## v3.6（2026-11-19）

一句话：**从「快速把状态改成完成」改成「按平台真实学时安全地学完」。**

### 核心（协议层）

- **自适应补齐课时时长**：新增 `welearn_sco_requirements()`，从 `startsco160928` 读 `timelitsec`（要求秒数）与 `useSeconds`（已累计）。
  目标时长 = `max(用户设定下限, timelitsec − useSeconds)`，上限 1500s，达标即停表。
  不再固定 60~120 秒刷完 18 分钟的课（这是被时钟流速校验命中、隔天回滚的头号原因）。
- **边学边心跳**：等待期间每 20~32 秒发 `keepsco_with_getticket_with_updatecmitime`，结束时补一次；
  参数对齐官方（`timelimitsec`、`endcaltime`）。服务端按两次心跳的墙钟差累计，漏发即丢时长。
- **提交后回读校验**：新增 `welearn_verify_learntime()`，以 `startsco.useSeconds` 为真值
  （课时列表的 `learntime` 有数分钟延迟，用它判断会误报），并在入账延迟时补读一次。
- **闸门检测**：新增 `welearn_check_gates()`，每节课前查
  `isPausing`（刷课行为锁定 N 分钟 / 今日锁定）与 `checkNoCaptcha`（`status==0` 强制滑块），
  命中立即停止并在日志里说明要人工处理什么。
- **停止即落库**：`stop_check` 触发时先补心跳把已学时长入账再退出，不白学。

### 严格模式（不谎报完成）

- 时长没学满 `timelitsec × 0.95` 时，提交的 `completion_status` 是 `incomplete`、`progress_measure` 按实际比例，
  不再把「秒完成」的 `completed` 送给平台——这是最容易被风控识别的组合。
- 已实测：`useSeconds` 562 → 622（60s 学习全额入账），完成标记不写入，下次运行继续补齐。
- 代价：一个课时可能要跑 2~3 次才真正 "completed"，但这是**唯一不会被时钟流速校验一眼看穿**的做法。

### 稳定性（修 audit blocker）

- 刷新课程失败不再让界面永久灰死：新增 `refresh_fail` 终态消息。
- 所有工作线程包 `try/finally`，异常时也必发 `curriculum_complete` / `time_complete` + `task_finished`，
  控件状态一定恢复（此前线程抛错→控件永久 disabled→连窗口都关不掉）。
- 进度计数移入锁内（此前 `processed[0] += 1` 在锁外，进度到不了 100%）。
- 批次不再共享 deadline / 不再串行 join 造成「假超时 + 孤儿线程」；改为逐线程等待。
- 并发强制 1（平台 `studyTicket` 单账号互斥，多开互相顶掉时长）。
- 统一 UTF-8 解码（`_text()`）：`requests` 对无 charset 的响应会退回 ISO-8859-1，
  导致 `'我的主页'` / `'"clist":[]}'` 判定全部失效。
- JSON 解析全部加容错（`.get()` + `ValueError`），不再因一个字段缺失打死线程。
- 时长/正确率/并发输入全部校验（30~1500s、50~100%、并发固定 1），非法值不再静默变成 100。
- 刷时长模式修 `elapsed` 未初始化（`UnboundLocalError`）、心跳间隔 30~40 → 20~32。

### 体验（GUI）

- 新增「节奏与风险」卡片：安全（推荐）/ 标准 / 极速三档预设，一键同步正确率、时长、冷却、单日上限。
- 启动前显示预计耗时并二次确认（`messagebox.askyesno`），避免糊里糊涂跑一整晚。
- 新增实时预估文案：单节约 X~Y 分钟、单日上限 N 节 ≈ Z 小时、含冷却说明。
- 帮助页新增「为什么刷完当天没事、隔天却被清掉」与「本工具的做法」两节。
- 默认值全面调整：正确率随机 80~92%、时长 600~900s、并发 1、单日上限 24 节、每 4 节休息 7~15 分钟。
- 吉祥物 `nobi.png`（毛绒玩偶照片）→ **大肥鱼鲸鱼娘** `src/mascot.png`
  （取自本机 `@linxin666/dsh-pet` 开源素材 `whale-refined` spritesheet 第 1 帧，BSD-3-Clause，
  合成 256×256 透明底方形图）；另附水手服版 `src/mascot_classic.png` 备用。
- 打包配置同步：`build_welearn_gui.bat` 与 `WelearnGUI.spec` 都改为带 `mascot.png` / `mascot_classic.png`，
  并补 `--hidden-import brotli`（`Accept-Encoding` 含 br，缺它会解码失败）。

### 文档

- 新增 `docs/RISK_ANALYSIS.md`：记录被清/打回的全部机制、代码级证据、v3.6 对策与使用建议、无法规避项。
- 新增 `docs/AUDIT_v35.md`（审计报告）、`docs/PROTOCOL_FORENSICS.md`（协议取证）、`docs/ANTICHEAT_RESEARCH.md`（公开资料检索）。
- 诊断脚本：`tools/diag_heartbeat.py`、`tools/diag_heartbeat2.py`、`tools/test_v36.py`、
  `tools/test_adaptive.py`、`tools/smoke_gui.py`。

### 审计修复对照（docs/AUDIT_v36.md）

- B1 `CONFIG_PATH` 未定义 → 已补常量，配置写入改 tmp + `os.replace` 原子写。
- B2 停止时跳过 finalize → 改 `break`，统一走收尾心跳 + 提交，停止也落库（实测 +50s 入账）。
- B3 `_poll_queue` 无逐条 try → 单条消息异常不再打死整个消息泵。
- H1 `find('{"ret"')` 双段 JSON 解析失败 → 统一 `_last_json()`（rfind）。
- H2 校验接口会重置计时 → 保留 startsco 回读但只在提交后调用一次，并接受其副作用。
- H3 空 interactions 仍拼 `[INTERACTIONINFO]` → 已按需拼接。
- H4 `_collect_lessons` 盲扫 999 单元、单单元失败即中止 → 按实际单元数遍历，失败单元跳过并提示。
- H5 布尔字符串 "false" 被判真 → `_as_bool()` 归一。
- H6 停止的课时被算作失败 → 先判 stopped 再计数。
- H7 刷时长 finalize 缺 `endcaltime` → 已补。
- H8 `DURATION_CAP` 与实际要求不符 / 刷时长忽略 `timelitsec` → 上限提到 1800s，刷时长按差额截断、满足即跳过。

### 已知未闭环

- `startsco` 的 `seconds` 授予算法在服务端，客户端只能被动接收；首段时长可能被吞掉一部分。
- 客观题每课时只能提交一次，提交错了不可逆。
- 平台侧复核与校级处置无技术规避面。
