# 研究前沿助手（Research Frontier）

把你的 **Zotero 文献库**变成桌面上的一块「研究前沿面板」：自动刻画研究领域画像，
每周抓取 arXiv 与你常读期刊的新论文，用大模型生成中文简报与论文简介，
每天推荐一篇**经典开山之作**，并把一切按日期结构化存档，配一个可离线打开的**日历回顾网页**。

支持 **KDE Plasma 6** 与 **GNOME** 桌面。

---

## 怎么用：把这个目录整个丢给你的 AI 助手

**这是推荐的安装方式。** 下载（或 `git clone`）本仓库后，直接把**整个目录**交给
你的 AI 编程助手（Claude Code / Codex / CodeWhale / Cursor / 任何能读写文件与执行命令的 agent），
然后说一句：

> 这是一个研究前沿助手项目。请读 `AGENT_GUIDE.md`，帮我在这台机器上安装配置好。
> 我的 Zotero 在 `<你的路径>`，工作目录想放在 `<你想放的地方>`。

AI 会照着 `AGENT_GUIDE.md` 完成剩下的事：跑配置向导、探测桌面环境、部署小组件、
装定时任务、验证数据链路。**你只需要回答它问的几个问题**（Zotero 位置、工作目录、
以及可选的 Obsidian / MATLAB / LaTeX 路径）。

> 为什么这样最好：本项目要动 Zotero 库、桌面部件、systemd 定时器，
> 每台机器的桌面环境与路径都不一样。AI 能边看实际情况边调整，比死板的安装脚本可靠得多。

---

## 前置条件

| 项目 | 要求 |
| --- | --- |
| 系统 | Linux，KDE Plasma 6 或 GNOME 45+ |
| Python | 3.10+（**只用标准库**，不需要 pip 安装任何包） |
| 命令行工具 | `curl`；翻译功能需要 `pdftotext` / `pdftohtml` / `pdfinfo`（poppler-utils） |
| Zotero | 本机已装且有文献库（默认 `~/Zotero`） |
| 大模型 | 一个 **DeepSeek API Key**（<https://platform.deepseek.com>），用于生成中文简介与简报 |
| 网络 | 能访问 arXiv / Crossref / api.deepseek.com |

---

## 它做什么

| 功能 | 说明 |
| --- | --- |
| 🧭 **研究画像** | 只读扫描你的 Zotero 库，统计主题词、双词组、期刊分布，生成 `terms.json` |
| 📄 **每周前沿** | 按核心术语检索 arXiv + 按 ISSN 抓你常读期刊，打分筛选后由大模型写中文简介 |
| 📜 **每日经典** | 内置 36 篇开山之作（Metropolis 1953、Kramers 1940、Landauer 1961、Jarzynski 1997…），每天一篇中文回顾，可「换一篇」不限次数 |
| 🗓 **日历回顾网页** | 每天结果结构化存档 + 纯离线网页（含 **KaTeX 公式渲染**），按日期回看 |
| 🔖 **一键收藏** | 把论文作为条目写进 Zotero 指定分类（写库前会检查 Zotero 已退出并自动备份） |
| 👍 **点赞反馈** | 你点赞的论文会影响后续抓取排序（同期刊/同话题加权） |
| 📖 **论文翻译** | 走随包携带的翻译规范（`translate/TRANSLATION_SPEC.md`）：定位全文 → 建项目 → 提取文本与字体 → 交给 AI 产出中文 LaTeX → 回写 Zotero |

---

## 手工安装（不想用 AI 的话）

```bash
python3 wizard.py      # 交互式配置：工作目录 / Zotero / 可选路径 / API Key
bash install.sh        # 探测桌面环境 → 装小组件 → 装每天 06:00 的定时器
python3 update.py all  # 生成第一份简报（3–10 分钟）
python3 preview.py     # 终端里查看结果
```

之后在桌面「添加部件」里搜 **研究前沿** 拖出来。

---

## 常用命令

```bash
python3 update.py all               # 完整跑一轮（抓取 + LLM + 存档）
python3 update.py all --force       # 忽略「本周已更新」，强制重跑前沿
python3 update.py status            # 数据状态 / API key / Zotero 是否可读
python3 update.py profile           # 只重建画像
python3 update.py crawl             # 只抓取+评分，打印候选
python3 update.py synth             # 只重新生成综合简报
python3 classic.py new              # 换一篇经典
python3 preview.py [--profile|--all|N|--md]
bash install.sh --no-timer          # 只装小组件
systemctl --user list-timers research-frontier.timer
```

---

## 你的工作目录

向导会问你把它放哪（默认 `~/research-frontier-work`）。所有属于你的东西都在这里：

```
<工作目录>/
├── config.json            你的配置（向导生成，可手改）
├── terms.json             你的研究领域词典（向导生成，可手改）
├── runtime/               运行时 JSON（桌面小组件读这里）
├── daily/                 每日结构化存档
│   ├── 2026-09-18.json
│   ├── 2026-09-18.md
│   └── site/index.html    📅 日历回顾网页（双击离线打开）
└── translations/          翻译项目（按翻译规范建立）
```

**本仓库自身不存任何你的数据**，所以你随时可以删掉/更新这个目录而不影响已生成的成果。

---

## 刷新节奏

| 内容 | 节奏 |
| --- | --- |
| 前沿论文（抓取 + 简介 + 综合简报） | **每周一次**（每天 06:00 检查，本周已刷过就跳过抓取与大模型调用） |
| 经典论文回顾 | 每天一篇，另有「🎲 换一篇」不限次数 |
| 画像 / 存档 / 日历 | 每次更新时刷新 |

强制重跑前沿：`python3 update.py all --force`

---

## 关于 Zotero 权限

- **读取**：用 SQLite 的 `immutable` 模式打开 `zotero.sqlite`，**不会干扰正在运行的 Zotero**，也不加锁。
- **写入**（点「☆ 收藏」或翻译完成后回写译稿时）：
  - 需要**先完全退出 Zotero**（判据：`23119` 端口不再监听），否则会撞库锁
  - 工具会自动把 `zotero.sqlite` 备份到 `_cache/` 再写
  - 新条目建到配置里的 `zotero_collection` 分类（默认「研究前沿app收藏」）
  - 写完后 `synced=0`，等你下次打开 Zotero 同步时上传
- 不点「收藏」、不跑翻译回写，就永远不会写你的库。

---

## 关于大模型调用

- 抓取/简介默认模型：`deepseek-v4-flash`（快、省）
- 综合简报模型：`deepseek-v4-pro`（需要跨文献综合）
- 一轮（15 篇简介 + 1 份简报）约 2 万 token
- 简介按「DOI/标题 + 摘要 hash」缓存，论文没变就不重复花钱
- 只发送论文的**标题/摘要/期刊**等公开元数据，不上传你的笔记或本地文件

---

## 常见问题

| 现象 | 处理 |
| --- | --- |
| 小组件空白、显示「读取中…」 | 先跑 `python3 update.py all`；确认工作目录下 `runtime/*.json` 存在 |
| 改完 QML 界面不变 | 必须重载桌面：`systemctl --user restart plasma-plasmashell.service`（KDE） |
| 简介或简报为空 | 看 `runtime/update.log` 里的报错；多为 API Key 失效或超时 |
| 抓取排序不合理 | 编辑 `terms.json` 的 `core` / `secondary`，或调整 `config.json` 的 `min_score` |
| 点「收藏」提示 Zotero 在运行 | 完全退出 Zotero（Ctrl+Q）再试 |
| 点「翻译」提示没有全文 | 本包**不下载全文**。请在 Zotero 里获取该论文的 PDF（条目右键「查找可用的 PDF」或手工拖入），再重跑 |
| 网页公式显示成灰底等宽字 | 跑 `python3 setup_katex.py` 补齐 KaTeX |
| 定时器没触发 | `systemctl --user list-timers research-frontier.timer`；未登录时 user timer 不跑 |

---

## 给 AI 助手

请看 **[AGENT_GUIDE.md](AGENT_GUIDE.md)** —— 那里写清了环境依赖、数据流、文件职责、
**已知的坑**（QML / 抓取 / 推理模型 / 离线网页各自的陷阱）以及逐项验证方法。

---

## 许可

MIT
