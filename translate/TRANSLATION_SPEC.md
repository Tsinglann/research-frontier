# 学术论文翻译规范（中文 LaTeX）

将英文论文 PDF 翻译成中文 LaTeX 项目并编译通过。本规范适用于本项目所有翻译工作。

## 项目命名（重要）
- 翻译项目目录名必须以日期前缀开头，格式 `YYYYMMDD_项目名`，例如 `20260915_wigner_unreasonable_effectiveness`。
- 项目名用简短的英文标识（作者/主题/arXiv 编号均可）。

## 目录结构
```
<项目目录>/
  main.tex           # 主文件
  sections/*.tex     # 各章节（按需拆分）
  main.pdf           # 编译产物（自动生成）
  source.txt         # 原文全文（已存在，勿删）
```

## 格式范例（务必先读取学习）
- `/Users/user/Documents/<workdir>/20260915_wigner_unreasonable_effectiveness/`（main.tex + sections/*.tex）
- `/Users/user/Documents/<workdir>/dicks_2024_energylandscapes/`（main.tex + sections/*.tex）

## 基本要求
1. 文档类：`\documentclass[11pt]{article}`；中文支持 `\usepackage[UTF8]{ctex}`；数学 `amsmath,amssymb,bm`；表格 `booktabs`；图片 `graphicx`；引用 `natbib`（如需）；摘要框可用 `mdframed,xcolor`。
2. 标题块：中文标题（\LARGE\bfseries）+ 英文原标题（斜体，其下或括号内）+ 作者英文原名 + 机构/期刊/DOI 等信息（可保留英文或翻译，格式仿范例）。
3. 摘要：翻译成中文。
4. 章节标题：`\section{中文标题（English Title）}`，子节 `\subsection{中文（English）}`。
5. 正文中文；公式、符号用 LaTeX 数学模式，符号保持原样不译。
6. 术语：首次出现写「中文（English 缩写）」，之后可只用中文或缩写。

## 图片处理（重要）

**优先精准截取原图并嵌入**（矢量保真）。工具：`_tools/pdfgrab`，完整说明见 `_tools/PDFGRAB.md`。

```bash
# 1 探测全篇 + 生成红框标注图
_tools/pdfgrab detect 项目/source.pdf --overlay 项目/_qa

# 2 【必做】逐张 read_image 看 项目/_qa/ovl-pNNN.png，确认红框贴合图边界
#    注意：只有输出带 [overlay-ok] 才代表框真的画上了（曾因静默失败产生过误判）

# 3 批量裁切（矢量 PDF 优先）
_tools/pdfgrab auto 项目/source.pdf --out 项目/figures --formats pdf
```

```latex
\begin{figure}[htbp]
\centering
\includegraphics[width=0.95\linewidth]{figures/fig_fig_1.pdf}
\caption{翻译后的图注}
\label{fig:xxx}
\end{figure}
```

- 框不准时手动指定：`_tools/pdfgrab crop 项目/source.pdf --page N --bbox "x0,y0,x1,y1" --out ...`
  （点坐标 = 渲染像素 ÷ dpi × 72）。改坐标后**重新出 overlay 复核**。
- `pdfimages` 单独提图**不可用**：RevTeX/AIP 的图是「矢量坐标轴 + 位图子图」混合，
  直接提会得到没有坐标轴和面板标签的碎片。
- **扫描件**（整页位图的老论文，如 Metropolis 1953）与**无图注的图**自动探测不可靠
  → 手动 crop，或退回下面的占位框：

```latex
\begin{figure}[htbp]
\centering
\fbox{\begin{minipage}{0.7\textwidth}\centering 图 N 占位（原图未包含）\end{minipage}}
\caption{翻译后的图注}
\label{fig:xxx}
\end{figure}
```

- 图注 caption **一律翻译成中文**；正文引用 `图~\ref{fig:xxx}`。
- 图编号与原文一致（Fig. 1 → 图 1，依此类推）。
- 图**内部**的英文（坐标轴刻度、面板标签、图内公式）**不翻译**，按原样保留。

## 表格
- 内容翻译成中文，用 booktabs（\toprule/\midrule/\bottomrule），caption 翻译成中文。

## 公式
- 完整保留原文所有公式，用 LaTeX 数学模式重建；编号保留；上下标、矩阵、求和、积分等不可出错。

## 参考文献
- **保留英文原文，不翻译**。
- 用 `thebibliography` 环境（或 natbib + \cite{}），编号顺序与原文 [1][2]... 一致。
- 正文引用用 `\cite{...}`（上标式）或对应编号。

## 编译验证（必须）
```bash
cd <项目目录> && latexmk -xelatex -interaction=nonstopmode -halt-on-error main.tex
```
- 必须 exit 0、生成 main.pdf。
- 检查 log：无 LaTeX Error、无 "Missing character"（缺字）。
- 页数与原文尽量接近。

## 质量要求
- 忠实原文，术语准确，不增删内容；译文通顺、符合中文科技写作习惯。
- 完成后报告：翻译了多少章、编译页数、遗留问题（如原文提取缺失、公式存疑等）。

## 译稿归档到 Zotero（2026-09-18 用户指定，**标准收尾步骤**）

**每篇论文译完、`main.pdf` 编译通过后，必须把译稿同步到 Zotero 里对应原文的条目上。**

```bash
# 1) 先【完全退出 Zotero】（Ctrl+Q，确认 23119 端口不再监听）
#    写库必须独占，否则撞锁、或改动被 Zotero 内存状态覆盖

# 2) 预演（列出会挂到哪个条目）
python3 _tools/sync_translation.py

# 3) 执行
python3 _tools/sync_translation.py --apply

# 也可以只处理一篇
python3 _tools/sync_translation.py EdwardsJammed --apply
```

**规则**：
- 附件显示名统一为 **「中文译文」**，文件是该项目目录下的 `main.pdf`
- 匹配顺序：`source.pdf` 元数据标题 → `main.tex` 里的英文副标题 → 与库中标题的关键词交集
- **已挂过同名附件的会自动跳过**，不会产生重复
- 匹配不到的会列出来（库里没有该文献，或标题提取不准），需人工判断
- 每次写库前工具会自动备份到 `_cache/zotero_backup/`

**注意**：若某项目在 Zotero 里根本没有对应条目（例如 Metropolis 1953、ModMag、Miao 等
本库未收录的文献），则跳过即可，或先用 Zotero 自己录入条目后再同步。

---

# 扫描件论文翻译专项（2026-09-17 Metropolis 1953 实战定稿）

> 面向「无文本层 / 只有 OCR 文本层」的老论文扫描件。目标：**一次走通，不返工**。

## 一、先判定有没有文本层，别急着 OCR

```bash
pdfinfo 原PDF                              # 页数 / 页尺寸（算 300dpi 像素）
pdftotext -f 1 -l 3 原PDF - | head -50     # 有文本层吗？正文可读吗？
```

- AIP/APS 老论文下载件常见「图像 + OCR 文本层」：**正文可读、公式必乱**。
- 典型错读：`2^{\nu-8}` → `2- v/8`；`\alpha` → `a`；`\xi_1` → `~l`；`\bar{n}` → `ii`；`\pi` → `7r`；`\surd3` → `3!`。
- 文本层**只用于定位段落与本文起止页**；公式一律以图像为准，不要相信文本层里任何公式。
- 相邻论文残余：用页眉期刊行（如 `THE JOURNAL OF CHEMICAL PHYSICS  VOLUME 21, NUMBER 6  JUNE, 1953`）+ 起始页码定位本文第一页，其前的上一篇残余整段丢弃。

## 二、看图：直接读图，不要用 tesseract

```bash
pdftoppm -r 300 -png -f 2 -l 7 source.pdf pages/pg     # 逐页渲染
```

整页 2400×3200 会被降采样，**公式上下标必然看不清** → 按需裁剪 + 放大再看：

```python
from PIL import Image
c = Image.open('pages/pg-6.png').crop((1220,2060,2400,2260))
c.resize((int(c.width*1.9), int(c.height*1.9)), Image.LANCZOS).save('crops/z.png')
```

- 坐标换算：`原图 y = 裁切起点 + crop图 y / 缩放比`。定位不准就分批上下扫，别赌单一坐标。
- **时间盒：同一处最多放大核对 2 次。** 仍不清 → 按自洽性取读法，并在交付报告里注明「原文此处模糊，按自洽性取 X」。

## 三、数值自洽反推（扫描件公式的最强武器）

公式印糊了，就用论文**自己的数据表、数值结果、极限行为**反推它的形式：

- 幂次/指数不确定 → 用数据表逐行代回验证。（Metropolis 的 `d_0=d(1-2^{\nu-8})` 是靠 Table I 的 8 行 A/A₀ **全部**吻合才定案，文本层的 `2^{-\nu/8}` 是错的。）
- 系数不确定 → 用该领域已知解析结果独立推导。（2D 硬盘 B₂=πd₀²/2、B₃\*=0.782、B₄\*=0.532 → 反推 C₁=π/√3=1.813799、C₂=2.5727、C₃=3.179，与原文 Eq (14) 数值吻合。）
- 记号语义不确定 → 找守恒/恒等关系验证。（`(PA/NkT)-1` 是「减 1」还是「负一次方」：用末列 `PA₀/NkT=(1+X₁)(A₀/A)` 精确验证，ν=2 时 50.17×0.95903=48.11 ✓。）
- **先推后核**：译文里的公式应当是独立推出来的，原刊只作最终比对。

## 四、原文自身矛盾

**照原文照录，不擅改**；在交付报告里单列「原文疑点」。

例：Metropolis Eq (13) 的 C₄ 前置因子印 `8π³/135`，正文亦印 `C₄=8π³(0.585)/135`（=1.075），与 Eq (14) 同位置系数 `3.38` 恰好差一个 π（`8π⁴/135×0.585=3.377`）——照录 + 报告。

## 五、环境坑（DSH 本机实测）

1. **文件工具（`read`/`read_image`/`write`/`edit`/`present`）会概率性报 `not found` 或 `sandbox: file access denied`** → **原位重试一次即成功**。不要据此判定文件不存在而重建。
2. **bash 里 `cd <长绝对路径>` 与 heredoc 组合会失败**（报「没有那个文件或目录」）→ **不要 cd**。cwd 默认就是 workspace 根，直接用 `项目目录/sections/foo.tex` 这类**相对路径 + heredoc** 写文件（实测稳定）。
3. **`/tmp` 在每次 bash 调用之间不共享**（本次调用写的文件下次看不见）→ 中间产物一律放工作区内。
4. **绝对路径写入会被拦，相对路径正常** → 全程统一相对路径。
5. **latexmk 未安装** → `env -C 项目目录 xelatex -interaction=nonstopmode main.tex` 跑两遍（`env -C` 规避 cd 问题）。
6. **amsmath 的 `\tag{}` 会抑制 equation 计数器递增** → 凡用了 `\tag` 的公式，其后必须补 `\addtocounter{equation}{1}`，否则全文编号自该处起整体错位（本次踩过：(12) 起全错一位）。
7. `present` / `dsh_im_return_file` 用**相对路径**更可靠。

## 六、一次到位的开工顺序（照做）

1. `pdfinfo` + `pdftotext` 探文本层 → 定位本文起止页，忽略封面与相邻论文残余
2. 建项目目录 `YYYYMMDD_简称/`，cp 源 PDF，`pdftoppm -r 300` 渲染 `pages/`
3. `pdftotext -layout` 出 `source.txt`，通读掌握结构与**公式清单**
4. 逐页 `read_image` 核对**所有公式、表格、图注**（配合裁剪放大）；不确定处数值反推
5. 先推导公式，再写 LaTeX（`main.tex` + `sections/`；相对路径 + heredoc 写）
6. `env -C` 跑 xelatex 两遍 → 查 `grep -c '^!'`、`Missing character`、`Output written`、**逐式编号序列**
7. 渲染 1–2 页（含公式页）`read_image` 做视觉验收
8. 清理 aux/临时图 → 交付报告：页数、公式核对结论、原文疑点、遗留问题
