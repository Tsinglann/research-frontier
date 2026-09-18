#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""研究前沿助手 —— 配置。

所有路径与偏好都从 <workdir>/config.json 读取（由 wizard.py / install.sh 生成），
**包里不含任何作者的路径或研究画像**。缺失项用保守默认值。
"""
import json
import os

PKG_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

_DEFAULTS = {
    'workdir': os.path.join(os.path.expanduser('~'), 'research-frontier-work'),
    'zotero_dir': os.path.join(os.path.expanduser('~'), 'Zotero'),
    'data_dir': '',
    'obsidian_vault': '',
    'matlab_dir': '',
    'latex_dirs': [],
    'window_days': 45,
    'top_n': 15,
    'min_score': 3.0,
    'max_per_source': 3,
    'model_brief': 'deepseek-v4-flash',
    'model_synth': 'deepseek-v4-pro',
    'journals': [],
    'zotero_collection': '研究前沿app收藏',
}


def _load():
    """配置查找顺序：环境变量 → 包内 config.json → 工作目录 config.json → 默认值。"""
    cfg = dict(_DEFAULTS)
    candidates = []
    env = os.environ.get('RESEARCH_FRONTIER_CONFIG')
    if env:
        candidates.append(env)
    candidates.append(os.path.join(PKG_DIR, 'config.json'))
    wd = os.environ.get('RESEARCH_FRONTIER_WORKDIR')
    if wd:
        candidates.append(os.path.join(wd, 'config.json'))
    candidates.append(os.path.join(
        os.path.expanduser('~'), 'research-frontier-work', 'config.json'))
    for c in candidates:
        try:
            with io_open(c) as f:
                cfg.update({k: v for k, v in json.load(f).items()
                            if not k.startswith('_')})
            break
        except Exception:
            continue
    return cfg


def io_open(path):
    return open(path, encoding='utf-8')


CONFIG = _load()

HOME = os.path.expanduser('~')
WORKDIR = os.path.expanduser(CONFIG['workdir'])
DATA_DIR = os.path.expanduser(CONFIG['data_dir']) if CONFIG['data_dir'] \
    else os.path.join(WORKDIR, 'runtime')
ZOTERO_DIR = os.path.expanduser(CONFIG['zotero_dir'])
ZOTERO_DB = os.path.join(ZOTERO_DIR, 'zotero.sqlite')
OBSIDIAN_VAULT = os.path.expanduser(CONFIG['obsidian_vault']) \
    if CONFIG['obsidian_vault'] else ''
MATLAB_DIR = os.path.expanduser(CONFIG['matlab_dir']) if CONFIG['matlab_dir'] else ''
LATEX_DIRS = [os.path.expanduser(p) for p in (CONFIG.get('latex_dirs') or [])]
LATEX_ROOT = LATEX_DIRS[0] if LATEX_DIRS else os.path.join(WORKDIR, 'latex')
# 翻译项目放在工作目录下（发行版约定：翻译都在用户选定的工作目录进行）
TRANSLATE_ROOT = os.path.join(WORKDIR, 'translations')

# ---- 运行时产物 ----
PROFILE_JSON = os.path.join(DATA_DIR, 'profile.json')
PAPERS_JSON = os.path.join(DATA_DIR, 'papers.json')
BRIEF_JSON = os.path.join(DATA_DIR, 'brief.json')
BRIEF_MD = os.path.join(DATA_DIR, 'brief.md')
STATE_JSON = os.path.join(DATA_DIR, 'state.json')
LOG_FILE = os.path.join(DATA_DIR, 'update.log')
ACTIONS_JSON = os.path.join(DATA_DIR, 'actions.json')
CONFIG_USER = os.path.join(WORKDIR, 'config.json')

# ---- DeepSeek ----
DEEPSEEK_BASE = 'https://api.deepseek.com'
MODEL_BRIEF = CONFIG['model_brief']
MODEL_SYNTH = CONFIG['model_synth']
HTTP_TIMEOUT = 180
USER_AGENT = 'research-frontier/1.0'

# ---- 抓取规模 ----
WINDOW_DAYS = int(CONFIG['window_days'])
TOP_N = int(CONFIG['top_n'])
MIN_SCORE = float(CONFIG['min_score'])
MAX_PER_SOURCE = int(CONFIG['max_per_source'])
JOURNAL_QUOTA = 4
ZOTERO_COLLECTION = CONFIG['zotero_collection']

# ---- 期刊（按 ISSN 抓最新论文）----
CROSSREF_JOURNALS = [
    (j['name'], j['issn'], 2.0) for j in (CONFIG.get('journals') or [])
    if j.get('name') and j.get('issn')
]

ARXIV_MAX = 240
ARXIV_QUERY_BATCH = 6
ARXIV_PER_BATCH = 45
ARXIV_CATEGORIES = ['cond-mat.stat-mech', 'cond-mat.soft', 'physics.comp-ph', 'nlin.CD']

# ---- 词典与画像 ----
# 发行版**不含任何作者领域的硬编码词表**：改用 <workdir>/terms.json（由 setup_wizard 生成）
# 或用户手写。缺失时给一个跨领域通用骨架，保证开箱可跑。
_TERMS_FILE = os.path.join(WORKDIR, 'terms.json')


def _load_terms():
    try:
        with io_open(_TERMS_FILE) as f:
            d = json.load(f)
        return (d.get('core') or [], d.get('secondary') or [],
                d.get('weak') or [], d.get('clusters') or {})
    except Exception:
        return ([], [], [], {})


TERMS_CORE, TERMS_SECONDARY, TERMS_WEAK, TOPIC_CLUSTERS = _load_terms()

if not TERMS_CORE:
    # 兜底：从 Zotero 标题自动提取的关键词会写进 terms.json；这里只放极通用的词
    TERMS_CORE = ['review', 'theory', 'model', 'experiment', 'simulation']
    TERMS_SECONDARY = ['method', 'analysis', 'measurement', 'dynamics']
    TERMS_WEAK = ['study', 'data', 'system']
if not TOPIC_CLUSTERS:
    TOPIC_CLUSTERS = {'未分类': list(TERMS_CORE)}

TERM_WEIGHTS = {}
for _t in TERMS_CORE:
    TERM_WEIGHTS[_t] = 3.0
for _t in TERMS_SECONDARY:
    TERM_WEIGHTS[_t] = 2.0
for _t in TERMS_WEAK:
    TERM_WEIGHTS[_t] = 1.0

# 期刊加成：可按需在 config.json 的 journals 里用 weight 字段覆盖
JOURNAL_BONUS = [(j[0].lower(), j[2] if len(j) > 2 else 1.0)
                 for j in CROSSREF_JOURNALS] or [('', 1.0)]

OFF_TOPIC_TERMS = []      # 发行版留空：无关领域过滤交给用户按需配置
OFF_TOPIC_PENALTY = 0.12

NOISE_WORDS = set("""pdf fulltext full text file article download attachment
supplement supplementary supporting appendix manuscript accepted
version copy author authors preprint""".split())
