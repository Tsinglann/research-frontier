# AGENT_GUIDE —— 给 AI 助手的复现与改造指引

本文件面向 Claude Code / Codex / CodeWhale / Cursor 等 AI 编程助手。
目标：让你能在一台**全新的 Linux 机器**上把本项目跑起来，或按用户需求改造它。

---

## 0. 一句话架构

```
Zotero 库 ──只读──> 画像(terms.json) ──┐
用户配置(config.json) ────────────────┤
                                     ├─> 抓取(arXiv + Crossref) ─> 打分筛选 ─> DeepSeek
                                     │                                        │
                                     └────────── 每日存档(daily/) <───────────┘
                                                     │
                          桌面小组件(Plasma/GNOME) <── runtime/*.json
                                     │
                          日历网页(daily/site/index.html) ── 浏览器
```

**关键分工**：Python 后端负责一切数据与 LLM；桌面小组件只负责「读 JSON 并显示 + 把按钮点击转发给 `action.py`」。
所以换桌面环境只需重写 UI 层，后端不用动。

---

## 1. 环境要求

```bash
python3 --version        # 需要 3.10+；只用标准库
which curl pdftotext pdftohtml pdfinfo    # 翻译功能需要 poppler-utils
echo $DEEPSEEK_API_KEY   # 或写进 <包目录>/.env
```

KDE Plasma 6：需要 `plasma-workspace 6.x`、`kbuildsycoca6`、`qmllint`（调试用）
GNOME：`gnome-shell 45+`、`gnome-extensions`

---

## 2. 首次部署步骤（照着做）

```bash
cd <包目录>
python3 wizard.py            # 交互式；非交互可用 --yes 全默认
bash install.sh              # 探测桌面 → 装小组件 → 装 systemd timer
python3 update.py all        # 第一份简报（3–10 分钟）
python3 preview.py           # 终端验证
```

验证清单（**不要只看命令退出码**）：

1. `python3 update.py status` —— 应显示 Zotero 可读、API key OK、数据目录路径
2. `ls $WORKDIR/runtime/` —— 应有 `profile.json papers.json brief.json actions.json state.json`
3. `python3 preview.py --profile` —— 画像应有真实的主题词与期刊分布
4. KDE：`journalctl --user -u plasma-plasmashell.service | grep researchfrontier`
   —— 应看到 `ingest papers: N 字节` 与 `✓ 已装载 papers：N 篇`
5. 网页：`xdg-open $WORKDIR/daily/site/index.html`

---

## 3. 文件职责速查

| 文件 | 职责 | 改动注意 |
| --- | --- | --- |
| `researchlib/config.py` | 读 `config.json` → 常量；**所有路径都在这里** | 加新配置项要同时改 `templates/config.example.json` 与 `wizard.py` |
| `researchlib/zotero.py` | 只读库（immutable 打开） | 不要加写操作 |
| `researchlib/zotero_write.py` | 写库（收藏） | 写前必须检查 Zotero 未运行 + 自动备份 |
| `researchlib/profile.py` | 画像 + 评分（含点赞反馈加成） | 词典来自 `terms.json`，不要硬编码领域词 |
| `researchlib/crawl.py` | arXiv（交错分批）+ Crossref（按 ISSN） | 见下方「抓取坑」 |
| `researchlib/llm.py` | DeepSeek 调用 | 见下方「推理模型坑」 |
| `researchlib/brief.py` | 编排：画像→抓取→评分→LLM→存档 | 入口是 `build_brief()` |
| `researchlib/archive.py` | 每日存档 + 日历网页（KaTeX 内联） | 见下方「网页坑」 |
| `researchlib/classics.py` | 36 篇经典典籍 | 纯数据，直接加条目 |
| `plasmoid/` | KDE 小组件 | 见下方「QML 坑」 |
| `gnome/` | GNOME 扩展（只读 JSON + 转发按钮） | 需要 `@DATA_DIR@` 占位符替换 |
| `translate/` | 翻译 SOP 与工具 | SOP 是 AI 执行翻译时的作业指导书 |

---

## 4. 已知坑（都是实测踩过的，务必避开）

### QML / 桌面小组件

1. **`P5S.DataSource` 直接 `/bin/cat <绝对路径>.json`，不要在中间套 shell 脚本**。
   实测：`DataSource → collect.sh → cat` 时 QML 只拿到 3 字节 `{}`；直接 cat 就正常。
2. **`XMLHttpRequest` + `file://` 会被 Plasma 静默拒绝** —— 界面空白且 journal 无报错。
3. **`font.pixelSize` 必须是整数**：`9.5` 会让整个文件解析失败 → `Type xxx unavailable`。
   改完 QML 一定跑：`grep -rn 'pixelSize: [0-9]*\.' plasmoid/contents/ui/*.qml`（必须为空）。
4. **QML 属性名不能与基类重名**：`Rectangle` 自带 `panel`/`radius`，自定义同名属性会
   `Property value set multiple times` 并导致类型加载失败。
5. **改完必须重载 plasmashell**：`systemctl --user restart plasma-plasmashell.service`，
   否则运行中的实例会一直用内存里的旧 QML。
6. **给数据做字段兜底**：定时任务运行中会整体替换 `runtime/*.json`，视图里直接访问
   `obj.a.b` 会在那一瞬间抛 `TypeError`。统一在 `ingest()` 里 `|| []` / `|| 0` / `|| "—"`。
7. **验证手法**：`plasmawindowed <id>` 退出码 **124 = 正常跑到超时**；
   不要 `| head`（`$?` 会变成 head 的退出码）。`qmllint` 只查语法，抓不到运行期错误。

### 抓取

8. **arXiv 单次大 OR 查询有严重采样偏差**：15 个术语 OR 成一条、按日期倒序取 150 条，
   最新提交会占满名额（实测 54/150 挤在两天内）。本包用**交错分批**
   （`terms[i::6]` 分 6 组）解决。
9. **纯术语命中数打分偏向长摘要**：短摘要的好文章会被挤掉，所以有 `JOURNAL_BONUS` 期刊加成。
10. **候选与入选都要按来源配额**（`MAX_PER_SOURCE`），避免单一期刊霸榜。

### DeepSeek（推理型模型）

11. **`max_tokens` 会被 reasoning 吃光**：简介给 900 时正文被截断甚至返回空串；
    综合简报给 2600 时正文完全为空。本包用 3000 / 12000，并把空内容当失败重试。
12. `reasoning_effort: low` **不减少** reasoning token（实测 796 > 默认 257），别用它省 token。

### 网页

13. **`file://` 打开时浏览器以 CORS 拒绝加载同目录的 .js/.css** ——
    所以 KaTeX 的样式与脚本必须**内联进 HTML**（字体走相对路径没问题）。
14. 日历网页的数据也**内联在 `site/data.js`** 里，正是为了绕开这个限制。

### 路径

15. **Linux 上大小写是敏感的**：`~/Documents/Foo` 与 `~/Documents/foo` 是两个**不同目录**
    （本项目开发期就被这个坑过一次，浪费了很久）。脚本里一律用
    `os.path.expanduser` + 配置项，不要写死路径；调试时先 `pwd` + `ls` 确认。

---

## 5. 改造指引

### 换领域（最常见）

不需要改代码。让用户编辑 `<工作目录>/terms.json`：

```json
{
  "core":       ["你的核心术语", "bigram 更有效，例如 entropy production"],
  "secondary":  ["相关分支术语"],
  "weak":       ["外围术语"],
  "clusters":   { "方向名": ["术语1", "术语2"] }
}
```

`core` 权重 3、`secondary` 2、`weak` 1。

### 换期刊

编辑 `config.json` 的 `journals`（名称 + ISSN）。ISSN 可从期刊官网或 Zotero 条目里查。

### 加一台桌面环境（如 XFCE / Waybar）

后端完全不用动。新写一个 UI，只要能：

1. 每 N 分钟读 `<data_dir>/{profile,papers,brief,actions}.json`
2. 展示 `brief.markdown_short`、`papers[].summary_short`、`brief.classic.review`
3. 把按钮点击转成 `python3 action.py <collect|like|translate|newclassic> [rank]`

`action.py` 的用法在它自己的 `--help` 与文件头注释里。

### 换 LLM 供应商

改 `researchlib/llm.py` 的 `chat()`：它只依赖一个 OpenAI 兼容的
`POST /chat/completions`。`config.json` 里已把模型名参数化。

---

## 6. 安全与隐私约定（改造时请保持）

- **不采集、不上传**任何用户数据；所有产物都在用户选定的工作目录
- 读 Zotero 用 `immutable` 模式，绝不加锁、绝不改动
- 写 Zotero 前必须检查 23119 未监听（Zotero 已退出），并自动备份
- API Key 只从环境变量或 600 权限的 `.env` 读取，不要写进仓库
- 不要在任何文件里硬编码个人路径、姓名、邮箱、服务器地址、密码

---

## 7. 快速自检脚本

```bash
python3 - <<'PY'
import json, os, sys
sys.path.insert(0, '.')
from researchlib import config as C
print('workdir   :', C.WORKDIR)
print('data_dir  :', C.DATA_DIR)
print('zotero db :', C.ZOTERO_DB, '存在' if os.path.exists(C.ZOTERO_DB) else '**缺失**')
print('terms     :', len(C.TERMS_CORE), '个核心词')
print('journals  :', len(C.CROSSREF_JOURNALS), '种')
print('auto_fetch:', C.ENABLE_AUTO_FETCH)
PY
```
