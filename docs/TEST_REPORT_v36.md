# v3.6 实测记录（真实账号，2026-11-19）

> 账号：`<测试账号>`（课程 cid=3222，uid=13178431，classid=779946，6 单元）
> 目的：验证"按时长补齐 + 心跳入账 + 回读校验 + 闸门检测"是否真实生效。

## 1. 协议指纹核对

| 项 | 结果 |
|---|---|
| 登录 | 密码 SSO 登录成功，返回 1 门课程 |
| `isPausing` | `{"isPausing":false,"pausingMinute":0}` → 未被判定刷课行为 |
| `checkNoCaptcha` | `{"status":-1,"msg":""}` → 未要求滑块 |
| `startsco160928` | `{"ret":0,"timelitsec":1080,"useSeconds":539,...}` → 每课时要求 18 分钟 |
| 心跳响应 | `{"ret":-1}{"ret":0,"seconds":30,"ticket":"52f56a76-…"}` → 双段 JSON，`seconds` 为权威增量 |

## 2. 心跳是否真的记时长（以 `useSeconds` 为真值）

```
t0 startsco: useSeconds = 539
hb#1 st=30  → seconds 30
hb#2 st=60  → seconds 30
hb#3 st=90  → seconds 30
t1 startsco: useSeconds = 609   (+70)
```

结论：**服务端按两次心跳的墙钟差累加**，客户端上报的 `session_time/total_time` 不参与计算。
（课时列表里的 `learntime` 字段有明显延迟，不能用来判断，必须读 `useSeconds`。）

## 3. 普通提交（自适应关闭，等 60s）

```
requirements: timelitsec=1080, use_seconds=699
submit: way1=True way2=True target=60 verified=760 reached=False
耗时 65.1s
```

- 60 秒等待 → `useSeconds` 699 → 760（**+61s 全额入账**）。
- `reached=False` 说明时长未达 95%，提交的 `completion_status` 是 `incomplete`（严格模式生效，不谎报完成）。

## 4. 自适应补齐（按 timelitsec 缺口）

```
选定 m-3-3-10：use=714 need=1080 deficit=366
submit: target=366 verified=1069 / 1080  耗时 373.6s
```

结论：一次运行把缺口补到 1069s（99%），下一轮几秒即可补满。**自适应逻辑按预期工作。**

## 5. 中途停止是否落库（修 B2 后）

```
before: use_seconds=517
submit(stop_check 50s 后触发): stopped=True way1=True way2=True
after : use_seconds=567   (+50)
```

结论：停止不再白等，已学时长会先落库再退出。

## 6. GUI 冒烟

- 默认值：`rate=[80,92] dur=[600,900] threads=1 preset=safe cap=24`
- 预设切换：安全 → 标准，`cap` 24→36、预估文案同步更新
- 消息泵：`progress` + `task_finished` 后 `running=False`，控件恢复
- 页面切换 home/help/settings/donate 无异常
- 截图：`docs/ui_v36.png`（吉祥物"大肥鱼鲸鱼娘"、节奏卡片、预设分段按钮均正常渲染）

## 7. 打包

```
pyinstaller --onefile --windowed … --add-data "src/mascot.png;src/"
→ dist/WelearnGUI.exe  30.6 MB  启动正常（2 进程 = onefile 引导 + 主进程）
```

## 遗留观察

- 首段心跳前的时长可能被吞掉一小部分（第一次 `hb(st=0)` 只回 `seconds=0`），属服务端行为，客户端无法改变。
- 单课时跑满 1080s 需要约 18 分钟真实等待，这是平台设计的物理下限。

---

# v3.7 并行实测（2026-11-20）

## 1. 只发心跳、不提交 → 时长不落库

4 路各心跳 3×30s（心跳都返回 `seconds` 27~33），但随后读 `useSeconds` 全部 **+0**。
→ 心跳只是「续时」，真正写库要靠 `setscoinfo` + `savescoinfo160928`。所以并行必须**每路走完整提交流程**。

## 2. 2 路并发完整提交

```
before: m-3-3-16=713  m-3-3-17=606
墙钟 71s
m-3-3-16: 713 -> 775 (+62)  way1✓ way2✓
m-3-3-17: 606 -> 668 (+62)  way1✓ way2✓
```

## 3. 4 路并发完整提交

```
before: 775 / 668 / 605 / 603
墙钟 86s
m-3-3-16: 775 -> 836 (+61)
m-3-3-17: 668 -> 729 (+61)
m-3-3-18: 605 -> 666 (+61)
m-3-3-20: 603 -> 664 (+61)
闸门: isPausing=false
```

→ **线性扩展、零损耗**。每一路的时长都是服务端按墙钟真实授予的。

## 4. 走完整 worker 链路（含 GUI 线程/队列/统计）

```
[L1]…[L4] 四路同时开跑，各自 90s 目标
墙钟 107s，4/4 全部 way1✓ way2✓
m-3-3-21: 517 -> 875 (+358，含上一轮被中断运行残留)
m-3-3-22/23/24: 各 +92 / +91 / +92
curriculum_complete: way1_ok=4 way1_fail=0 way2_ok=4 way2_fail=0
```

→ 多路调度、错峰启动、独立 Session、进度统计全部正常。

## 5. 单次心跳的有效增量有上限

单路 195s 不心跳再补一次，只记 **151s**（约 77%）。
所以心跳间隔必须保持在 ~30s（v3.6 起 20~32s），拉长间隔会丢时长。

## 结论

| 手段 | 效果 | 风险 |
|---|---|---|
| 4 路并行 | 墙钟 ÷4（40 节 ≈ 3~4 小时） | 完成密度高于真人，6 路以上更显眼 |
| 拉长心跳间隔 | ❌ 反而丢时长（>150s 折损） | — |
| 篡改客户端时长 | ❌ 服务端只认自己的钟 | — |
