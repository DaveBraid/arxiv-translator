---
name: arxiv-translator
description: 将 arXiv 论文自动翻译为中文 PDF。触发后按本 skill 顺序执行，勿长篇规划。用户提供论文标题或 arXiv ID、说「翻译论文」「我想读中文版」等时立即使用。支持多篇论文处理；首次使用若论文库路径未设置，需先询问保存目录。
---

# arXiv 论文中文翻译

**目标：** 将指定论文的 LaTeX 源码译为中文，并编译得到 PDF。

**流程：** 须严格按下文「第零步」至「第四步」顺序执行，不得擅自省略、合并或调换步骤。

**交互：** 仅在论文库路径为空、论文 ID 无法确定、检索结果存在多个需用户择一，以及成品交付后确认是否清理源码时向用户提问；其余情况无中断地执行到 PDF 交付。

**翻译：** 翻译全部由当前对话模型自身完成，严禁使用外部翻译工具以及下载已有的翻译版本。

**文件纪律：** 非必要不得新增任何一次性脚本、辅助程序或临时项目文件；不得把单次任务的临时代码写入仓库、skill 目录或论文目录。优先使用本 skill 已有脚本和直接编辑完成任务；只有逻辑会长期复用且用户明确同意时，才可新增或修改 `scripts/` 中的脚本。

---

## 第零步：确定论文库目录

论文库绝对路径配置如下；若用户明确提供新的长期目录，应更新此值：

```text
PAPER_LIBRARY_DIR=""
```

若 `PAPER_LIBRARY_DIR` 为空，必须先询问用户论文库绝对路径，并说明该目录会存放每篇论文的独立文件夹和中英文 PDF；翻译期间还会保存 `download.env` 与临时源码。用户答复后，将所选绝对路径写回本机已安装的 skill 文件中的 `PAPER_LIBRARY_DIR="..."`；仓库副本仍保持空值。仅当用户明确拒绝提供长期目录时，才可把当前目录用于本次任务，且不得写回配置。

论文库采用单篇文献目录，arXiv ID 是唯一标识：

```text
<PAPER_LIBRARY_DIR>/
└── 2501.12948v2 - Paper Title/
    ├── 2501.12948v2 - Paper Title.en.pdf
    ├── 2501.12948v2 - Paper Title.zh.pdf
    └── download.env                 # 仅在翻译与复核期间存在
```

同步盘（包括 CloudDrive、iCloud）不得承载活跃源码：同步过程可能恢复旧文件，使后续编译读取过期译文。源码须放在脚本创建的系统临时目录中，编译成功后再把 PDF 一次性写回论文目录。清理完成后，论文目录只保留 `.en.pdf` 和 `.zh.pdf`。

脚本调用采用“单篇文献目录”方案：`download.py` 创建/复用以 `{PAPER_ID} - {Paper Title}` 命名的目录并写入 `download.env`；`compile.py paper "$PAPER_DIR"` 只编译该目录；`cleanup.py "$PAPER_DIR"` 只清理该目录。不得对论文库根目录执行清理。

每篇论文目录下必须同时保留英文原版 PDF 和中文翻译 PDF；翻译期间 `download.env` 与二者同级。文件名以单篇文献目录名为基准：英文原版使用 `.en.pdf` 后缀，中文翻译版使用 `.zh.pdf` 后缀。

---

## 第一步：确定论文 ID

- arXiv URL/ID → 直接提取 ID
- 论文标题 → 搜索 arXiv / 网页查找 ID；找不到时给出候选让用户确认

---

## 第二步：获取源码并确定翻译范围

同步盘论文库使用本地临时源码：

```bash
python3 {SKILL_DIR}/scripts/download.py --library-dir "$PAPER_LIBRARY_DIR" --local-work-copy "{PAPER_ID}"
```

普通本地磁盘可省略 `--local-work-copy`，继续把源码放在单篇目录的 `.tmp_arxiv` 中。

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

- **禁止额外脚本：** 翻译正文时不得为了批量替换或写入译文而创建新的脚本文件；确需一次性辅助处理时，只可使用不落地的命令行片段或编辑器能力，并在执行前确认不会留下额外文件。
- **术语库：** 翻译前必须阅读 `references/术语库.md`；命中术语按推荐译法处理，未命中术语按下列规则处理。
- **翻译范围：** 默认只翻正文，不翻附录，但附录中的内容需要得到保留，若同一文件中出现 `\appendix`，默认只翻该命令之前的内容。用户明确要求“翻译全文”时才翻附录。
- **必须翻译：** 正文叙述、摘要、图表标题、列表项、脚注中的描述文本，以及代码块中的注释。
- **保留不翻：** 数学环境、LaTeX 命令、`\cite{}`/`\ref{}`/`\label{}`、图片路径、URL、代码本体、`.bib`、人名、机构名、模型名、数据集名。
- **专有名词：** Transformer、Softmax、Token 等通用学术术语保留英文，不要生硬硬译。
- **标题要求：** `\title{}` 须改为自然中文题名，不保留英文原题或中英并列；最终中文 PDF 文件名必须为 `$PAPER_DIR/<单篇文献目录名>.zh.pdf`。
- **中文强调：** 英文粗体、斜体或粗斜体对应的中文须使用具备 CJK 字形的同一字体族；不得让中文切换到仅含拉丁字形的字体。需要粗斜体时配置 CJK 粗体与仿斜体后在源码中实现，不得用 PDF 覆盖层补字。
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

`paper` 只在源码工作区生成候选 PDF，并输出 `STAGED_PDF` 与 `FINAL_PDF`，不得在视觉检查前自行复制到论文库。

编译失败时：读取 stderr 中的错误日志，参考 `references/compile-errors.md` 修复源码，重新编译（最多重试 2 次）。

编译后必须渲染并逐页检查，重点核对中文粗体/斜体、双栏换行、行距、图表和公式。文本提取无乱码不能替代视觉检查；发现缺字、叠字、错行或异常字重时，须修复 CJK 字体映射并从 LaTeX 源码重新编译，禁止直接修改 PDF。

候选 PDF 检查通过后再原子发布到论文库：

```bash
python3 {SKILL_DIR}/scripts/compile.py publish "$PAPER_DIR"
```

命名 PDF 前必须检查最终文件名和路径各级名称，不得包含 `\ / : * ? " < > |` 或表情符号；若标题含缩写前缀冒号，如 `RMA: Rapid Motor Adaptation`，改为 `【RMA】Rapid Motor Adaptation`。

`publish` 将候选 PDF 一次性替换为 `$PAPER_DIR/<单篇文献目录名>.zh.pdf`。同时下载英文原版 PDF 到 `$PAPER_DIR/<单篇文献目录名>.en.pdf`；如果该英文 PDF 已存在，不要覆盖，除非用户明确要求刷新。

交付中英文 PDF 后询问用户是否确认成品无误。用户确认后调用下列命令；脚本会删除该论文的 `.tmp_arxiv`、受管本地临时源码、检查输出和 `download.env`，最终只保留中英文 PDF：

```bash
python3 {SKILL_DIR}/scripts/cleanup.py "$PAPER_DIR"
```

多篇论文时，每篇都在自己的 `PAPER_DIR` 内下载、翻译、编译和清理；不得用论文库根目录代替 `PAPER_DIR`。

最后输出 PDF 保存路径。

---

## 参考文件
- `references/compile-errors.md`：编译常见错误及修复方法
- `references/术语库.md`：翻译术语推荐译法
