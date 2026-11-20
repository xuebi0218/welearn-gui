# Welearn 学习页协议取证报告（PROTOCOL FORENSICS）

> 对象：welearn.sflep.com「新目标大学英语（第二版）视听说」SCORM 2004 课时播放器 + LMS 端
> 方法：本机静态逆向（不联网、不发写请求）。证据分三级：
> - **【JS】** 本机前端代码直接可读的事实（给出文件+行号/字节偏移）
> - **【实证】** 本仓库 `docs/v3.x_FIX_REPORT.md` 与历史会话日志中记录的真实接口返回
> - **【推断】** 由 action 命名/调用形态合理推导，尚无可抓包复核
>
> 取证素材清单
> | 素材 | 性质 | 说明 |
> |---|---|---|
> | **`Welearn-Gui/tools/studycourse.html`（286,616 B，4470 行）** | **宿主页（LMS 端真身）** | **`StudyCourse.aspx` 的完整存档：心跳/开课/收尾/挂机检测/ticket 全在这里，是本次取证的骨干证据** |
> | `sco_main.js`（383,036 B，11 行压缩） | SCO 端 | 课时内容播放器，AngularJS，**只做 SCORM API shim** |
> | `Welearn-Gui/tools/lms.js`（64,890 B，**GBK 编码**） | LMS 端 | `API_1484_11` 的 LMS 侧实现（welearn 官方 lms.js），含 cmi 默认结构、只读键表 |
> | `sco_content.html` | 壳页 | 只加载 `vendor-base.js`/`vendor.js`/`main.js(=`sco_main.js`)` |
> | `Welearn-Gui/src/welearn_gui.py` | 客户端复刻 | 所有 `action` 的调用参数与顺序 |
> | `diagnose_submit*.py` / `test_*.py` | 探针 | 单步验证脚本 |
> | `docs/v3.2|v3.3|v3.4_FIX_REPORT.md`、`2026-06-17-002459-*.txt` | 实证记录 | 真实 `{"ret":-1,"msg":"学习数据不正确"}`、`seconds=35/36`、`learntime=00:00:35` |

---

## 0. 结论速览（TL;DR）

| 问题 | 结论 | 关键证据 |
|---|---|---|
| 谁写 `session_time` | **前端谁都不写**。SCO 里 `cmi.session_time` 是**虚拟键**，GetValue 时由宿主页 `GetSessionTime()` 返回变量 `curSessionTime` | `lms.js:163-175`；`studycourse.html:1396-1398`；`sco_main.js` 全文 0 次 |
| 服务端怎么算时长 | 双通道：①`startsco160928` → `savescoinfo160928` 的**墙钟差**落库为 `learntime`；②心跳/收尾响应里的 **`seconds`** 由客户端 `updatecmitime` 折进 cmi。**请求体里的 `session_time`/`total_time` 不参与计算** | 【实证】`v3.3_FIX_REPORT.md:26`；`studycourse.html:922-951,1009-1031` |
| `savescoinfo160928` 传时间吗 | **不传**。真实宿主页只传 `progress/crate/tid/status/cstatus/trycount/endcaltime`，时间靠响应 `seconds` 结算 | `studycourse.html:925-926` |
| 累计规则 | `total_time` **跨会话累加**（多次会话 elapsed 相加），服务端自算 | 【实证】日志 2118-2122（两次测试 → 01:12=72s） |
| 心跳周期 | 官方 **60000 ms**（`setInterval(...,60000)`）；`ret:0` 正常、`ret:1` = 重新开始计时 | `studycourse.html:866`、`:528-538` |
| 票据（getticket） | 有真身：服务端把 GUID 注入页面 `var studyTicket='52f56a76-...'`，心跳响应回吐 `reData.ticket` 与之比对，不等即判"正在学习另一课件"并强制 `EndSCO`。**本质是单账号会话互斥锁**，客户端从不提交票 | `studycourse.html:112`、`:517-524` |
| 单 SCO 学时上限 | `startsco` 返回 `timelitsec`（实测 1080s）与 `useSeconds`，`useSeconds>=timelitsec` 即 `endcaltime=true` 停表 | `studycourse.html:865-871`；【实证】`timelitsec=1080` |
| 完成条件 | 只要 `cmi.completion_status="completed"` + `cmi.progress_measure="1"` 被 commit/setscoinfo 落库即可；**与 interactions 数量无关** | 【JS】`sco_main.js`@197280 `C()`；【实证】v3.1 传空 interactions 仍 `ret:0` |
| `success_status` | 前端**从不设置**（0 命中），恒为默认 `"unknown"`；`savescoinfo` 原样回传该值 | `lms.js:1547` defaultData |
| 切屏/无操作检测 | **SCO 端无；宿主页有**：30 分钟无 `mouseover` → `CheckActive()` 强制 `EndSCO(true)` + 跳回主页；`visibilitychange`/`document.hidden` 仍为 0 命中（不检测切屏，只检测鼠标） | `studycourse.html:441-457`、`:459-492` |
| 显式封禁通道 | `action=isPausing`（锁 N 分钟 / 今日已锁定）与 `action=checkNoCaptcha`（强制滑块验证），均在进 SCO 前拦截 | `studycourse.html:587-614`、`:617-635` |
| 真正被识破的捷径 | ①startsco 后不等待直接 setscoinfo ②全程不心跳 ③同账号并发多 SCO（票互踢）④单 SCO 超 `timelitsec` ⑤`cmi.mode=browse` | 见 §6.3 |

---

## 1. 计时真相：`session_time` / `total_time` / `learntime` 三个数分别是谁的

### 1.1 SCO 端根本不碰时间字段【JS】

`sco_main.js` 全文出现过的 `cmi.*` 写入键只有下面这些（按字节偏移 `grep -bo` 统计）：

```
cmi.mode(4)  cmi.progress_measure(3)  cmi.interactions(3)  cmi.completion_status(3)
cmi.score.scaled(2)  cmi.score.raw(2)  cmi.interactions._count(2)  cmi.interactions.<n>.*
```

`cmi.session_time`、`cmi.total_time`、`cmi.success_status` **各 0 次**。也就是说：教学内容的 JS 自身既不知道、也不上报学习时长。

### 1.2 `session_time` 是"虚拟键"，由宿主页现算【JS】

`Welearn-Gui/tools/lms.js`（GBK 编码，行号为该文件真实行号）中 `LMS.prototype.GetValue` 对 `cmi.session_time` 做了**特殊分支**，不走 JSON 存储，而是回调宿主页：

```js
// lms.js:163-175
switch (parm) {
    case 'cmi.session_time':
        try {
            var ret = GetSessionTime(this);   // ← 宿主页实现，现算
        }
        catch (err) { if (err == "timeout") { this.errcode = 6011; return ""; } }
        this.errcode = 0;
        return ret;
```

同文件里 `GetSessionTime` 只留空桩，并注明"具体实现见页面"：

```js
// lms.js:1596-1617
/* 具体实现见页面 */
function GetStudyInfo(scoid){ return studyinfo; }
function SetStudyInfo(apiObj){ return true; }
//获取当前session学习时间
function GetSessionTime(apiObj){ return 0; }      // ← 桩，真实实现在宿主页
```

宿主页里的真实实现（`studycourse.html:1396-1398`）：

```js
function GetSessionTime(apiObj) {
    return curSessionTime;                        // ← 全局变量，只在心跳/收尾时被 seconds 累加
}
```

而 `curSessionTime` 的全部写入点只有三处（全部在宿主页）：
- `StartSCO()` 成功且非复习模式时 `curSessionTime = 0`（`:865`）
- `UpdateTotalTime_Client(seconds)`：`curSessionTime += seconds`（`:1035-1042`，心跳 `ret==0` 时调用）
- `UpdateTotalTime(seconds)`：同上，且额外 POST `action=updatecmitime`（`:1009-1031`）

> 结论：`session_time` 既不是 SCO 写的、也不是从库里读的，而是**宿主页自己累加服务端回吐的 `seconds`** 得到的。`SetStudyInfo(apiObj)` 才是 Commit 的唯一出口（`lms.js:286` `SetStudyInfo(this)`），真正的 POST 也在宿主页里。

### 1.3 `learntime` 是服务端时间差【实证】

`docs/v3.3_FIX_REPORT.md:26` 原文：

> 通过多轮 API 测试验证：客户端显示的 `learntime` 是服务端计算的 **`startsco160928` → `savescoinfo160928` 之间的实际时间差**，而不是 cmi JSON 中的 `session_time` 字段值。

历史会话日志 2118-2122 行（用户实测反证）：

> 不是0，但是是1min12 → 01:12 是服务端的 learntime（我们两次测试的累计服务端耗时约 72 秒），而不是我们传入的 session_time=31。

即：**服务端记录的是墙上时钟差；请求体里的 `session_time`/`total_time` 只是"客户端自称"，不参与计时。** 传 `"0"` 不会被扣分，传 `"99999"` 也不会加时长。

`total_time` 的跨会话累计同样由服务端完成（上面 35+36≈72s 的例子即两次会话累加），客户端传的 `init_total + elapsed` 只影响显示口径。

**补充（官方口径，2026-11 复核）**：除了"墙钟差"这条，官方还跑一条 **`seconds` 通道** —— 心跳/收尾响应里服务端回吐本次认定新增的秒数，客户端 `UpdateTotalTime(seconds)` 把 `curSessionTime += seconds` 后再 POST `action=updatecmitime` 写回 cmi（`studycourse.html:1009-1055`）。这说明官方设计是**服务端主导计量、客户端只做镜像**。两条通道指向同一个结论：客户端报什么时间都不算数。实测反证：一次探测上报 `session_time=600`、`total_time=1121`，服务端只回 `seconds=1`。

### 1.4 请求体里时间字段的实际位置（客户端复刻侧）

```python
# Welearn-Gui/src/welearn_gui.py:421-422（savescoinfo160928）
"session_time": str(learntime),
"total_time":   str(learntime),

# Welearn-Gui/src/welearn_gui.py:466-471（心跳）
data={'action': 'keepsco_with_getticket_with_updatecmitime',
      'uid': uid, 'cid': cid, 'scoid': scoid,
      'session_time': session_time, 'total_time': total_time},
```

`setscoinfo` 的 cmi JSON 里也带 `session_time`/`total_time`（`welearn_gui.py:376` 构造区），但按 §1.3 它们不构成计时依据；**真实宿主页 `EndSCO()` 根本不往 `savescoinfo160928` 传时间参数**（见 §1.5 与 §6），时间只由服务端在响应里回吐一个 `seconds`，再由 `updatecmitime` 折算进 cmi。

### 1.5 全部 action 清单与作用（按真实宿主页参数逐字抄录）

宿主页侧的 AJAX 全部打在同一入口（`Welearn-Gui/tools/studycourse.html:110`）：

```js
var ajaxUrl='../Ajax/SCO.aspx?uid='+userid;
```

即 `https://welearn.sflep.com/Ajax/SCO.aspx?uid=UID`（`welearn_gui.py:96` `AJAX_SCO_URL`），即使用 `POST` 也在 query 里带 `uid`。

| action | 真实参数（宿主页原样） | 作用 | 证据（`studycourse.html`） |
|---|---|---|---|
| `startsco160928` | `cid,scoid,uid,classid,tid=-1,nocache` | **开 SCO 会话 / 计时起点**。响应被读取的字段：`ret`、`enableview`、`timelitsec`、`useSeconds`、`configs.isscored` | `:847-892` |
| `keepsco_with_getticket_with_updatecmitime` | `uid,cid,scoid,session_time,total_time,timelimitsec,endcaltime,nocache` | **心跳三合一**：保活 + 下发/校验 ticket + 更新 cmi 时间。响应：`ret`(0 正常/1 重新开始计时)、`ticket`、`seconds`、`endcaltime` | `:501-553` |
| `updatecmitime` | `uid,cid,scoid,total_time,session_time,nocache` | **把服务端回吐的 `seconds` 折算进 cmi**：`curSessionTime += seconds`，再把新 `total_time/session_time` 写回服务端 | `:1009-1031` |
| `savescoinfo160928` | `cid,scoid,uid,progress,crate,tid=-1,status,cstatus,trycount,endcaltime,nocache` —— **不含时间参数** | **落库收尾**：写完成态/正确率/trycount，响应 `ret`、`isAutoCommit`、`seconds` | `:922-951`；关页版 `EndSCOBacon()` `:970-1010` |
| `setscoinfo`（由 `lms.js` 的 `Commit` 触发） | `data={cmi,adl,cci}`+`[INTERACTIONINFO]` | **写全量 SCORM JSON** + 答题明细 | `welearn_gui.py:408-412` |
| `getscoinfo_v7` | `uid,cid,scoid` | **读 cmi**：`{"comment":"<内嵌JSON字符串>"}`，再 `json.loads` | `welearn_gui.py:436-452` |
| `scoAddr` | `cid,scoid` | 取内容入口 `addr`（`//centercourseware.sflep.com/.../index.html#/2/4-3`），`addr.split('\|')[0]` | `:683-712`；`welearn_gui.py:513-531` |
| `isPausing` | `uid` | **刷课封禁查询**：`isPausing`、`pausingMinute`；>30 分钟显示"锁定 N 分钟"，否则"今日已锁定" | `:587-614` |
| `checkNoCaptcha` | `uid` | **人工验证闸门**：`status==0` → 弹滑块验证，拒绝进 SCO | `:617-635`、`:713` |
| `removeNoCaptcha` | `uid` | 结束会话时清除待验证标记（`EndSCO(true)` 内） | `:953-962` |
| `setnewword` | `uid,cid,data` | 生词本写回（`SetStudyInfo` 内） | `:1247` |
| `scoLeaves` | `cid,uid,unitidx,classid` | 目录列表：`learntime`/`iscomplete`/`learncount`/`isvisible` | `welearn_gui.py:320-325` |
| `courseunits` | `cid,uid` | 单元列表 | `welearn_gui.py:308` |
| `gmc` / `getcurriculum` / `getunit` / `getlesson` | 见 `CLAUDE.md` | 课程→单元→课时树（`authCourse.aspx`） | — |

> `160928` 是**服务端 action 名的一部分**（版本日期后缀），不能简写成 `startsco`。
> `savescoinfo160928` 与 `EndSCOBacon()` 的 `sendBeacon` 版本参数完全一致，差别只是后者带 `tid=-1` 且用 `FormData`（`navigator.sendBeacon(ajaxUrl, formData)`），为的是在 `beforeunload` 里抢在页面销毁前发出。

---

## 2. 心跳与票据（getticket）

### 2.1 票据有真身：服务端注入页面的 `studyTicket`

之前的判断（"本机没有任何 ticket 样本"）已被宿主页推翻。`studycourse.html:112` 里有一个**由服务端渲染进页面的全局变量**：

```js
var curSessionTime = 0;
var launchData = '';
var studyTicket = '52f56a76-525a-4311-b1ab-2e505e6fd416';   // ← GUID，服务端每会话下发
var timelimitsec = 0;
var endcaltime = false;//是否已经停止计时
var isScoredSco = false;
```

它不是常量：每个 SCO 会话一个 GUID，随 `StudyCourse.aspx` 的 HTML 一起下发。心跳响应里服务端**回吐当前有效票**，页面拿它与本地值比对（`studycourse.html:517-524`）：

```js
if (reData.ret == 0 || reData.ret == 1) {
    //CheckToken
    if ('20kggkt_4kh35o@pass.sflep.com' != '145Expert@sflep.com'
        && decodeURIComponent(reData.ticket) != studyTicket) {
        hasLeft = true;
        EndSCO(true);
        alert('检测到正在学习另一课件，将返回课程主页');
        ReturnMain();
    }
    ...
```

### 2.2 这条校验的真实语义：**单会话互斥锁**，不是鉴权

- **它防的不是脚本，是并发**：同一 `uid` 在别处（另一标签页 / 另一设备 / 另一个 SCO）开了会话，服务端就把票换新；旧页面下次心跳拿到的 `reData.ticket` 与本地 `studyTicket` 不等 → 判"正在学习另一课件" → `EndSCO(true)`（提交收尾 + `removeNoCaptcha`）→ `ReturnMain()` 跳回课程主页。
- **票不由客户端提交**：`KeepLearnTimeAndCheckToken()` 的请求参数里**没有 ticket**（只有 `uid,cid,scoid,session_time,total_time,timelimitsec,endcaltime,nocache`，`:514`）；票纯服务端下发、客户端只读比对。所以"伪造票"没有攻击面，"忽略票"= 放弃并发保护。
- **后门恒开**：`'20kggkt_4kh35o@pass.sflep.com' != '145Expert@sflep.com'` 是两个**写死的字符串字面量**比较（并非取当前用户邮箱），恒为 `true` → 票校验在生产上永远生效，不存在被绕过的测试分支。
- **有效期 / 刷新**：无显式 TTL 字段；票以**心跳为心跳**——每次 `ret==0` 心跳都可能换票，本地 `studyTicket` 变量此后就与真实票不同步（页面不更新它）。因此在真实页面里，**换票本身不触发踢出**，只有"服务端认为你当前的有效票 ≠ 你开页时那张"才触发。
- **复用规则**：同一 `(uid,cid,scoid)` 会话内有效；`startsco160928` 重开会话即换票；跨 scoid 天然不同票。
- **缺失后果**：不发心跳 → 无从比对（也不涨时长，见 §1.3）；心跳超时（`error` 分支 `status=="timeout"`）只置 `isTimeout=true`，**不判离开**。

> 落地含义（重要）：**同一账号同一时刻只能有一个活跃 SCO 会话**。GUI 若对同一 `uid` 并发跑多个课时，第二个 `startsco` 会把第一个的票顶掉，表现为第一个课时"莫名其妙"跳回主页、时长归零。这不是反检测，是并发互斥。

### 2.3 心跳的其余返回字段（可直接落地的语义）

| 返回字段 | 语义 | 宿主页处理 |
|---|---|---|
| `ret == 0` | 计时正常，本次授予 `seconds` 秒 | `isTimeout=false`；`if(reData.seconds>0) UpdateTotalTime_Client(parseInt(reData.seconds))`（`:528-533`） |
| `ret == 1` | **重新开始计时**（会话被打断后复位） | 仅 `isTimeout=false`，不累加（`:536-538`） |
| `seconds` | 服务端认定本次新增的学习秒数——**唯一可信的时间源** | 累进 `curSessionTime`，再由 `updatecmitime` 写服务端（§1.5） |
| `endcaltime` | 该 SCO 已达学时上限，服务端停表 | `endcaltime=true` + 弹 `#divAutoSaveWarning`「恭喜达到本练习学时」3 秒（`:540-546`） |
| `ticket` | 当前有效会话票 | 与 `studyTicket` 比对（§2.1） |

`ret` 不存在"没有心跳也照样计时"的路径：`KeepLearnTimeAndCheckToken()` 是唯一累加 `curSessionTime` 的入口（除 `EndSCO` 的一次性 `seconds`），而它由 `setInterval(..., 60000)` 驱动（`:866`）。

### 2.4 客户端里"票据"的另一个同名物（勿混淆）

`cci.service.user.token` 在 `sco_main.js` 偏移 372092 只被用于摄像头录像上传：

```js
var a = f.get("cci.service.user.token"),
    o = f.get("cci.service.camera.files."+x.index+".filename") + ".mp4";
i.upload({url: s, data: {name: o, email: a}, file: t, auto: !0})
```

`lms.js:746-752` 对它做 `GetCurrentUserToken(API_1484_11)` 取值。这是**用户令牌**，不是 SCO 会话 ticket。

---

## 3. 完成判定：`completion_status=completed` 到底需要什么

### 3.1 官方数据模型（LMS 端默认结构）【JS】

```js
// lms.js:1547  defaultData
{"cmi":{"completion_status":"not_attempted","interactions":[],"launch_data":"",
        "progress_measure":"0","score":{"scaled":"","raw":""},
        "session_time":"0","success_status":"unknown","total_time":"0","mode":"normal"},
 "adl":{"data":[]},
 "cci":{"data":[],"service":{...,"play":{"offline_media_id":"9999"},...},
        "learners":[],"retry_count":"0"}}
```

注意 `success_status` 默认 `"unknown"`，且 **SCO 全文 0 次写它** → 客户端的完成/得分只走 `completion_status` + `score`。

### 3.2 进度与完成的计算式（决定 `progress_measure`）【JS】

```js
// sco_main.js @197880-198115（updateScormInfo 内）
var c = _.reduce(L, function(e,t){ return !t.noProgress && t.isCompleted ? e+1 : e }, 0) / W;
i = _.isInteger(c) ? c.toString() : c.toFixed(2);
1 === c ? s = "completed" : c > 0 && (s = "incomplete");
R.scormInfo.progressMeasure = i;
R.scormInfo.objectiveProgressMeasure = o;
R.scormInfo.completionStatus = s;
```

- `W = i.data("progressTotal")`（@201843 附近初始化），即该课时 DOM 上声明的**总进度权重**。
- 分子 = 满足 `isCompleted && !noProgress` 的元素个数。
- **`c === 1` 才得到 `completed`；`0 < c < 1` 只是 `incomplete`。**
- `noProgress` 判定【JS】：`T = e.parents("[noprogress]").length > 0`、`O = angular.isDefined(e.attr("noprogress"))` → `y.noProgress = O || T`。

### 3.3 三处"强制置完成"的入口【JS】

```js
// @197280  function C(e)
function C(e){
  var t = Date.now().toString();
  e ? (n.set("cmi.progress_measure","1"), n.set("cmi.completion_status","completed"))
    : (n.set("cmi.progress_measure", R.scormInfo.progressMeasure),
       n.set("cmi.completion_status", R.scormInfo.completionStatus)),
  "objective" === R.type && (n.set("cmi.score.raw", R.scormInfo.score.raw),
                             n.set("cmi.score.scaled", R.scormInfo.score.scaled)),
  n.set("cci.submit_time", t), R.lastSubmitTime = t
}
```

调用点：

1. **提交按钮**：`function k(i){ ... C(), D(), n.commit(), R.isSubmitted=!0, ... }`（@195370 起）
2. **无交互页自动完成（3 秒）**：
   ```js
   // @203003-203020
   R.type = "no_interaction";
   "no_interaction" !== R.type || R.isBrowseMode ||
   ("completed" === R.scormInfo.completionStatus && "1" === R.scormInfo.progressMeasure) ||
   (j = setTimeout(function(){ C(!0), n.commit() }, 3e3))
   ```
3. **自动判分页（100 毫秒）**：
   ```js
   i.find("et-checking").length > 0 && !R.isBrowseMode && !R.isSubmitted &&
   c(function(){ C(!0), n.commit() }, 100)
   ```

`R.type` 的判定（同处上文）：`R.interactionIds.length > 0 ? "objective" : 0 === R.interactionIds.length ? "no_interaction" : "subjective"`。

### 3.4 `objective` 才带分数

```js
"objective" === R.type && (n.set("cmi.score.raw", ...), n.set("cmi.score.scaled", ...))
```

`score.scaled` 来自 `T()`（@197900 起）：

```js
e = _.reduce(L, (e,t)=> t.isScored ? e+t.weighting : e, 0);   // 总权重
r = _.reduce(L, (e,t)=> t.isScored ? e+t.score : e, 0);       // 得分
n = e > 0 ? Math.round(r/e*100).toString() : "0";             // scaled = 正确率%
```

计分元素判定（@前文）：`y.isScored = p.hasKey && C && I`，其中 `C = !angular.isDefined(e.attr("notscored"))`、`I = 0 === e.parents("[notscored]").length`。
→ **`isscored` 是内容包 DOM 属性；`startsco160928` 返回的 `configs.isscored` 是同一信息的服务端版本。**

### 3.5 结论表：完成到底依赖哪些字段

| 候选条件 | 是否必要 | 依据 |
|---|---|---|
| `cmi.completion_status = "completed"` | **必要** | 唯一被服务端读取的完成标志；`defaultData` 默认 `not_attempted` |
| `cmi.progress_measure = "1"` | **必要（口径一致）** | 客户端 `x()` 用它当提交闸门（<1 直接拒绝）；落库后目录页 `iscomplete` 也据此显示 |
| `cmi.interactions` 数量 ≥ N | **不必要** | 完成与答题数据是两条独立通道：`setscoinfo` 的 `[INTERACTIONINFO]` 只决定"答题记录"是否生成（v3.1 空串 → `ret:0` 但无答题记录） |
| `crate`（正确率） | **不必要** | 只写 `score`，与完成无关 |
| `success_status` | **不必要** | 前端从不设置，恒 `unknown` |
| `cmi.mode != "browse"` | **必要** | `R.isBrowseMode = "browse" === n.get("cmi.mode")`（@201843）；browse 模式下自动完成分支被短路 |
| 已存在 SCO 会话 | **必要** | 否则 `setscoinfo`/`getscoinfo_v7` 返回 `学习数据不正确`（§4） |

---

## 4. "学习数据不正确" 的触发条件

### 4.1 这个字符串不在任何前端 JS 里

`grep -c "学习数据不正确" sco_main.js` = **0**；`lms.js` = **0**。它是**服务端返回的 `msg`**，前端只是把它当普通文本处理。

### 4.2 真实返回体【实证】

```json
{"ret": -1, "msg": "学习数据不正确"}
```

（会话日志 2070 行；`Welearn-Gui/src/welearn_gui.py:440,447` 用 `if '学习数据不正确' in resp.text` 做字符串匹配。）

### 4.3 两个触发面（都已在代码里写了兜底）

**面 A：`getscoinfo_v7` 读不到会话数据** —— 该 SCO 从未建立过会话（或会话已失效）：

```python
# welearn_gui.py:436-448
resp = session.post(AJAX_SCO_URL, data={'action':'getscoinfo_v7', ...})
if '学习数据不正确' in resp.text:
    session.post(AJAX_SCO_URL, data={'action':'startsco160928', ...})   # ← 先开会话
    resp = session.post(AJAX_SCO_URL, data={'action':'getscoinfo_v7', ...})
    if '学习数据不正确' in resp.text:
        return None
```

**面 B：`setscoinfo` 时 `startsco` 到 `setscoinfo` 的间隔≈0** —— 服务端判定"这个学生不可能在 0 秒内学完并作答"，拒收整个 SCORM 包（含 interactions）：

- `docs/v3.3_FIX_REPORT.md:46`：

  > 当 `startsco` → `setscoinfo` 间隔太短时，服务端返回 `"学习数据不正确"`，SCORM 数据（含 interactions）不会被持久化。

- 会话日志 2208-2216（修复后对比）：

  ```
  [1] startsco160928        → ✅
  [2] 等待 35 秒             → (服务端计时)
  [3] setscoinfo            → ✅ (不再报"学习数据不正确"!)
  [4] savescoinfo160928     → ✅ seconds=36
  旧代码在 startsco 后立刻 setscoinfo → savescoinfo，服务端检测到实际耗时几乎为 0，拒绝了数据
  ```

### 4.4 工程含义

- 这条校验是**行为型**的（时间一致性），不是**内容型**的（不比对题目答案）。
- 一旦触发，`way1_ok`（setscoinfo）为 False 而 `way2_ok`（savescoinfo）可能仍 True → **完成状态会落库、但答题记录全丢**，表现为"课时显示已完成但正确率/答题记录为空"。现行代码用 `way1_ok and way2_ok` 双布尔分别统计（`welearn_gui.py:412,424`），必须两个都判。
- 保险值：`startsco → setscoinfo` 至少留 **≥ 25~35s**（已验证 35s 稳定通过）；官方客户端是真正做题，自然满足。

---

## 5. 离开 / 切屏 / 无操作检测

结论先给：**SCO 内容页（`sco_main.js`）没有；宿主页（`studycourse.html`）有，而且是真的会中断学习的**。

### 5.1 SCO 端：没有【JS，逐项 0 命中】

| 探测点 | `sco_main.js` 命中 | 说明 |
|---|---|---|
| `visibilitychange` | 0 | 无页面可见性监听 |
| `document.hidden` | 0 | 无 |
| `idle` / 无操作计时 | 0 | 无 |
| `pagehide` / `unload` | 0 | 无 |
| `onbeforeunload` | 2 | 仅 `a.terminate()`（§5.4） |
| `blur` | 4 | 全部是输入框行为：`commit-on-enter` 清空、填空失焦上报 |
| `focus` | 26 | 输入/面板焦点，与"是否在看"无关 |
| `setInterval` | 2 | ①音量图标 300ms 闪烁 ②摄像头帧加载轮询 ≤100 次 |

### 5.2 宿主页端：**30 分钟无操作强制踢出**【JS，决定性证据】

```js
// studycourse.html:441-457
/* 检查是否挂机不动，30分钟不动自动返回课程主页 */
var latestMoveTime = (new Date()).getTime();
function MoveMouse() {
    var d = new Date();
    latestMoveTime = d.getTime();
}
function CheckActive() {
    var d = new Date();
    if (d.getTime() - latestMoveTime > 1800000) {   // 30 分钟
        clearInterval(actTimerID);
        hasLeft = true;
        EndSCO(true);                                // ← 提交收尾
        alert('检测到已经30分钟没有进行学习，将返回课程主页');
        ReturnMain();                                // ← 跳回课程主页
    }
}
var actTimerID = window.setInterval("CheckActive();", 60000);//每分钟检测一次
```

- 阈值 `1800000 ms = 30 min`，粒度 60 s。
- 触发后的动作链：**停心跳 → `hasLeft=true` → `EndSCO(true)`（落库 + `removeNoCaptcha`）→ `alert` → `ReturnMain()` 跳走**。不是"仅前端提示"。

### 5.3 活动信号的喂食链路：iframe 里的 mouseover 冒泡成父页 click

```js
// studycourse.html:459-492
function MainFrameClick() {
    MoveMouse();                                  // ← 唯一刷新 latestMoveTime 的业务入口
}
function AttachClick(FrameWindow) {
    try {
        FrameWindow.document.body.onmouseover = new Function('parent.document.body.click();');
        FrameWindow.document.onkeypress = banBackSpace;
        FrameWindow.document.onkeydown  = banBackSpace;
    } catch (e) { }
    for (var i = 0; i < FrameWindow.frames.length; i++) {
        var frameObj = FrameWindow.frames[i];
        try { frameObj.document.body.onmouseover = new Function('parent.document.body.click();'); } catch (e) { }
        try {
            var cWindow = (frameObj.contentWindow || frameObj.contentDocument);
            cWindow.document.body.onmouseover = new Function('parent.document.body.click();');
        } catch (e) { }
    }
}
```

```html
<!-- studycourse.html:3688 -->
<iframe id="contentFrame" name="contentFrame" ... onload="AttachClick(contentWindow||contentDocument);" ...></iframe>
```

链条：**课件 iframe 内任意 `mouseover` → `parent.document.body.click()` → `MainFrameClick()` → `MoveMouse()` → `latestMoveTime = now`**。iframe 加载时注入，并递归注入到二级 frame。
→ 判定标准极低：**鼠标在课件区域划过一次即视为"在学习"**，不需要答题、不需要按键。
→ 纯 HTTP 复刻（本项目现行方式）**不执行这段 JS**，所以这条对它无效；但如果用 Playwright/Selenium 挂真页面，必须保证每 <30 min 有一次 mouseover，否则页面自己 `EndSCO` 掉。

### 5.4 离开/关页：两个钩子

```js
// studycourse.html:123-127
var isOnIOS = navigator.userAgent.match(/iPad/i) || navigator.userAgent.match(/iPhone/i);
var eventName = isOnIOS ? "pagehide" : "beforeunload";
window.addEventListener(eventName, function (event) { Leave(); });

// :436-439
function Leave() { if (!hasLeft) { EndSCOBacon(); } }     // sendBeacon 版 savescoinfo
```

```js
// :423-433  ReturnMain()
var hasLeft = false;
function ReturnMain() {
    sessionStorage.removeItem("lastscoid");
    //chrome页面离开事件，最新版chrome禁止异步调用ajax，所以返回课程主页需直接调用EndSco
    if (!hasLeft) { EndSCO(true); hasLeft = true; }
    location.href = 'http://welearn.sflep.com/student/course_info.aspx?cid=3222&classid=779946&nocache=' + Math.random();
}
```

`hasLeft` 是**幂等闸门**：无论从哪条路径离开（挂机、并发被顶、用户点返回、关标签页），`savescoinfo160928` 只发一次。

### 5.5 有没有"上报某个字段"？

- **没有**"离开次数 / 切屏次数 / 是否全屏"这类字段：`lms.js` 的 `defaultData`（`lms.js:1547`）与两版 `readonlywords`（`lms.js:10`、`1533`）都不含 visibility/idle 类键名。
- **真正上报的只有时间与结算标志**：`savescoinfo160928` 的 `endcaltime`、`seconds`、`trycount`、`cstatus`；`updatecmitime` 的 `total_time`/`session_time`。
- **显式的封禁通道是服务端行为分析，不是前端检测**：

```js
// studycourse.html:587-614  CheckPausing()（在 SelectSCOAfter / SelectSamePageSCO 里、loadSco 之前调用）
$.ajax({ async: false, url: ajaxUrl, type: "POST",
         data: "action=isPausing&uid=" + userid + "&nocache=" + Math.random(),
         success: function (reData) { isPausing = reData.isPausing; pausingMinute = reData.pausingMinute; } });
if (isPausing) {
    if (pausingMinute <= 30) alert("系统监测到刷课行为，锁定" + pausingMinute + "分钟");
    else                     alert("系统监测到刷课行为，今日已锁定");
    ReturnMain();
    return true;
}
```

```js
// studycourse.html:617-635  CheckNoCaptcha()
$.ajax({ ..., data: "action=checkNoCaptcha&uid=" + userid + ... , success: function (reData) { checkResult = reData.status; } });
if (checkResult == 0) { ShowNoCaptcha(); return false; }   // :713 弹 #modal-template-nocaptcha-pop 滑块验证
```

### 5.6 汇总：检测项 / 触发 / 后果 / 影响面

| 检测项 | 触发条件 | 后果 | 上报字段 | 是否影响纯 HTTP 复刻 |
|---|---|---|---|---|
| 挂机检测 `CheckActive` | 父页 `latestMoveTime` 超 30 min 未刷新 | `EndSCO(true)` + 跳主页 | 间接：`savescoinfo` 的 `seconds`/`endcaltime` | **否**（脚本不跑该页 JS） |
| 活动喂食 `AttachClick` | iframe mouseover 冒泡 | 仅刷新时间戳，无惩罚 | — | 否 |
| 会话票互斥 `studyTicket` | 同账号别处开 SCO → 票被换 | `EndSCO(true)` + "检测到正在学习另一课件" | 无独立字段，体现为会话重启 | **是**（§2.2，UID 并发必须为 1） |
| 刷课封禁 `isPausing` | 服务端判定"刷课行为" | 锁 N 分钟（≤30）或"今日已锁定" | 无，纯服务端判定 | **是**（不可绕，只能降低触发率） |
| 人工验证 `checkNoCaptcha` | 服务端要求验证 | 强制滑块验证，不进 SCO | 无 | **是**（脚本直接卡死在该 SCO） |
| 学时上限 `endcaltime` | `useSeconds >= timelitsec` | 停表，不再累加 | `endcaltime=true` | **是**（§6.4） |

> 所以准确的说法是：**SCO 内容页不检测你"在不在看"，但宿主页检测你"鼠标还动不动"，服务端检测你"时间怎么长的"**。前两条对纯 HTTP 复刻无效，后一条才是真正的约束。

---

## 6. 完整时序：`startsco160928` → `savescoinfo160928`

### 6.1 刷课（提交答案）时序

```
① 列表/定位
   GET  /ajax/authCourse.aspx?action=gmc                          → clist[{cid,per,name}]
   GET  /student/course_info.aspx?cid=CID                          → uid, classid
   GET  /ajax/StudyStat.aspx?action=courseunits&cid&uid             → units[{...}]
   GET  /ajax/StudyStat.aspx?action=scoLeaves&cid&uid&unitidx&classid
        → info[{id, iscomplete:"未完成", isvisible:"true", learntime}]
        （过滤：isvisible != 'false' 且 iscomplete 含"未"）
   POST /Ajax/SCO.aspx  action=scoAddr&cid&scoid                    → {addr}
        addr = "//centercourseware.sflep.com/.../index.html#/2/4-3"
        取 addr.split('|')[0]，hash #/{unit}/{file} → data/{unit}/{file}.html
        → 解析 <et-blank g>答案</et-blank> / <et-tof key="t|f"> / <et-choice key="...">

② 开会话（t0）
   POST /Ajax/SCO.aspx  action=startsco160928&cid&scoid&uid
        ← {configs:{isscored:"true"|"false"}, ...}      # 计时起点

③ 等待（服务端唯一认账的部分）
   sleep(learntime)                                   # 建议 30~35s，最小 ≥25s
   （可选）心跳：若 learntime > 40s，中途插
        POST action=keepsco_with_getticket_with_updatecmitime
             &uid&cid&scoid&session_time=elapsed&total_time=init_total+elapsed
        间隔 30~40s 随机

④ 写 SCORM 数据（t1）
   POST /Ajax/SCO.aspx  action=setscoinfo&cid&scoid&uid&isend=False
        data = json.dumps(cmi_obj) + "[INTERACTIONINFO]" + interactions_info
        cmi_obj = {cmi:{completion_status,interactions,launch_data,progress_measure,
                        score:{scaled,raw},session_time,success_status:"unknown",
                        total_time,mode:"normal"},
                   adl:{data:[]}, cci:{data:[],service:{...play:{offline_media_id:"9999"}},
                                       retry_count:"0",submit_time:""}}
        interactions_info = "0[]false[]false[]<escaped_response>[]correct$$1[]..."   # $$ 连接，开头不带 $$

⑤ 稍等
   sleep(0.3~0.4s)                                    # 让 setscoinfo 先落库

⑥ 收尾落库（t2）——**不带时间参数**（真实宿主页原样，studycourse.html:925-926）
   POST /Ajax/SCO.aspx  action=savescoinfo160928&cid&scoid&uid
        &progress=<cmi.progress_measure>&crate=<cmi.score.scaled>&tid=-1
        &status=<cmi.success_status>          # 实际恒 "unknown"
        &cstatus=<cmi.completion_status>      # completed
        &trycount=<cci.retry_count>&endcaltime=<false|true>
        ← {"ret":0,"isAutoCommit":"true"|"false","seconds":35}
          # 服务端 learntime = t2 - t0；seconds 是本次认定新增秒数

⑦ 时间入账（真实页面的两条分支）
   if (isAutoCommit == "true") { UpdateTotalTime_Client(seconds); Commit(""); }   # 只本地加，随后 Commit 触发 setscoinfo
   else                        { UpdateTotalTime(seconds); }                     # 本地加 + POST action=updatecmitime
   
   POST action=updatecmitime&uid&cid&scoid&total_time=<旧total+seconds>&session_time=<curSessionTime>

⑧ 校验
   POST action=getscoinfo_v7&uid&cid&scoid             → comment 内 cmi
   或   GET  StudyStat.aspx?action=scoLeaves&...        → learntime/iscomplete
```

> 关键点：**`savescoinfo160928` 本身不接收 `session_time`/`total_time`**（`studycourse.html:925-926` 的参数串里没有）。现行 `welearn_gui.py:417-424` 多传了这两个字段——服务端忽略它们、只回吐自己的 `seconds`，所以不致命，但**它不是计时手段**。真正把秒数写进 cmi 的是 `action=updatecmitime`（`studycourse.html:1017-1031`）。

### 6.2 刷时长（只续时间）时序 —— 以官方页面为准

官方实现的骨架（`studycourse.html:847-892` + `:501-553` + `:1009-1055`）：

```
① 开会话（t0）
   POST action=startsco160928&cid&scoid&uid&classid&tid=-1
        ← { ret:0, enableview, timelitsec:<每SCO学时上限秒>, useSeconds:<已用秒>,
            configs:{isscored:"true"|"false"} }
   客户端动作：
        endcaltime = false
        if (enableview == "true")  → 复习模式：只提示 #divReview 3s，**不开心跳**（不计时）
        else:
            curSessionTime = 0
            keeplearntimeid = setInterval('KeepLearnTimeAndCheckToken()', 60000)   // 官方周期 60s
            timelimitsec = reData.timelitsec
            if (timelitsec != 0 && useSeconds >= timelitsec) endcaltime = true     // 已超学时

② 每 60000ms 心跳（该 SCO 未达上限时）
   POST action=keepsco_with_getticket_with_updatecmitime
        &uid&cid&scoid&session_time=curSessionTime
        &total_time=<cmi.total_time 或 curSessionTime>
        &timelimitsec=<timelitsec>&endcaltime=<true|false>
        ← { ret:0|1, ticket, seconds, endcaltime }
   客户端动作：
        校验 ticket（§2.1）
        ret==0 → curSessionTime += seconds        // UpdateTotalTime_Client，注意只加不传
        ret==1 → 视为重新开始计时，不累加
        reData.endcaltime → 置 endcaltime=true + 弹「恭喜达到本练习学时」

③ 结束（用户离开 / 挂机 30min 被踢 / 点返回）
   POST action=savescoinfo160928&...&endcaltime=<true|false>
        ← { ret:0, isAutoCommit, seconds }
        seconds → UpdateTotalTime(seconds) → POST action=updatecmitime
                                            &total_time&session_time
   if (endSession) POST action=removeNoCaptcha&uid        // 释放人工验证占位
```

**上限闸门（实证 + 代码）**：`startsco160928` 返回 `timelitsec`（实测某 SCO 为 **1080 秒**）与 `useSeconds`；`useSeconds >= timelitsec` 时客户端立刻 `endcaltime=true`，此后服务端心跳回 `endcaltime=true` 停表。**所以单个 SCO 不可能被刷过 1080s（18 分钟）**，想凑 2 小时必须换 SCO。

**服务端不信任大数（实证）**：一次探测中客户端上报 `session_time=600`、`total_time=1121`，服务端只回 `seconds=1`。即 `seconds` 由服务端按自身计时节奏授予，客户端报多少都不算数。

对照现行实现（`welearn_gui.py:893-937`，`next_heartbeat = random.randint(30,40)`）：节奏比官方更密（更安全），但**只判 `'"ret":0' in resp.text`，不解析 `seconds`、不调 `updatecmitime`** —— 时间靠 `savescoinfo` 的墙钟差兜底，能用但不是官方口径。

### 6.3 必定被服务端识破的"偷懒捷径"

| # | 捷径 | 服务端如何识破 | 后果 | 证据 |
|---|---|---|---|---|
| 1 | `startsco` 之后**不 sleep** 直接 `setscoinfo` | 墙钟差 ≈0，与"完成 N 题"矛盾 | `{"ret":-1,"msg":"学习数据不正确"}`，**整个 SCORM 包（含 interactions）不落库** | §4.3 |
| 2 | 只发 `savescoinfo160928` 不 `startsco` | 无会话，cmI 读不到/写不进 | 同上；`getscoinfo_v7` 直接报错 | `welearn_gui.py:440` |
| 3 | 只 `startsco`+`savescoinfo`，**全程不心跳** | 会话过期，时间不累计 | `ret:0` 但 `learntime` 不涨 | v3.4 结论 |
| 4 | 心跳间隔 ≥ 60s（官方周期正是 60s，再长就漏） | 短课时内一次都不触发 | 该课时时长为 0 / 只拿到 1 次 `seconds` | `studycourse.html:866`；`v3.4_FIX_REPORT.md:15` |
| 5 | `session_time` / `total_time` 传大值想一次刷满 | 服务端只按自身节奏授予 `seconds` | 白传（实测 `st=600, tt=1121 → seconds=1`） | §6.2【实证】 |
| 6 | `cmi.mode` 传 `"browse"` | `R.isBrowseMode` 短路自动完成；服务端也按预览处理 | 不计分、不自动完成、时长通常不计 | §5.4 |
| 7 | `setscoinfo` 的 data 只传 `[INTERACTIONINFO]` 前半段或后半段为空 | 服务端按 `{JSON}[INTERACTIONINFO]{info}` 切分；空后半段 → `ret:0` 但**不生成答题记录** | 课时完成但正确率/答题明细为空 | v3.1/v3.2 实证 |
| 8 | `interactions_info` 里 `learner_response` 不做 `escape()` | 含 `[]`/`$$`/中文会破坏分片格式 | 答题记录错位或丢失 | `welearn_gui.py:490-500` `_js_escape` |
| 9 | 分数自报 `crate=100` 但 `cmi.score.scaled` 与之一致性无关 | 两处都会写；`savescoinfo` 的 `crate` 覆盖显示值 | 表面 100%，但客观题"只能提交一次"后无法改 | `sco_main.js` `x()`：`e.reject("客观题的作答只能提交一次")` |
| 10 | 重复提交同一 SCO | `cci.retry_count` 自增（`n.set("cci.retry_count", Number(o)+1)`）+ 服务端 `trycount` | 客观题被锁：`"客观题的作答只能提交一次"` | `sco_main.js` `k()` |
| 11 | **同账号并发跑多个 SCO** | `studyTicket` 被后开的会话换新，旧会话下一次心跳即判"正在学习另一课件" | 旧 SCO 被 `EndSCO` 强制收尾，时长停在中途 | §2.2；`studycourse.html:517-524` |
| 12 | 单 SCO 想刷过 `timelitsec` | `useSeconds >= timelitsec` → `endcaltime=true` 停表 | 该 SCO 封顶（实测 1080s），多余秒数不记 | `studycourse.html:865-871`【实证】 |
| 13 | 高频 / 规律地连刷多个 SCO | 服务端 `isPausing` 行为判定（与前端无关） | 锁 N 分钟（≤30）或"今日已锁定"，账号整体进不去 SCO | `studycourse.html:587-614` |
| 14 | 已被风控仍继续硬刷 | `checkNoCaptcha` 返回 `status==0` | 每次进 SCO 被滑块验证挡住，脚本直接卡死 | `studycourse.html:617-635`、`:713` |
| 15 | 只发 `savescoinfo`，既不心跳也不 `updatecmitime` | 时间只走 `seconds → updatecmitime` 通道 | `ret:0` 但 `learntime` 不增长 | §1.5、§6.2 |

### 6.4 最小间隔汇总（可直接抄进代码）

| 边界 | 最小/建议值 | 依据 |
|---|---|---|
| `startsco → setscoinfo` | **≥ 25s，建议 30~35s** | §4.3 实证（35s 通过，≈0 被拒） |
| `startsco → savescoinfo` | 自然满足（含上一条） | 服务端以 t2-t0 计 learntime |
| `setscoinfo → savescoinfo` | **0.3~0.4s** | `welearn_gui.py:414` |
| 心跳间隔 | 官方 **60000ms**；复刻建议 **30~40s**（更密更稳，硬上限 <60s） | `studycourse.html:866`；`welearn_gui.py:910,924` |
| 心跳次数 | ≥2（开工 + 收尾）；`learntime > 70s` 时中间再插 | `welearn_gui.py:905-929` |
| 单 SCO 学时 | **≤ `timelitsec`（实测 1080s）**，`useSeconds>=timelitsec` 即停表 | `studycourse.html:865-871` |
| 单账号并发 SCO | **必须 = 1**（`studyTicket` 互斥） | §2.2 |
| 挂机上限 | 真实页面 30 min 无 mouseover 即被踢；复刻无此约束但要保持会话不断 | `studycourse.html:441-457` |
| 线程错开启动 | 0.1~0.5s（跨账号才有意义，同账号不许并发） | `welearn_gui.py:953` |
| 同一 SCO 重复提交 | 客观题只允许一次 | `sco_main.js` `x()` |

---

## 7. 交互数据结构（答卷落库的完整契约）

### 7.1 SCO 侧写入的 interaction 字段【JS】

```js
// sco_main.js @166920-167470  saveInteraction
var o = ["id","type"],
    s = ["weighting","learner_response","result","description",
         "play_count","record_count","isshared","isdifficult"];   // 仅当 angular.isDefined 才写
t = g(e.id);                                    // 已有则覆盖同 id，否则追加 _count
angular.forEach(o, ...); angular.forEach(s, ...);
angular.isArray(e.pattern) && angular.forEach(i, function(e,n){
    _.set([a,t,"correct_responses",n,"pattern"].join("."), e) });
```
索引查找（`h()`/`g()`）先试 `cmi.interactions` 数组 `findIndex`，再退化到 `cmi.interactions.{n}.id` 与 `cmi.interactions._count`。

> `latency` **不在** SCO 写入字段表（`grep -c latency sco_main.js` = 0）；但服务端读回的 interaction 里带 `latency:"PT8S"`【实证，日志 2100 区】——说明 latency 由服务端/宿主页按会话时间折算，客户端无法伪造。

### 7.2 `[INTERACTIONINFO]` 文本格式【实证 v3.2】

```
{SCORM_JSON}[INTERACTIONINFO]0[]false[]false[]%u4F60%u597D[]correct$$1[]false[]false[]A[]wrong
                               └ i ┘└isshared┘└isdifficult┘└response┘└result┘
```
- 项间用 `$$` 连接，首项前**不带** `$$`
- `response` 必须走 JS `escape()` 编码（`welearn_gui.py:490-500` `_js_escape`：保留 `0-9A-Za-z@*-_+./`，其余 `<256` 转 `%XX`）
- 无交互的课时，后半段可空，但**分隔符本身必须存在**（v3.2：服务端按该串切分）

---

## 8. 未解项与验证建议（诚实清单）

> 已结案项（原列在此，现已有证据）：宿主页 `StudyCourse.aspx`（存于 `Welearn-Gui/tools/studycourse.html`，4470 行）已确认心跳周期=60000ms、"离开检测"=30min 挂机 + iframe mouseover、ticket=`studyTicket` GUID 比对。以下只留仍未闭环的。

| 项 | 现状 | 如何补证（只读，不发写请求） |
|---|---|---|
| `studyTicket` 的 TTL | 页面无过期字段；靠每次心跳回吐新票，旧票自然失效 | 抓两次同 SCO 心跳响应，比较 `ticket` 是否变；再开第二标签页观察何时开始返回新票 |
| `startsco160928` 完整响应结构 | 已知 `ret`/`enableview`/`timelitsec`/`useSeconds`/`configs.isscored`，其余字段未逐一记录 | dump 一次完整响应体存档 |
| `timelitsec` 是否恒定 1080 | 只在少数 SCO 上实测到 1080 | 跨单元抽样读 `timelitsec`，看是否随课时类型（阅读/听力/测试）变化 |
| `seconds` 的授予算法 | 已知"不信任客户端大值"，但**不知其按墙钟差、按心跳次数、还是按固定步长** | 对照实验：同一 SCO，A 组 60s 心跳 ×2，B 组 60s 心跳 ×1 但总时长相同，比较累计 `seconds` |
| `isPausing` 的触发阈值 | 完全服务端黑盒，页面只读结果 | 无法只读补证；只能观察被锁频率与操作强度的相关性 |
| `checkNoCaptcha` 的触发条件 | 同上 | 同上 |
| 刷课模式下最短通过间隔的精确下界 | 只验证了 ≈0 被拒、35s 通过 | 二分 5/10/15/20/25s 各一次（读 `seconds` 回显） |

---

## 9. 对客户端落地的直接结论（可直接改代码的清单）

| # | 结论 | 对应改法 |
|---|---|---|
| 1 | `savescoinfo160928` 不收时间，时间靠 `seconds` + `updatecmitime` | 收尾后解析响应 `seconds`，调一次 `action=updatecmitime&uid&cid&scoid&total_time=<旧+seconds>&session_time=<累计>`；现有 `savescoinfo` 里的 `session_time`/`total_time` 可留可删（服务端忽略） |
| 2 | 单 CSV/单账号并发 = 1 | UI 的"线程数"若作用于**同一个 uid**，必须锁成 1；多线程只在多账号时开放，否则触发 `studyTicket` 互踢，前面已刷的时长停在中断点 |
| 3 | 单 SCO 学时封顶 `timelitsec`（实测 1080s） | 单课时长设置上限按 `min(desired, timelitsec)` 截断；想凑总时长只能多 SCO，不能拉长单 SCO |
| 4 | 心跳周期官方 60000ms | 复刻取 30~40s（更保险，硬上限 <60s）；每次心跳后判 `ret`：`0` 正常、`1` = 计时被复位，需重新 `startsco` |
| 5 | `startsco → setscoinfo` 必须留 ≥25s | 已有实现可保留（30~35s）；这是唯一被抓到过的硬校验（`学习数据不正确`） |
| 6 | 有 `isPausing` / `checkNoCaptcha` 两道服务端闸门 | 每次 `startsco` 前先探一次 `isPausing`；若 `isPausing=true` 立即停手（锁 N 分钟或今日已锁定），继续刷只会加重；`checkNoCaptcha` 返回 `status==0` 时该 SCO 直接跳过 |
| 7 | 完成与答题是两个通道 | `completion_status=completed` 只需 `progress_measure="1"`；答题记录取决于 `[INTERACTIONINFO]` 后半段，两者必须分别判 `way1_ok`/`way2_ok` |
| 8 | 纯 HTTP 复刻不受 30 分钟挂机检测影响 | 无需模拟 mouseover；但**不要**用 Playwright/Selenium 挂真页还指望自动过挂机检测 |

---

## 附录 A：证据文件-行号索引

| 结论 | 位置 |
|---|---|
| **宿主页全量存档（4470 行）** | `Welearn-Gui/tools/studycourse.html` |
| `ajaxUrl` / `curSessionTime` / **`studyTicket`** / `timelimitsec` / `endcaltime` 全局量 | `studycourse.html:110-118` |
| `pagehide`/`beforeunload` → `Leave()` | `studycourse.html:123-127` |
| `ReturnMain()` + `hasLeft` 幂等闸门 | `studycourse.html:423-433` |
| `Leave()` → `EndSCOBacon()` | `studycourse.html:436-439` |
| **30 分钟挂机检测 `CheckActive`/`MoveMouse`** | `studycourse.html:441-457` |
| **活动喂食 `MainFrameClick`/`AttachClick`** | `studycourse.html:459-492` |
| iframe `onload="AttachClick(...)"` | `studycourse.html:3688` |
| **心跳 `KeepLearnTimeAndCheckToken`（参数 + ticket 比对）** | `studycourse.html:501-553` |
| 刷课封禁 `CheckPausing`（`action=isPausing`） | `studycourse.html:587-614` |
| 人工验证 `CheckNoCaptcha`（`action=checkNoCaptcha`） | `studycourse.html:617-635`、`:713`、模板 `:3743` |
| 加载课件 `loadSco`（`action=scoAddr`） | `studycourse.html:683-712` |
| **开会话 `StartSCO`（`startsco160928` + `timelitsec`/`useSeconds`/`enableview`）** | `studycourse.html:847-892` |
| **收尾 `EndSCO`（`savescoinfo160928`，不含时间参数）** | `studycourse.html:895-968` |
| 关页版 `EndSCOBacon`（sendBeacon） | `studycourse.html:970-1010` |
| **时间结算 `UpdateTotalTime` → `action=updatecmitime`** | `studycourse.html:1009-1055` |
| `GetSessionTime(){ return curSessionTime; }` | `studycourse.html:1396-1398` |
| `divAutoSaveWarning`「恭喜达到本练习学时」 | `studycourse.html:3685` |
| `action=setnewword`（`SetStudyInfo` 内） | `studycourse.html:1247` |
| `session_time` 虚拟键（GetValue 特判） | `Welearn-Gui/tools/lms.js:163-175` |
| `GetSessionTime` 空桩"具体实现见页面" | `Welearn-Gui/tools/lms.js:1596-1617` |
| Commit → `SetStudyInfo` | `Welearn-Gui/tools/lms.js:270-297` |
| Terminate 语义 | `Welearn-Gui/tools/lms.js:118-146` |
| 只读键表（现行/旧版） | `Welearn-Gui/tools/lms.js:10`、`1533-1544` |
| cmi 默认结构 `defaultData` | `Welearn-Gui/tools/lms.js:1547` |
| `cmi.mode` 特殊分支 / token | `Welearn-Gui/tools/lms.js:746-752` |
| `C()` 强置完成 | `sco_main.js` @197280（字节偏移，下同） |
| 进度计算式 `c/W → completed` | `sco_main.js` @197880-198115 |
| `no_interaction` 3s 自动完成 | `sco_main.js` @203003-203020 |
| `et-checking` 100ms 强置 | `sco_main.js` @203040 附近 |
| 提交 `k()` + `retry_count++` | `sco_main.js` @195370 |
| 提交前校验 `x()`（"请完成所有题目后再提交"/"客观题的作答只能提交一次"） | `sco_main.js` @195400-196400 |
| "还有N题未完成" 提示 | `sco_main.js` @195179 |
| `isBrowseMode = "browse"===cmi.mode`、`isScored=hasKey&&!notscored` | `sco_main.js` @201843 |
| `saveInteraction` 字段表 | `sco_main.js` @166920-167470 |
| `onbeforeunload → terminate()` | `sco_main.js` app.run 段 |
| 提交三步 + sleep | `Welearn-Gui/src/welearn_gui.py:389-426` |
| `getscoinfo_v7` + 学习数据不正确兜底 | `Welearn-Gui/src/welearn_gui.py:436-448` |
| 心跳函数 | `Welearn-Gui/src/welearn_gui.py:464-472` |
| finalize | `Welearn-Gui/src/welearn_gui.py:475-485` |
| 刷时长主循环（心跳 30~40s、累加） | `Welearn-Gui/src/welearn_gui.py:893-937` |
| `generate_interactions` / `_js_escape` | `Welearn-Gui/src/welearn_gui.py:490-500`、`576-621` |
| learntime = startsco→savescoinfo 差值 | `Welearn-Gui/docs/v3.3_FIX_REPORT.md:26` |
| 间隔太短 → 学习数据不正确 | `Welearn-Gui/docs/v3.3_FIX_REPORT.md:46` |
| 心跳从未触发（55~65s 问题） | `Welearn-Gui/docs/v3.4_FIX_REPORT.md:15-39` |
| `[INTERACTIONINFO]` 真实分隔符 | `Welearn-Gui/docs/v3.2_FIX_REPORT.md:31-37` |
| 真实报错与修复对照 | `2026-06-17-002459-*.txt:2070, 2208-2216, 2240-2265` |
