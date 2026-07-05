# Repository Guidelines

## 项目结构与模块组织

本仓库是一个 Codex/Agent Skill 项目，核心内容位于 `arxiv-translator/`。

- `arxiv-translator/SKILL.md`：Skill 主入口，定义论文下载、翻译、自检、编译流程。
- `arxiv-translator/scripts/`：Python 工具脚本，包括 `download.py`、`inspect_tex.py`、`compile.py`、`cleanup.py`。
- `arxiv-translator/references/`：排障参考文档，例如编译错误处理。
- `tests/`：离线单元测试，覆盖脚本的路径管理和元数据行为。
- `images/`：README 中使用的安装与效果截图。
- `README.md`：面向用户的安装、使用说明和项目介绍。

## 构建、测试与开发命令

本项目没有传统构建步骤；开发重点是验证脚本和 Skill 流程。

```bash
python3 -c 'import ast, pathlib; [ast.parse(p.read_text(encoding="utf-8"), filename=str(p)) for p in pathlib.Path("arxiv-translator/scripts").glob("*.py")]'
```

检查所有 Python 脚本是否存在语法错误，且不会改动已跟踪的 `__pycache__`。

```bash
python3 -m unittest tests/test_paper_library_paths.py
```

运行离线单元测试，验证论文库目录、`download.env` 和按单篇目录编译参数。

```bash
python3 arxiv-translator/scripts/download.py 1706.03762 /tmp/arxiv-test
```

下载并解压指定 arXiv 源码，用于验证下载与主文件识别逻辑。

```bash
python3 arxiv-translator/scripts/inspect_tex.py scan /tmp/arxiv-test main.tex body
```

扫描正文中可能未翻译的英文片段；请将 `main.tex` 替换为 `download.py` 输出的 `MAIN_TEX`。

## 代码风格与命名约定

Python 脚本使用 4 空格缩进，函数和变量采用 `snake_case`，常量采用全大写加下划线，如 `BEGIN_DOC_RE`。优先使用标准库；新增第三方依赖前需说明用途，并同步更新 README 的依赖说明。脚本应保留清晰的 CLI 用法、确定性的 stdout/stderr 输出，以及对失败场景的明确 `sys.exit`。

遵循最小改动原则：只修改完成任务必需的内容；Skill 必须要点明确、逻辑清晰，不写废话，不长篇大论。

## 测试指南

当前使用 Python `unittest`，暂无覆盖率门槛。修改脚本后至少运行 AST 语法检查和 `python3 -m unittest tests/test_paper_library_paths.py`，并在涉及下载、编译或 LaTeX 处理时用一个小型 arXiv ID 做 smoke test。涉及引用内联、中文字体注入时，应验证真实源码目录，而不只检查单个字符串。

## 提交与 Pull Request 指南

现有提交信息较短，例如 `update`、`skill`。后续建议使用简洁祈使句，说明实际改动，例如 `Improve compile error handling` 或 `更新翻译自检规则`。PR 应包含：改动目的、影响的脚本或文档、已运行的验证命令、相关 issue 链接；若修改 README 展示内容，请附截图或说明图片路径。

## 安全与配置提示

不要提交 `.tmp_arxiv/`、论文源码临时目录、生成的 PDF 或个人 API/服务配置。`compile.py` 会调用远端 LaTeX 编译服务；修改上传文件筛选逻辑时，请确保不会包含无关本地文件或敏感内容。

## Agent 同步规则

后续修改 Skill 时，优先在本仓库内编辑 `arxiv-translator/`。完成验证后，先提交 git （提交信息用中文撰写）并推送到远端仓库，再同步到本机已安装的 skills 目录（例如 `$CODEX_HOME/skills/arxiv-translator` 或对应绝对路径）。不要直接把 skills 目录作为唯一修改来源。
