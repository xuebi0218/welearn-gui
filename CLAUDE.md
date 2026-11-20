# CLAUDE.md

## 项目身份

Welearn 刷课工具 GUI v3.6 — CustomTkinter 桌面应用。
- **主文件**: `src/welearn_gui.py`（唯一需要修改的文件）
- **风险分析**: `docs/RISK_ANALYSIS.md`（打回原因 + 对策，必读）
- **变更日志**: `docs/CHANGELOG_v3.6.md`
- **GitHub**: https://github.com/xuebi0218/welearn-gui
- **Python**: 3.13.9, **PyInstaller**: 6.20.0
- **修复报告**: `docs/v3.2_FIX_REPORT.md`, `docs/v3.3_FIX_REPORT.md`, `docs/v3.4_FIX_REPORT.md`
- **v3.2 备份**: `src/welearn_gui_v3.2_backup_20260616_220245.py`
- **v3.3 备份**: `src/welearn_gui_v3.3_backup_20260617_*.py`
- **v3.1 备份**: `src/welearn_gui_v3.1_backup.py`

## 构建 & 运行

```bash
# 直接运行（开发调试）
python src/welearn_gui.py

# 打包 exe
rm -f dist/WelearnGUI.exe
pyinstaller --clean --onefile --windowed \
  --name WelearnGUI \
  --add-data "src/donate_qr.jpg;src/" \
  --add-data "src/help_1.jpg;src/" \
  --add-data "src/help_2.jpg;src/" \
  --add-data "src/help_3.jpg;src/" \
  --add-data "src/mascot.png;src/" \
  --collect-data customtkinter \
  --hidden-import queue \
  --hidden-import PIL \
  --hidden-import PIL.Image \
  --hidden-import brotli \
  src/welearn_gui.py
# 输出: dist/WelearnGUI.exe (~37MB)
```

打包前务必 `taskkill /f /im WelearnGUI.exe` 避免文件锁定。

## 代码架构（`src/welearn_gui.py`）

### 行号速查表（自动生成，v3.6）

主文件共 **2402** 行。索引由 `tools/gen_index.py` 从 AST 生成，改代码后重新生成。

| 行号 | 名称 | 类型 |
|------|------|------|
| 33 | `_rand_delay` | 函数 |
| 52 | `_random_ua` | 函数 |
| 57 | `_rand_delay` | 函数 |
| 64 | `_build_headers` | 函数 |
| 102 | `_text` | 函数 |
| 135 | `parse_cookie_string` | 函数 |
| 171 | `welearn_validate_session` | 函数 |
| 199 | `welearn_password_login` | 函数 |
| 298 | `_verify_login` | 函数 |
| 313 | `welearn_get_course_info` | 函数 |
| 330 | `welearn_get_units` | 函数 |
| 346 | `welearn_get_lessons` | 函数 |
| 376 | `_last_json` | 函数 |
| 391 | `_as_bool` | 函数 |
| 400 | `_clamp` | 函数 |
| 404 | `_parse_hms` | 函数 |
| 412 | `welearn_sco_requirements` | 函数 |
| 435 | `welearn_verify_learntime` | 函数 |
| 457 | `welearn_curriculum_submit` | 函数 |
| 606 | `welearn_time_init` | 函数 |
| 642 | `welearn_check_gates` | 函数 |
| 679 | `welearn_heartbeat_full` | 函数 |
| 705 | `welearn_time_heartbeat` | 函数 |
| 712 | `welearn_time_finalize` | 函数 |
| 728 | `_js_escape` | 函数 |
| 743 | `welearn_get_sco_addr` | 函数 |
| 774 | `_fetch_sco_template` | 函数 |
| 787 | `parse_sco_questions` | 函数 |
| 814 | `generate_interactions` | 函数 |
| 863 | `thread_login` | 函数 |
| 880 | `thread_refresh_courses` | 函数 |
| 897 | `thread_fetch_units` | 函数 |
| 909 | `_collect_lessons` | 函数 |
| 939 | `thread_curriculum_execute` | 函数 |
| 951 | `_curriculum_worker` | 函数 |
| 1076 | `thread_time_execute` | 函数 |
| 1087 | `_time_worker` | 函数 |
| 1137 | `_time_one` | 函数 |
| 1202 | `_load_config` | 函数 |
| 1212 | `_save_config` | 函数 |
| 1224 | `WelearnApp` | 类 |
| 1225 | `.__init__` | 方法 |
| 1292 | `._save_prefs` | 方法 |
| 1307 | `._build_sidebar` | 方法 |
| 1394 | `._build_content` | 方法 |
| 1404 | `._show_page` | 方法 |
| 1418 | `._build_home_page` | 方法 |
| 1681 | `._on_preset_change` | 方法 |
| 1713 | `._update_estimate` | 方法 |
| 1730 | `._on_task_mode_change` | 方法 |
| 1739 | `._build_donate_page` | 方法 |
| 1789 | `._build_help_page` | 方法 |
| 1879 | `._build_settings_page` | 方法 |
| 1923 | `._build_statusbar` | 方法 |
| 1940 | `._setup_log_tags` | 方法 |
| 1948 | `._log` | 方法 |
| 1966 | `._clear_log` | 方法 |
| 1971 | `._export_log` | 方法 |
| 1992 | `._set_running` | 方法 |
| 2007 | `._on_login_mode_change` | 方法 |
| 2017 | `._on_login` | 方法 |
| 2036 | `._on_course_selected` | 方法 |
| 2048 | `._on_unit_selected` | 方法 |
| 2058 | `._on_rate_mode_change` | 方法 |
| 2068 | `._on_time_mode_change` | 方法 |
| 2078 | `._on_refresh` | 方法 |
| 2082 | `._on_start_task` | 方法 |
| 2201 | `._on_close` | 方法 |
| 2208 | `._on_stop` | 方法 |
| 2216 | `._on_lang_change` | 方法 |
| 2224 | `._on_theme_change` | 方法 |
| 2230 | `._on_open_github` | 方法 |
| 2234 | `._on_check_update` | 方法 |
| 2248 | `._refresh_labels` | 方法 |
| 2258 | `._show_disclaimer` | 方法 |
| 2299 | `._poll_queue` | 方法 |
| 2316 | `._handle_message` | 方法 |
| 2379 | `._populate_course_menu` | 方法 |
| 2386 | `._populate_unit_menu` | 方法 |
| 2395 | `.run` | 方法 |


## 关键 API 知识点

### SSO 登录 (IdentityServer4 + OIDC + PKCE)
- **登录页**: `https://sso.sflep.com/idsvr/Account/Login?ReturnUrl=...`
- POST 参数名: **`Account`** 和 **`pwd`**（不是 Username/Password!）
- 这是通过 reverse engineering 400 错误响应发现的
- 参考: `src/diagnose_sso3.py`, `src/sso_debug3.txt`
- 密码登录比 Cookie 登录更易被检测（绕过浏览器 SPA 指纹）

### Welearn API 端点
- 课程列表: `welearn.sflep.com/ajax/authCourse.aspx?action=gmc`
- 课程信息: `.../ajax/authCourse.aspx?action=getcurriculum&ocid=...&uid=...&classid=...`
- 单元列表: `.../ajax/authCourse.aspx?action=getunit&cid=...&uid=...`
- 课时列表: `.../ajax/authCourse.aspx?action=getlesson&cid=...&uid=...&unit=...&classid=...`
- 提交答案: `.../curriculum/student/curriculum/restfull/RESTful.aspx?action=submit`
- 时长初始化: `.../restfull/RESTful.aspx?action=cmi`
- 时长心跳: `.../restfull/RESTful.aspx?action=cmifile&b=...&d=...`
- 时长结束: `.../restfull/RESTful.aspx?action=cmifile&b=6&d=...`

## 反检测措施

1. **UA 轮换**: 18 个浏览器 UA，每次请求随机选取
2. **延迟抖动**: 基础延迟 + 请求计数指数退避 + 随机毫秒偏移
3. **浏览器请求头**: `Sec-Fetch-Site/Dest/Mode/User`, `sec-ch-ua`, `Origin`, `Referer`
4. **SPA 资源模拟**: 密码登录前先 GET transfer.html 和静态资源
5. **心跳随机化**: 刷时长心跳间隔 55-65 秒随机

## GUI 页面结构

```
┌─ sidebar (170px) ───┬─ content_area ──────────────────────┐
│  Welearn Tool        │  [home] [donate] [help] [settings]  │
│  [主页]              │                                      │
│  [赞助]              │  四种页面通过 pack_forget/pack 切换 │
│  [帮助]              │                                      │
│  [设置]              │                                      │
│  v3.1                │                                      │
├──────────────────────┴─────────────────────────────────────┤
│  ● 就绪                                        [停止]      │
└─ status_bar ───────────────────────────────────────────────┘
```

## 常见修改指引

| 需求 | 改哪里 |
|------|--------|
| 添加/修改 UA | `_USER_AGENTS` 列表（第25-50行） |
| 调整延迟参数 | `_rand_delay()` 函数（约第65行） |
| 修改 i18n 文本 | `T` 字典（第617-746行） |
| 调整 GUI 布局 | `_build_home_page()` 等方法（第853行起） |
| 修改刷课逻辑 | `thread_curriculum_execute()`（第595行） |
| 修改刷时长逻辑 | `thread_time_execute()`（约第605行） |
| 添加新页面 | `_build_xxx_page()` + 加入 `_build_content()` 和 `nav_items` |
| 修改 API 调用 | 对应 API 函数（第102-480行） |
| 调整打包参数 | `build_welearn_gui.bat`（需更新 --add-data） |
| 更换赞赏码 | 替换 `src/donate_qr.jpg` |
| 更新教程截图 | 替换 `src/help_1/2/3.jpg` |
| 更新版本号 | `__init__` 中 title + `_build_sidebar` 中版本标签 + `_build_settings_page` |

## 注意事项

- 只修改 `src/welearn_gui.py`，其他 Python 文件均为遗留或诊断脚本
- 修改后**必须重新打包 exe**，否则用户看不到变更
- exe 打包时图片通过 `--add-data` 嵌入，运行时路径用 `sys._MEIPASS`
- 开发调试时图片路径为 `os.path.dirname(os.path.abspath(__file__))`
- 打包前确保 exe 未被占用（`taskkill /f /im WelearnGUI.exe`）
- CTk 组件操作非线程安全，所有 UI 更新必须通过消息队列
- `_set_running(True)` 会禁用除停止按钮外的所有操作控件
