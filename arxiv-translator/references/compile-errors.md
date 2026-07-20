# 编译错误速查

## 常见错误与修复

**字体未找到** `Font "XXX" not found`
→ 请求的 CJK 字体在远程服务器上不存在。改用已确认可用的字体：`Noto Serif CJK SC`（已在 latex.ytotech.com 验证）。

**宏包冲突**（`fontenc` 或 `inputenc`）
→ 注释掉 `\usepackage[T1]{fontenc}` 和 `\usepackage[utf8]{inputenc}`——XeLaTeX / LuaLaTeX 的 Unicode 编译栈原生支持 UTF-8，通常不需要这两个包。

**宏重复定义** `LaTeX Error: Command \xxx already defined`
→ 常见于为中文支持引入 `luatexja` 后，与论文源码里的 `\newcommand\xxx...` 冲突。优先把源码中的该行从 `\newcommand` 改为 `\renewcommand`（保留论文作者期望的宏定义）。

**编译“成功”但引用/交叉引用仍是问号**（PDF 里出现 `??` 或 `[?]`）
→ 这通常意味着编译过程里发生了 LaTeX 错误，但在 `nonstopmode` 下仍生成了 PDF，导致 `latexmk` 没能完成多次编译而解析引用/交叉引用。
→ 解决思路：开启 `-halt-on-error`（让错误直接失败并返回日志）并修复首个报错后重试。
→ 若论文自带 `.bbl`，优先把 `.bbl` 内容内联到 `\bibliography{...}` 位置；不要再向 latex-on-http 发送 `options.bibliography`，该字段已被上游 API 移除。

**宏包缺失** `File 'xxx.sty' not found`
→ 该包未安装在远程服务器上。可在 `https://latex.ytotech.com/packages` 查询可用包列表。若缺失，尝试注释掉该包或替换为等价的可用包。

**中文溢出 / Overfull \hbox**
→ preamble 中已包含 `\setlength{\emergencystretch}{3em}`，通常足够。若仍溢出，添加 `\sloppy`。

**参考文献问题（bibtex/biber）**
→ 确认 `.bib` 文件已存在于工作目录并被正确引用；若论文自带 `.bbl`，优先内联 `.bbl`，让远端单遍编译也能解析引用。
→ 如果 `.bbl` 已被内联，可将 `options.compiler.bibliography` 设为 `false`，避免远端再次运行 BibTeX。

**PDF 文本提取出现 `�`**
→ 使用 pypdf 提取 CJK PDF 时出现 `�` 不一定是 PDF 缺字；FakeSlant 等字体特性可能影响 ToUnicode 回查。优先用 PyMuPDF 提取文本，或将页面渲染成 PNG 后目视检查。

**中文粗体/斜体缺字、叠字、错行或字重异常**
→ 根因通常是 `\textbf`、`\textit`、`\emph` 将中文切换到仅含拉丁字形的字体，或 CJK 字体未定义粗体/斜体变体。为 `xeCJK`/`luatexja-fontspec` 明确配置同一 CJK 字体族的 Bold、Italic、BoldItalic；没有真实斜体时使用适度 FakeSlant。
→ 对照英文稿的强调位置，渲染相关页检查栏宽、换行、基线和字重。必须回到 LaTeX 源码修复并重编译；禁止用 PDF 覆盖文字，因为覆盖层会破坏分栏行宽、行距和字体一致性。

**远端编译超时 / 变慢**
→ 检查工作目录里是否混入了历史产物（尤其是无关的 PDF、`.aux`、`.log`、旧输出文件）。这些文件会被一并上传，显著拖慢远端编译，甚至导致超时。

**远端编译连续失败或触发限制**
→ 远端编译最多尝试 2 次。若 2 次后仍失败，且本机有 Codex LaTeX 插件或 TeX Live/MacTeX，应切到本地编译，不要继续反复打远端服务。
→ 本地也不可用时（既没有 LaTeX 插件，也没有 TeX Live/MacTeX），停止编译并告知用户缺少本地编译环境。
→ 本地 LuaLaTeX 若提示 `Font "Noto Serif CJK SC" cannot be found`，优先改用本机可见字体的文件路径，例如 macOS 上的 `\setmainjfont[Path=/System/Library/Fonts/]{Hiragino Sans GB.ttc}`，并设置 `TEXMFVAR` / `TEXMFCACHE` 到可写临时目录。

**云盘目录本地编译生成 PDF 但 latexmk 返回非零**
→ 在 iCloud/CloudDrive 等同步目录中，`latexmk` 可能因旧 `.log` 时间戳、图片 md5 读取、`.fls`/`.fdb_latexmk` 写入异常返回非零，同时日志已经出现 `Output written on ...pdf`。
→ 不要直接交付这种 PDF。先将当前源码、样式文件、`.bbl`/`.bib` 和被引用图片复制到 `/private/tmp` 等本地临时目录，排除历史 PDF、`.aux`、`.log`、`.out`、`.fls`、`.fdb_latexmk`、`.synctex.gz` 和时间戳备份，再在临时目录重新编译。
→ 临时目录编译成功后，用 `pdfinfo` 检查页数和结构，并渲染首页确认中文字体、图片和版面正常，最后再把干净 PDF 复制回论文库的 `.zh.pdf` 路径。

## 读取错误日志

编译失败时，服务端返回含完整日志的 JSON。找到以 `!` 开头的行定位致命错误：

```
! LaTeX Error: ...
! Undefined control sequence ...
! Missing $ inserted ...
```

优先修复第一个错误——后续错误通常是连锁反应。
