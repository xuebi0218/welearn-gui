# Welearn 刷课工具 — 项目文件汇总报告

## 项目简介

Welearn 自动化刷课 + 刷时长桌面应用。使用 CustomTkinter 构建 GUI，支持 Cookie / 账号密码登录，整合课程自动完成和时长刷取功能。

- **当前版本**: v3.1
- **主文件**: `src/welearn_gui.py`（~1500行）
- **打包输出**: `dist/WelearnGUI.exe`（~37MB，单文件免安装）
- **GitHub**: https://github.com/xuebi0218/welearn-gui

---

## 文件目录结构

```
welearn-curriculum-finsh-master/
├── PROJECT_OVERVIEW.md               # 本文件 — 项目汇总报告
├── CLAUDE.md                         # AI 助手快速上手指南
├── README.md                         # 原始项目说明（旧版，v0.7dev）
├── LICENSE                           # 开源许可证
├── FILE_STRUCTURE.md                 # 旧版文件结构说明（过时）
├── TEST_REPORT.md                    # 测试报告
├── .gitignore                        # Git 忽略规则
├── build_welearn_gui.bat             # PyInstaller 打包批处理脚本
│
├── .workflow/                        # CI/CD 流水线配置（Gitee Go）
│   ├── BranchPipeline.yml            # 分支构建流水线
│   ├── MasterPipeline.yml            # 主分支构建+发布流水线
│   └── PRPipeline.yml               # PR 自动化测试流水线
│
├── src/                              # ★ 源代码目录
│   ├── welearn_gui.py                # ★★★ GUI 主程序（核心，约1500行）
│   ├── WelearnCurriculumFinsh.py     # 原始命令行版脚本（遗留，v0.7dev）
│   ├── WelearnCurriculumFinsh.spec   # 旧版 PyInstaller 配置（过时）
│   ├── diagnose_sso.py              # SSO 登录诊断脚本 v1
│   ├── diagnose_sso2.py             # SSO 登录诊断脚本 v2
│   ├── diagnose_sso3.py             # SSO 登录诊断脚本 v3（最终版）
│   ├── sso_debug.txt                # 诊断输出 v1
│   ├── sso_debug2.txt               # 诊断输出 v2
│   ├── sso_debug3.txt               # 诊断输出 v3
│   ├── donate_qr.jpg                # 微信赞赏码图片（1037×830）
│   ├── help_1.jpg                   # 教程图1：F12 + Network（840×1401）
│   ├── help_2.jpg                   # 教程图2：刷新 + 找请求（840×1395）
│   └── help_3.jpg                   # 教程图3：定位Cookie（528×837）
│
├── dist/                             # 打包输出目录
│   ├── WelearnGUI.exe                # ★ 打包后的可执行文件（37MB）
│   └── te/                           # 教程资源
│       ├── te.txt                    # Cookie 获取教程文本（6步）
│       ├── 1.jpg                     # 教程截图1
│       ├── 2.jpg                     # 教程截图2
│       └── 3.jpg                     # 教程截图3
│
└── build/                            # PyInstaller 构建中间产物（不提交Git）
```

---

## 各文件详细说明

### ★ 核心文件

| 文件 | 用途 | 重要性 |
|------|------|--------|
| `src/welearn_gui.py` | GUI 主程序，整合所有功能（登录/刷课/刷时长/设置） | ⭐⭐⭐⭐⭐ |
| `dist/WelearnGUI.exe` | 打包后的可执行文件，用户直接运行 | ⭐⭐⭐⭐⭐ |

### 辅助文件

| 文件 | 用途 |
|------|------|
| `build_welearn_gui.bat` | 一键打包脚本。**注：当前版本缺少 `--add-data` 图片参数，需更新** |
| `src/donate_qr.jpg` | 赞助页面显示的微信赞赏码 |
| `src/help_1.jpg`~`help_3.jpg` | 帮助页面的 Cookie 获取教程截图 |
| `dist/te/te.txt` | Cookie 获取步骤文字说明 |
| `dist/te/1.jpg`~`3.jpg` | 原始教程截图（已被复制到 src/ 供 exe 打包） |

### 诊断/遗留文件

| 文件 | 用途 |
|------|------|
| `src/WelearnCurriculumFinsh.py` | 原始命令行版脚本。保留了基础的 API 调用逻辑，但已不再维护 |
| `src/diagnose_sso3.py` | SSO 登录逆向诊断脚本。通过尝试不同 POST 参数组合，发现正确字段名为 `Account`/`pwd` |
| `src/diagnose_sso.py` / `diagnose_sso2.py` | 早期诊断版本，已过时 |
| `src/sso_debug.txt`~`sso_debug3.txt` | 诊断脚本输出日志，仅供查问题参考 |
| `src/WelearnCurriculumFinsh.spec` | 旧版 PyInstaller 配置，不再使用 |

### CI/CD 配置

| 文件 | 用途 |
|------|------|
| `.workflow/BranchPipeline.yml` | Gitee Go 分支流水线（PHP 构建 + 制品上传） |
| `.workflow/MasterPipeline.yml` | Gitee Go 主分支流水线（编译 + 发布） |
| `.workflow/PRPipeline.yml` | Gitee Go PR 校验流水线 |

> 注：这些是 Gitee 平台的 CI 配置，GitHub 上可能需要改为 GitHub Actions。

### 文档文件

| 文件 | 用途 |
|------|------|
| `PROJECT_OVERVIEW.md` | 本文件 — 项目汇总报告 |
| `CLAUDE.md` | AI 助手快速上手指南 |
| `README.md` | 原始项目 README（v0.7dev，内容过时） |
| `FILE_STRUCTURE.md` | 旧版文件结构说明（过时，未包含 GUI 相关内容） |
| `TEST_REPORT.md` | 测试报告 |
| `LICENSE` | 开源许可证 |

---

## 模块功能总览

### `src/welearn_gui.py` 功能模块（按行号）

| 行号范围 | 模块 | 说明 |
|----------|------|------|
| 1-22 | 导入声明 | requests, customtkinter, PIL, threading, queue 等 |
| 24-50 | UA 轮换池 | 18 个浏览器 User-Agent（Chrome/Edge/Firefox/Safari/Opera） |
| 52-85 | 工具函数 | `_random_ua()`, `_rand_delay()`, `_build_headers()` — 反检测核心 |
| 87-100 | Cookie 解析 | `parse_cookie_string()` — 支持多种分隔符 |
| 102-150 | 会话验证 | `welearn_validate_session()` — 验证 Cookie 并获取课程列表 |
| 152-220 | SSO 密码登录 | `welearn_password_login()` — IdentityServer4 + PKCE 完整流程 |
| 222-260 | 登录验证 | `_verify_login()` — 统一的登录结果验证 |
| 262-330 | 课程/单元 API | `welearn_get_course_info()`, `welearn_get_units()`, `welearn_get_lessons()` |
| 332-410 | 刷课提交 API | `welearn_curriculum_submit()` — 双路径提交（方式1+方式2） |
| 412-480 | 刷时长 API | `welearn_time_init()`, `welearn_time_heartbeat()`, `welearn_time_finalize()` |
| 490-590 | 后台线程 | `thread_login()`, `thread_refresh_courses()`, `thread_fetch_units()` |
| 595-615 | 执行线程 | `thread_curriculum_execute()`, `thread_time_execute()` |
| 616-747 | 国际化文本 | `T` 字典（中文/英文），`_()` 辅助函数 |
| 750-799 | GUI 主类初始化 | `WelearnApp.__init__()` — 窗口、状态、参数初始化 |
| 800-830 | 侧边栏 | `_build_sidebar()` — 170px 宽，4 个导航按钮 + 版本号 |
| 831-852 | 内容区管理 | `_build_content()`, `_show_page()` — 页面切换 |
| 853-928 | 主页 | `_build_home_page()` — 登录面板 + 课程选择 + 选项卡 + 日志 |
| 930-968 | 刷课选项卡 | `_build_curriculum_tab()` — 正确率设置 + 进度条 + 统计 |
| 970-1014 | 刷时长选项卡 | `_build_time_tab()` — 时长设置 + 线程数 + 进度条 |
| 1016-1065 | 赞助页面 | `_build_donate_page()` — 赞赏文字 + QR 码 + "下次一定" |
| 1067-1115 | 帮助页面 | `_build_help_page()` — 6 步 Cookie 教程 + 3 张截图 + 注意事项 |
| 1119-1165 | 设置页面 | `_build_settings_page()` — 语言/主题/关于/GitHub 链接/检查更新 |
| 1167-1208 | 状态栏 + 工具 | `_build_statusbar()`, `_log()`, `_set_running()` |
| 1212-1271 | 事件处理 | 登录/课程选择/正确率/时长模式切换 |
| 1288-1340 | 启动操作 | `_on_start_curriculum()`, `_on_start_time()` |
| 1341-1370 | 停止/设置 | `_on_stop()`, `_on_lang_change()`, `_on_theme_change()`, `_on_check_update()` |
| 1380-1411 | 免责声明弹窗 | `_show_disclaimer()` — 启动时弹出，勾选后不再显示 |
| 1414-1470 | 消息处理 | `_poll_queue()`, `_handle_message()` — 线程安全 UI 更新 |
| 1479-1486 | 入口 | `run()`, `if __name__ == '__main__'` |

### 线程模型

```
主线程 (Tkinter UI)
  ├─ thread_login()          → 验证 Cookie/密码登录
  ├─ thread_refresh_courses() → 刷新课程列表
  ├─ thread_fetch_units()    → 获取选中课程的单元
  ├─ thread_curriculum_execute() → 逐课提交刷课
  └─ thread_time_execute()   → 多线程并发刷时长

通信: queue.Queue + root.after(100ms) 轮询
```

---

## 打包构建

### 完整命令

```bash
pyinstaller --clean --onefile --windowed \
  --name WelearnGUI \
  --add-data "src/donate_qr.jpg;src/" \
  --add-data "src/help_1.jpg;src/" \
  --add-data "src/help_2.jpg;src/" \
  --add-data "src/help_3.jpg;src/" \
  --collect-data customtkinter \
  --hidden-import queue \
  --hidden-import PIL \
  --hidden-import PIL.Image \
  src/welearn_gui.py
```

- `--windowed`: 无控制台窗口
- `--add-data`: 将图片资源打包进 exe，运行时通过 `sys._MEIPASS` 访问
- `--collect-data customtkinter`: 打包 CTk 主题文件
- 预计输出: `dist/WelearnGUI.exe` (~37MB)

### 注意事项

- 打包前确保 `dist/WelearnGUI.exe` 没有被运行或杀毒软件锁定
- 如遇 `PermissionError`，用 `taskkill /f /im WelearnGUI.exe` 结束进程
- Python 3.13.9 + PyInstaller 6.20.0

---

## SSO 登录机制（知识沉淀）

Welearn 使用 **IdentityServer4 + OIDC + PKCE（S256）** 认证：

1. `prelogin.aspx` → 302 重定向到 `sso.sflep.com/idsvr/connect/authorize`
2. `/connect/authorize` → 302 重定向到 `/Account/Login?ReturnUrl=...`
3. `/Account/Login` (GET) → 返回 SPA 页面（`transfer.html`）
4. `transfer.html` → 加载 `browser.min.js`，动态渲染 React 登录表单
5. POST `/Account/Login` → 提交 `Account` + `pwd` + `ReturnUrl`
6. 成功后 → 302 重定向到 `signin-sflep` → welearn 写入登录 Cookie

**关键发现**：
- POST 参数名是 `Account` 和 `pwd`（不是 `Username`/`Password`）
- 登录表单由 SPA（React）动态渲染，HTML 解析无用
- PKCE 的 `code_challenge`/`code_verifier` 由 ASP.NET 后端生成，存储在加密的 `state` 参数中，无法自行构造
- Cookie 登录比密码登录更安全（真实浏览器完整 SPA 指纹）

---

## 反检测措施

| 措施 | 实现位置 | 说明 |
|------|----------|------|
| UA 轮换 | `_USER_AGENTS[18]`, `_random_ua()` | 每次请求随机选取 |
| 延迟抖动 | `_rand_delay()` | 基于请求数量指数退避 + 随机偏移 |
| 浏览器头 | `_build_headers()` | `Sec-Fetch-*`, `sec-ch-ua`, `Origin` 等 |
| SPA 模拟 | `welearn_password_login()` | 密码登录前先请求 `transfer.html` 和静态资源 |
| 心跳抖动 | `welearn_time_heartbeat()` | 55-65 秒随机间隔 |
