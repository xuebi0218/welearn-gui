# WeLearn-GUI
[![Release](https://img.shields.io/github/v/release/xuebi0218/welearn-gui)]()
[![License](https://img.shields.io/github/license/xuebi0218/welearn-gui)]()
[![Python](https://img.shields.io/badge/python-3.8+-blue)]()

> 一款面向高校 WE Learn 在线学习平台的可视化辅助学习工具，基于 CustomTkinter 图形界面实现课程学习自动化管理，全程本地运行，保障账号信息安全。

## 项目介绍

本项目基于 Python 开发，使用 CustomTkinter 构建可视化操作界面，封装了 WE Learn 平台接口，支持刷课（自动完成课程小节 + 解析题目 + 答题记录）和刷时长（心跳保活）两种模式，极大简化重复的人工操作流程。

核心设计特点：
- 纯本地运行，无第三方中转服务器，数据不对外泄露
- 图形化交互界面，零基础用户可直接上手使用
- 多线程并发处理，适配多门课程同步学习
- 学习进度实时与官网同步

## 核心功能

1. **账号登录模块**
   - 支持 Cookie 登录（推荐）和账号密码 SSO 登录
2. **课程信息加载**
   - 一键拉取个人所有已选线上课程
   - 区分已完成/未完成学习任务，直观展示进度
3. **刷课模式** — 自动完成课程小节，解析题目并生成答题记录
4. **刷时长模式** — 心跳保活刷学习时长
5. **国际化** — 界面支持中文 / English 切换，深色/浅色主题

## 环境依赖

- Python 3.8 及以上版本
- 兼容 Windows / macOS / Linux

### 依赖库

```txt
customtkinter>=5.2
requests>=2.26
Pillow>=9.0
```

## 使用方法

### 方式一：下载 exe（推荐）

从 [Releases](../../releases) 下载 `WelearnGUI.exe`，双击运行。

### 方式二：源码运行

```bash
pip install customtkinter requests Pillow
python src/welearn_gui.py
```

### 登录

1. 浏览器访问 [welearn.sflep.com](https://welearn.sflep.com/) 并登录
2. F12 → Network → 刷新页面 → 复制任意请求的 Cookie 值
3. 粘贴到软件 Cookie 输入框，点击登录

## 打包

```bash
pip install pyinstaller
pyinstaller WelearnGUI.spec --clean
```

## 免责声明

本软件完全免费，仅供学习交流使用。

- 严禁任何形式的倒卖、商用行为
- 如您通过付费渠道获得本软件，请立即退款并举报
- 请合理使用本工具，由此产生的一切后果由使用者自行承担

## 许可证

MIT License
