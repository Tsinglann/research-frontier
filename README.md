# 研究前沿助手（Research Frontier）

把你的 **Zotero 文献库**变成桌面上的一块「研究前沿面板」：自动刻画你的研究领域画像，
每周抓取 arXiv 与你常读期刊的新论文，用大模型生成中文简报与论文简介，
每天推荐一篇**经典开山之作**，并把一切按日期结构化存档，配一个可离线打开的**日历回顾网页**。

支持 **KDE Plasma 6** 与 **GNOME** 桌面。

> 这是一个**干净的可分发包**：不含任何作者的个人路径、研究画像、密码或主机信息。
> 所有与你有关的东西都由向导现场询问、只存在你自己机器上的工作目录里。

---

## 它做什么

| 功能 | 说明 |
| --- | --- |
| 🧭 **研究画像** | 只读扫描你的 Zotero 库，统计主题词、双词组、期刊分布，生成 `terms.json` |
| 📄 **每周前沿** | 按核心术语检索 arXiv + 按 ISSN 抓你常读期刊，打分筛选后由 LLM 写中文简介 |
| 📜 **每日经典** | 内置 36 篇开山之作（Metropolis 1953、Kramers 1940、Landauer 1961、Jarzynski 1997…），每天一篇中文回顾，可「换一篇」不限次数 |
| 🗓 **日历回顾网页** | 每天的结果结构化存档 + 一个纯离线网页（含 **KaTeX 公式渲染**），可按日期回看 |
| 🔖 **一键收藏** | 把论文作为条目写进 Zotero 指定分类（需你授权写库） |
| 👍 **点赞反馈** | 你点赞的论文会影响后续抓取排序（同刊/同话题加权） |
| 📖 **论文翻译** | 走随包携带的翻译 SOP：下载/复用全文 → 建项目 → 提取文本与字体 → 交给 AI 产出中文 LaTeX |

---

## 安装

### 0. 依赖

- Python **3.10+**（只用标准库，无需 pip 安装任何包）
- `curl`、`pdftotext` / `pdftohtml` / `pdfinfo`（poppler-utils，**翻译功能需要**）
- 一个 **DeepSeek API Key**（<https://platform.deepseek.com>）——用于生成中文简介与简报
- 桌面环境：KDE Plasma 6 或 GNOME 45+
- （可选）`zotero` 本机安装并有文献库

### 1. 配置向导

```bash
git clone <这个仓库> research-frontier
cd research-frontier
python3 wizard.py
```

向导会依次询问：

1. **工作目录** —— 数据、存档、翻译项目都放这里（默认 `~/research-frontier-work`）
2. **Zotero 数据目录** —— 默认 `~/Zotero`；向导会**只读**打开它来生成你的画像
3. **是否用该库生成画像** —— 会写出 `<工作目录>/terms.json`（可手工编辑）
4. **Obsidian 库**（可选）—— 填了会把「正在跟进的笔记」纳入画像
5. **MATLAB 程序目录**（可选）—— 扫描 `.m` 文件关键词，纳入「当前工作内容」
6. **LaTeX / Markdown 工作目录**（可选）—— 同上
7. **是否允许自动下载全文** —— **默认否**（见下方「与作者自用版的差异」）
8. **DeepSeek API Key** —— 也可改用环境变量

### 2. 部署桌面小组件

```bash
bash install.sh
```

脚本会：

- 探测桌面环境（Plasma / GNOME），安装对应的小组件
- 注册 `systemd --user` 定时器（**每天 06:00** 自动更新）
- 可选地下载 KaTeX 到本地（网页公式渲染用）

### 3. 生成第一份简报

```bash
python3 update.py all        # 约 3–10 分钟（抓取 + LLM）
python3 preview.py           # 终端里看结果
```

然后在桌面「添加部件」里搜 **研究前沿** 拖出来。

---

## 目录结构

```
research-frontier/
├── wizard.py              安装向导（Zotero 授权 + 画像生成 + 写配置）
├── install.sh             部署小组件（Plasma / GNOME）+ 定时器
├── uninstall.sh
├── setup_katex.py         下载 KaTeX（网页公式渲染，可选）
├── update.py              主流程：画像 → 抓取 → 评分 → LLM → 存档
├── action.py              部件按钮后端（翻译 / 收藏 / 点赞 / 换经典）
├── classic.py             换一篇经典论文
├── translate_worker.py    翻译准备（下全文 → 建项目 → 提取数据）
├── preview.py             终端预览
├── researchlib/           后端模块
│   ├── config.py          配置（全部从 config.json 读，无硬编码路径）
│   ├── zotero.py          只读读 Zotero 库
│   ├── zotero_write.py    写 Zotero（收藏，需授权）
│   ├── profile.py         画像与论文评分
│   ├── crawl.py           arXiv / Crossref 抓取
│   ├── llm.py             DeepSeek 调用
│   ├── brief.py           简报与存档流程
│   ├── archive.py         每日存档 + 日历网页（含 KaTeX 内联）
│   └── classics.py        经典论文典籍库
├── plasmoid/              KDE Plasma 6 小组件
├── gnome/                 GNOME Shell 扩展
├── translate/             翻译 SOP 与工具（随包携带）
└── templates/             配置模板
```

你的工作目录长这样：

```
~/research-frontier-work/
├── config.json            你的配置（向导生成，可手改）
├── terms.json             你的研究领域词典（向导生成，可手改）
├── runtime/               运行时 JSON（小组件读这里）
├── daily/                 每日结构化存档
│   ├── 2026-09-18.json
│   ├── 2026-09-18.md
│   └── site/index.html    📅 日历回顾网页（双击离线打开）
└── translations/          翻译项目（按翻译 SOP 建立）
```

---

## 常用命令

```bash
python3 update.py all               # 完整跑一轮
python3 update.py all --force       # 忽略「本周已更新」，强制重跑前沿
python3 update.py status            # 看数据状态 / API key / Zotero 是否可读
python3 update.py profile           # 只重建画像
python3 update.py crawl             # 只抓取+评分，打印候选
python3 update.py synth             # 只重新生成综合简报
python3 classic.py new              # 换一篇经典
python3 preview.py [--profile|--all|N|--md]
bash install.sh --no-timer          # 只装小组件
systemctl --user list-timers research-frontier.timer
```

---

## 刷新节奏

| 内容 | 节奏 |
| --- | --- |
| 前沿论文（抓取 + 简介 + 综合简报） | **每周一次**（每天 06:00 检查，本周已刷过就跳过抓取与 LLM） |
| 经典论文回顾 | 每天一篇，另有「🎲 换一篇」不限次数 |
| 画像 / 存档 / 日历 | 每次更新时刷新 |

强制重跑前沿：`python3 update.py all --force`

---

## 关于 Zotero 权限

- **读取**：向导用 SQLite 的 `immutable` 模式打开 `zotero.sqlite`，**不会干扰正在运行的 Zotero**，
  也不加锁。这是只读操作。
- **写入**（点「☆ 收藏」时）：
  - **必须先完全退出 Zotero**（判据：23119 端口不再监听），否则会撞库锁
  - 工具会自动把 `zotero.sqlite` 备份到 `_cache/` 再写
  - 新条目会建到配置里的 `zotero_collection` 分类（默认「研究前沿app收藏」）
  - 条目写入后 `synced=0`，等你下次打开 Zotero 同步时上传
- 不点「收藏」就永远不会写你的库。

---

## 关于 DeepSeek API

- 抓取默认模型：`deepseek-v4-flash`（简介、经典回顾）
- 综合简报模型：`deepseek-v4-pro`（需要跨文献综合）
- 一轮（15 篇简介 + 1 份简报）约 2 万 token
- 简介按「DOI/标题 + 摘要 hash」缓存，论文没变就不重复花钱
- ⚠️ 这两个模型是**推理型**：`max_tokens` 给小了会把预算全花在 reasoning 上导致正文为空。
  代码里已给足（简介 3000 / 简报 12000）并把空内容当失败重试。

---

## 与作者自用版的差异

发行版刻意**阉割**了一些东西，避免误用与隐私问题：

| 项目 | 作者自用版 | 发行版 |
| --- | --- | --- |
| 自动下载论文全文 | 开 | **默认关**（`enable_auto_fetch: false`）——点「📖 翻译」时若 Zotero 里没有全文会明确提示，而不是静默联网下载 |
| 研究领域词典 | 硬编码在代码里 | **由向导从你的 Zotero 生成** `terms.json`，可手改 |
| 无关领域过滤 | 有硬编码黑名单 | 留空，按需自己配 `OFF_TOPIC_TERMS` |
| 研究前沿部件 | 有 | **不含**（那是作者个人的服务器监控，与本项目无关） |
| 个人路径/画像/密码 | 有 | **已全部清除** |

---

## 故障排查

| 现象 | 处理 |
| --- | --- |
| 小组件空白、显示「读取中…」 | 先跑 `python3 update.py all`；再确认 `runtime/*.json` 存在 |
| 小组件改完 QML 不变 | 必须重载桌面：`systemctl --user restart plasma-plasmashell.service`（KDE） |
| 简介为空 / 简报为空 | 看 `runtime/update.log` 的 DeepSeek 报错；多为 key 失效或超时 |
| 抓取排序不合理 | 编辑 `terms.json` 的 `core` / `secondary`，或调 `min_score` |
| 「收藏」提示 Zotero 在运行 | 完全退出 Zotero（Ctrl+Q）再试 |
| 网页公式显示成灰底等宽字 | 跑 `python3 setup_katex.py` 补齐 KaTeX |
| 定时器没触发 | `systemctl --user list-timers research-frontier.timer`；未登录时 user timer 不跑 |

---

## 给 AI 助手（Claude Code / Codex / CodeWhale / Cursor…）

本仓库可以直接交给 AI 助手来部署与二次开发。请看 **[AGENT_GUIDE.md](AGENT_GUIDE.md)**，
里面写清了环境依赖、数据流、文件职责、已知坑与验证方法。

---

## 许可

MIT
