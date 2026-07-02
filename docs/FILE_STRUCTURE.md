# WelearnCurriculumFinsh 项目文件结构说明

## 项目概述

**项目名称**: WelearnCurriculumFinsh
**项目类型**: Python桌面应用程序（使用PyInstaller打包）
**功能描述**: Welearn网络课程自动完成工具，支持账号密码和Cookie登录，可自动完成课程学习并设置练习正确率。

---

## 文件目录结构

```
welearn-curriculum-finsh-master/
├── WelearnCurriculumFinsh.exe    # 可执行文件（主程序）
├── README.md                     # 项目说明文档
├── LICENSE                       # 开源许可证
├── .gitignore                    # Git版本控制忽略文件配置
├── .workflow/                    # CI/CD工作流配置目录
│   ├── BranchPipeline.yml
│   ├── MasterPipeline.yml
│   └── PRPipeline.yml
├── build/                        # PyInstaller构建产物目录
│   └── WelearnCurriculumFinsh/
│       ├── localpycs/           # Python字节码缓存目录
│       │   ├── pyimod01_archive.pyc
│       │   ├── pyimod02_importers.pyc
│       │   ├── pyimod03_ctypes.pyc
│       │   ├── pyimod04_pywin32.pyc
│       │   └── struct.pyc
│       ├── Analysis-00.toc      # PyInstaller分析结果文件
│       ├── EXE-00.toc            # 可执行文件构建记录
│       ├── PKG-00.toc            # 安装包构建记录
│       ├── PYZ-00.pyz            # Python标准库压缩包
│       ├── PYZ-00.toc            # PYZ包构建记录
│       ├── WelearnCurriculumFinsh.pkg    # PyInstaller生成的pkg文件
│       ├── base_library.zip      # Python基础库打包文件
│       ├── warn-WelearnCurriculumFinsh.txt   # 警告信息日志
│       └── xref-WelearnCurriculumFinsh.html  # 交叉引用HTML报告
└── src/                          # 源代码目录
    ├── WelearnCurriculumFinsh.py     # 主程序源代码
    └── WelearnCurriculumFinsh.spec   # PyInstaller打包配置文件
```

---

## 文件详细说明

### 根目录文件

#### WelearnCurriculumFinsh.exe
- **文件类型**: Windows可执行文件 (EXE)
- **文件路径**: `WelearnCurriculumFinsh.exe`
- **功能用途**: 项目的主程序入口，已使用PyInstaller打包为独立可执行文件
- **重要性**: ⭐⭐⭐⭐⭐ (核心文件)
- **说明**: 包含完整的Python解释器和所有依赖项，可直接在Windows系统中运行，无需安装Python环境

#### README.md
- **文件类型**: Markdown文档
- **功能用途**: 项目的说明文档，包含项目简介、使用方法、更新日志等信息
- **重要性**: ⭐⭐⭐⭐ (重要文档)
- **说明**: 用户应该首先阅读此文件了解项目基本信息和用法

#### LICENSE
- **文件类型**: 文本文件
- **功能用途**: 项目的开源许可证文件
- **重要性**: ⭐⭐⭐ (常规文件)
- **说明**: 声明项目的开源许可类型和使用条款

#### .gitignore
- **文件类型**: Git配置文件
- **功能用途**: 指定Git版本控制系统需要忽略的文件和目录
- **重要性**: ⭐⭐⭐ (配置文件)
- **说明**: 确保敏感信息和构建产物不会被提交到版本库

---

### .workflow 目录（CI/CD配置）

#### BranchPipeline.yml
- **文件类型**: YAML配置文件
- **功能用途**: GitHub Actions工作流配置，用于分支推送时的自动化任务
- **重要性**: ⭐⭐⭐ (自动化配置)

#### MasterPipeline.yml
- **文件类型**: YAML配置文件
- **功能用途**: GitHub Actions工作流配置，用于主分支的自动化构建和部署
- **重要性**: ⭐⭐⭐ (自动化配置)

#### PRPipeline.yml
- **文件类型**: YAML配置文件
- **功能用途**: GitHub Actions工作流配置，用于Pull Request的自动化测试
- **重要性**: ⭐⭐⭐ (自动化配置)

---

### build 目录（构建产物）

#### WelearnCurriculumFinsh.pkg
- **文件类型**: PyInstaller打包文件
- **功能用途**: PyInstaller生成的中间包文件，包含程序的所有组件
- **重要性**: ⭐⭐ (构建产物)
- **说明**: 这是生成最终exe的中间文件，一般用户不需要关注

#### base_library.zip
- **文件类型**: ZIP压缩包
- **功能用途**: Python标准库和第三方库的打包文件
- **重要性**: ⭐⭐ (构建产物)
- **说明**: PyInstaller将Python库依赖打包成此文件

#### warn-WelearnCurriculumFinsh.txt
- **文件类型**: 文本日志文件
- **功能用途**: PyInstaller构建过程中的警告信息记录
- **重要性**: ⭐ (调试文件)
- **说明**: 构建时如果有任何警告会记录在此文件中，用于排查问题

#### xref-WelearnCurriculumFinsh.html
- **文件类型**: HTML文件
- **功能用途**: Python模块交叉引用报告
- **重要性**: ⭐ (调试文件)
- **说明**: 显示模块之间的依赖关系，用于分析程序结构

#### localpycs/ 目录
- **文件类型**: Python字节码文件目录
- **功能用途**: PyInstaller打包过程中生成的Python字节码缓存文件
- **重要性**: ⭐ (构建产物)
- **说明**: 这些是Python模块的预编译字节码，用于加速程序启动

#### *.toc 文件
- **文件类型**: PyInstaller TOC格式文件
- **功能用途**: PyInstaller的构建记录文件，保存了打包过程中的元数据
- **重要性**: ⭐ (构建记录)
- **说明**: Analysis-00.toc、EXE-00.toc、PKG-00.toc等记录了各个阶段的构建信息

---

### src 目录（源代码）

#### WelearnCurriculumFinsh.py
- **文件类型**: Python源代码文件
- **功能用途**: 项目的主程序源代码，实现课程自动完成的全部逻辑
- **重要性**: ⭐⭐⭐⭐⭐ (核心源代码)
- **主要功能模块**:
  - 登录模块（支持账号密码和Cookie两种登录方式）
  - 课程查询模块（获取用户课程列表）
  - 单元选择模块（允许用户选择要完成的课程单元）
  - 刷课执行模块（自动完成课程学习）
  - 正确率设置模块（支持固定和随机正确率）
  - 结果统计模块（报告成功/失败统计）
- **依赖库**: requests（网络请求）

#### WelearnCurriculumFinsh.spec
- **文件类型**: PyInstaller配置文件
- **功能用途**: PyInstaller打包工具的配置文件，定义了如何将Python脚本打包成exe
- **重要性**: ⭐⭐⭐⭐ (打包配置)
- **说明**: 包含Analysis、PYZ、EXE三个主要部分的配置，决定了打包的行为和最终exe的特性

---

## 文件重要性等级说明

| 等级 | 符号 | 说明 |
|------|------|------|
| 核心文件 | ⭐⭐⭐⭐⭐ | 缺少则程序无法运行 |
| 重要文件 | ⭐⭐⭐⭐ | 对程序功能有重要影响 |
| 常规文件 | ⭐⭐⭐ | 程序运行非必需但有作用 |
| 配置/构建 | ⭐⭐ | 用于开发/构建过程 |
| 调试文件 | ⭐ | 仅用于问题排查 |

---

## 运行环境要求

- **操作系统**: Windows 10/11 或更高版本
- **运行环境**: 无需安装Python（已打包成独立exe）
- **网络要求**: 需要互联网连接以访问Welearn平台

---

## 构建信息

- **打包工具**: PyInstaller 6.20.0
- **Python版本**: Python 3.13.9
- **构建平台**: Windows-64bit
- **构建日期**: 2026-05-17
