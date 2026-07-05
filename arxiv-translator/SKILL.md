---
name: arxiv-translator
description: 将 arXiv 论文自动翻译为中文 PDF。触发后按本 skill 顺序执行，勿长篇规划。用户提供论文标题或 arXiv ID、说「翻译论文」「我想读中文版」等时立即使用。支持多篇论文处理；首次使用若论文库路径未设置，需先询问保存目录。
---

# arXiv 论文中文翻译

**目标：** 将指定论文的 LaTeX 源码译为中文，并编译得到 PDF。

**流程：** 须严格按下文「第零步」至「第四步」顺序执行，不得擅自省略、合并或调换步骤。

**交互：** 仅在论文库路径为空、论文 ID 无法确定、检索结果存在多个需用户择一时才可向用户提问；其余情况一律无中断地执行得到最终翻译后的 PDF。

**翻译：** 翻译全部由当前对话模型自身完成，严禁使用外部翻译工具以及下载已有的翻译版本。

---

## 第零步：确定论文库目录

论文库绝对路径配置如下；若用户明确提供新的长期目录，应更新此值：

```text
PAPER_LIBRARY_DIR=""
```

若 `PAPER_LIBRARY_DIR` 为空，先询问用户论文库绝对路径，并说明该目录会存放每篇论文的独立文件夹、英文/中文 PDF、源码工作区 `.tmp_arxiv` 和 `download.env` 元数据。若用户不提供，则使用当前目录作为本次 `PAPER_LIBRARY_DIR`。

论文库采用单篇文献目录，arXiv ID 是唯一标识：

```text
<PAPER_LIBRARY_DIR>/
└── 2501.12948v2 - Paper Title/
    ├── 2501.12948v2 - Paper Title.en.pdf
    ├── 2501.12948v2 - Paper Title.zh.pdf
    ├── download.env
    ├── .tmp_arxiv/
    │   └── 2501.12948v2/
    │       ├── <arXiv source files>
    │       └── <translated .tex files>
```

脚本调用采用“单篇文献目录”方案：`download.py` 创建/复用以 `{PAPER_ID} - {Paper Title}` 命名的目录并写入 `download.env`；`compile.py paper "$PAPER_DIR"` 只编译该目录；`cleanup.py "$PAPER_DIR"` 只清理该目录。不得对论文库根目录执行清理。

每篇论文目录下必须同时保留英文原版 PDF 和中文翻译 PDF，二者与 `download.env` 同级。文件名以单篇文献目录名为基准：英文原版使用 `.en.pdf` 后缀，中文翻译版使用 `.zh.pdf` 后缀。

---

## 第一步：确定论文 ID

- arXiv URL/ID → 直接提取 ID
- 论文标题 → 搜索 arXiv / 网页查找 ID；找不到时给出候选让用户确认

---

## 第二步：获取源码并确定翻译范围

```bash
python3 {SKILL_DIR}/scripts/download.py --library-dir "$PAPER_LIBRARY_DIR" "{PAPER_ID}"
```

`download.py` 一步完成：提取标题 → 创建/复用单篇文献目录 → 下载源码 → 解压 → 递归查找 `.tex` → 定位主文件 → 写入 `download.env`。

无源码（仅 PDF）则告知用户跳过。

脚本向 stdout 输出变量，格式如下：
```
WORK_DIR=<源码目录绝对路径>
MAIN_TEX=<主文件相对路径>
PDF_NAME=<论文标题>
PAPER_DIR=<单篇文献目录绝对路径>
PDF_PATH=<编译输出 PDF 绝对路径>
```

若已有目录名以同一个 arXiv ID 开头，脚本会复用该目录，即使标题发生变化也以 arXiv ID 为准。
---

## 第三步：翻译

由当前**对话模型**直接在原 `.tex` 文件上进行翻译修改，按以下规则翻译：

- **术语库：** 翻译前必须阅读 `references/术语库.md`；命中术语按推荐译法处理，未命中术语按下列规则处理。
- **翻译范围：** 默认只翻正文，不翻附录，但附录中的内容需要得到保留，若同一文件中出现 `\appendix`，默认只翻该命令之前的内容。用户明确要求“翻译全文”时才翻附录。
- **必须翻译：** 正文叙述、摘要、图表标题、列表项、脚注中的描述文本，以及代码块中的注释。
- **保留不翻：** 数学环境、LaTeX 命令、`\cite{}`/`\ref{}`/`\label{}`、图片路径、URL、代码本体、`.bib`、人名、机构名、模型名、数据集名。
- **专有名词：** Transformer、Softmax、Token 等通用学术术语保留英文，不要生硬硬译。
- **标题要求：** `\title{}` 须改为自然中文题名，不保留英文原题或中英并列；最终中文 PDF 文件名必须为 `$PAPER_DIR/<单篇文献目录名>.zh.pdf`。
- **多篇处理：** 多篇论文可以分别处理；只有在用户**明确要求**并行委派时，才开启多个 subagent，否则直接顺序完成。

译后必须做自检：

```bash
python3 {SKILL_DIR}/scripts/inspect_tex.py scan "$WORK_DIR" "$MAIN_TEX" body
```

若用户明确要求“翻译全文”，则改为：

```bash
python3 {SKILL_DIR}/scripts/inspect_tex.py scan "$WORK_DIR" "$MAIN_TEX" full
```

脚本会输出 `SUSPECT_COUNT=<数字>` 以及若干 `SUSPECT=<文件>:<行号>:<片段>`。
- 只要 `SUSPECT_COUNT` 非 0，就必须逐条回到对应位置进行翻译；
- 只有 `SUSPECT_COUNT=0`，或剩余项明确属于“保留不翻”范围时，才可进入第四步。

---

## 第四步：编译与清理

编译：

```bash
python3 {SKILL_DIR}/scripts/compile.py paper "$PAPER_DIR"
```

`compile.py` 会统一完成以下编译前处理：
- 若检测到中文且主文件尚无 CJK 支持，自动在主文件 preamble 中补入 LuaLaTeX 所需中文支持；
- 自动注释掉与 Unicode 编译栈冲突的 `fontenc` / `inputenc`；
- 若源码自带 `.bbl`，自动将其内联到 `\bibliography{...}` 位置，避免远端单遍编译后引用显示为 `?`；
- 自动忽略常见编译中间文件与未被源码引用的游离 PDF，避免把无关产物上传到远端编译服务。

编译失败时：读取 stderr 中的错误日志，参考 `references/compile-errors.md` 修复源码，重新编译（最多重试 2 次）。

命名 PDF 前必须检查最终文件名和路径各级名称，不得包含 `\ / : * ? " < > |` 或表情符号；若标题含缩写前缀冒号，如 `RMA: Rapid Motor Adaptation`，改为 `【RMA】Rapid Motor Adaptation`。

编译产物若仍是 `download.env` 中的无后缀 `PDF_PATH`，编译成功后立即将其移动/重命名为 `$PAPER_DIR/<单篇文献目录名>.zh.pdf`。同时下载英文原版 PDF 到 `$PAPER_DIR/<单篇文献目录名>.en.pdf`；如果该英文 PDF 已存在，不要覆盖，除非用户明确要求刷新。

编译成功后默认保留 `$PAPER_DIR/.tmp_arxiv`，方便检查 PDF 后继续微调。确认 PDF 可用且不再需要源码时，调用：

```bash
python3 {SKILL_DIR}/scripts/cleanup.py "$PAPER_DIR"
```

多篇论文时，每篇都在自己的 `PAPER_DIR` 内下载、翻译、编译和清理；不得用论文库根目录代替 `PAPER_DIR`。

最后输出 PDF 保存路径。

---

## 参考文件
- `references/compile-errors.md`：编译常见错误及修复方法
- `references/术语库.md`：翻译术语推荐译法
