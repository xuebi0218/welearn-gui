# tools

开发期辅助脚本（不参与打包）：

| 脚本 | 用途 |
|---|---|
| `mkart.py` | 从本地开源桌宠素材裁帧，生成界面立绘帧与渐变装饰条 |
| `shot_ui.py` | 用 PrintWindow 抓取运行中的窗口截图（被遮挡也能抓） |
| `smoke_gui.py` | 构造实例做无头冒烟测试，检查默认参数、预估文案、消息处理 |
| `patch*.py` | 各版本的定点补丁脚本（改代码前先跑，改动处带断言） |
| `test_v36.py` / `test_adaptive.py` / `test_stop_finalize.py` | 协议层实测：提交、自适应补齐、停止落库 |
| `test_lanes.py` / `test_parallel*.py` / `test_worker_real.py` | 多路并行调度与真实并发验证 |
| `probe_concurrency.py` / `diag_heartbeat*.py` | 并发上限、心跳增量上限探测 |
| `live_recon*.py` | 登录与课程结构侦察 |

账号从环境变量读取：`WELEARN_USER` / `WELEARN_PASS`。仓库里不保存任何凭据。

`lms.js`、`studycourse.html` 等平台前端文件仅本地留存，已在 `.gitignore` 中排除。
