#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""研究前沿助手 —— 经典论文回顾库。

每天从本地典籍库里取一篇「开山之作」，由 DeepSeek 生成简短中文回顾
（为什么重要 / 核心贡献 / 与用户当前研究的关系）。

这里**不联网、不检索**：典籍是人工维护的常青列表，稳定性优先于新鲜度。
要增删直接改 `CLASSICS` 即可（按 title 去重，被缓存的回顾不会丢失）。
"""
import datetime as dt

# 每项：标题 / 作者 / 年份 / 出处 / 领域标签 / 一句话定位
CLASSICS = [
    dict(title="Equation of State Calculations by Fast Computing Machines",
         authors="N. Metropolis, A. W. Rosenbluth, M. N. Rosenbluth, A. H. Teller, E. Teller",
         year=1953, venue="J. Chem. Phys. 21, 1087",
         tags=["蒙特卡洛", "采样"],
         note="Metropolis 算法：用随机采样算平衡态，现代 MCMC 的起点。"),
    dict(title="Simulating Physics with Computers",
         authors="R. P. Feynman", year=1982, venue="Int. J. Theor. Phys. 21, 467",
         tags=["计算物理"],
         note="提出用量子系统模拟量子系统，量子计算的思想源头。"),
    dict(title="There's Plenty of Room at the Bottom",
         authors="R. P. Feynman", year=1959, venue="Caltech 演讲 (J. Microelectromech. Syst. 1, 60)",
         tags=["纳米"],
         note="纳米科学与自下而上构造的开篇宣言。"),
    dict(title="Brownian Motion and Stochastic Theory of Irreversible Processes",
         authors="N. G. van Kampen", year=1981, venue="North-Holland 专著",
         tags=["朗之万方程", "主方程"],
         note="随机过程与主方程的标准教科书，介观热力学的语言基础。"),
    dict(title="Brownian Motion in a Field of Force and the Diffusion Model of Chemical Reactions",
         authors="H. A. Kramers", year=1940, venue="Physica 7, 284",
         tags=["克拉默斯", "逃逸率"],
         note="Kramers 逃逸率：把化学反应速率写成势垒扩散问题。"),
    dict(title="The Fokker-Planck Equation: Methods of Solution and Applications",
         authors="H. Risken", year=1984, venue="Springer 专著",
         tags=["福克-普朗克"],
         note="Fokker-Planck 方程求解方法的权威参考。"),
    dict(title="Irreversibility and Heat Generation in the Computing Process",
         authors="R. Landauer", year=1961, venue="IBM J. Res. Dev. 5, 183",
         tags=["兰道尔原理", "信息热力学"],
         note="擦除一位信息的极限耗散 k_B T ln2，信息与热力学的桥梁。"),
    dict(title="Minimal Energy Cost for Thermodynamic Information Processing",
         authors="T. Sagawa, M. Ueda", year=2010, venue="Phys. Rev. Lett. 104, 090602",
         tags=["信息热力学"],
         note="Sagawa-Ueda 等式：把信息作为热力学资源定量化。"),
    dict(title="Irreversibility and Generalized Fluctuation-Dissipation Theorem",
         authors="D. J. Evans, E. G. D. Cohen, G. P. Morriss", year=1993, venue="Phys. Rev. Lett. 71, 2401",
         tags=["涨落定理"],
         note="涨落定理的最早形式之一（Evans-Cohen-Morriss）。"),
    dict(title="Equilibrium Information from Nonequilibrium Measurements",
         authors="C. Jarzynski", year=1997, venue="Phys. Rev. Lett. 78, 2690",
         tags=["Jarzynski 等式", "功定理"],
         note="Jarzynski 等式：非平衡功的指数平均等于自由能差。"),
    dict(title="Entropy Production Fluctuation Theorem and the Nonequilibrium Work Relation",
         authors="G. E. Crooks", year=1999, venue="Phys. Rev. E 60, 2721",
         tags=["Crooks 定理"],
         note="Crooks 定理：正逆过程功分布之比给出熵产生。"),
    dict(title="Entropy Production along a Stochastic Trajectory and an Integral Fluctuation Theorem",
         authors="U. Seifert", year=2005, venue="Phys. Rev. Lett. 95, 040602",
         tags=["随机热力学", "轨迹熵"],
         note="轨迹层面的熵产生定义与积分涨落定理，随机热力学的基石。"),
    dict(title="Stochastic Thermodynamics: Principles and Applications",
         authors="U. Seifert", year=2012, venue="Rep. Prog. Phys. 75, 126001",
         tags=["随机热力学", "综述"],
         note="随机热力学最常被引用的综述（你正在跟读的那篇）。"),
    dict(title="Fluctuation Theorem for Stochastic Dynamics",
         authors="J. Kurchan", year=1998, venue="J. Phys. A 31, 3719",
         tags=["涨落定理"],
         note="把涨落定理推广到随机动力学的一般框架。"),
    dict(title="The Feynman Lectures on Physics, Vol. I, Ch. 46 (Ratchet and Pawl)",
         authors="R. P. Feynman, R. B. Leighton, M. Sands", year=1963, venue="Addison-Wesley",
         tags=["棘轮", "布朗马达"],
         note="费曼棘轮：用热二律否掉布朗马达的原始想象。"),
    dict(title="Forced Thermal Ratchets",
         authors="M. O. Magnasco", year=1993, venue="Phys. Rev. Lett. 71, 1477",
         tags=["布朗马达"],
         note="证明涨落 + 非平衡驱动可产生定向输运，布朗马达复兴之作。"),
    dict(title="Modeling Molecular Motors",
         authors="F. Jülicher, A. Ajdari, J. Prost", year=1997, venue="Rev. Mod. Phys. 69, 1269",
         tags=["分子马达"],
         note="分子马达的物理模型综述，把棘轮与 ATP 化学循环接起来。"),
    dict(title="Brownian Motors: Noisy Transport far from Equilibrium",
         authors="P. Reimann", year=2002, venue="Phys. Rep. 361, 57",
         tags=["布朗马达", "综述"],
         note="布朗马达领域的权威长篇综述。"),
    dict(title="Maxwell's Demon in Biochemical Signal Transduction",
         authors="S. Ito, T. Sagawa", year=2015, venue="Nat. Commun. 6, 7498",
         tags=["麦克斯韦妖", "信息热力学"],
         note="把麦克斯韦妖式信息-能量转换落到生化信号传导。"),
    dict(title="Irreversibility and Fluctuation Theorem in Stationary Time Series",
         authors="T. Harada, S.-i. Sasa", year=2005, venue="Phys. Rev. Lett. 95, 130602",
         tags=["熵产生", "时间序列"],
         note="从有限时间序列估计熵产生，实验可测路线的代表。"),
    dict(title="Thermodynamic Uncertainty Relation for Biomolecular Processes",
         authors="A. C. Barato, U. Seifert", year=2015, venue="Phys. Rev. Lett. 114, 158101",
         tags=["热力学不确定关系"],
         note="TUR：精度-耗散的定量权衡，近年最热的方向之一。"),
    dict(title="A Gallery of Fluid Motion",
         authors="M. Van Dyke", year=1982, venue="Annu. Rev. Fluid Mech. 14, 1",
         tags=["流体"],
         note="流动可视化经典图集（方法与审美并重）。"),
    dict(title="Statistical Mechanics of Powder Compacts",
         authors="S. F. Edwards, R. B. S. Oakeshott", year=1989, venue="Physica A 157, 1080",
         tags=["Edwards 系综", "颗粒物质"],
         note="Edwards 体积系综：给静态颗粒堆积造一套统计力学。"),
    dict(title="Granular Matter: A Tentative View",
         authors="P. G. de Gennes", year=1999, venue="Rev. Mod. Phys. 71, S374",
         tags=["颗粒物质"],
         note="de Gennes 对颗粒物质统计描述的展望性评论。"),
    dict(title="Jamming of Granular Matter",
         authors="A. J. Liu, S. R. Nagel", year=1998, venue="Nature 396, 21",
         tags=["堵塞", "颗粒物质"],
         note="堵塞相变的经典短文，提出 jamming 相图。"),
    dict(title="Jamming at Zero Temperature and Zero Applied Stress: The Epitome of Disorder",
         authors="C. S. O'Hern, L. E. Silbert, A. J. Liu, S. R. Nagel", year=2003, venue="Phys. Rev. E 68, 011306",
         tags=["堵塞"],
         note="用数值确定堵塞点临界指数，颗粒统计力学的定量基石。"),
    dict(title="Memory Effects in Granular Materials",
         authors="C. Josserand, A. V. Tkachenko, D. M. Mueth, H. M. Jaeger",
         year=2000, venue="Phys. Rev. Lett. 85, 3632",
         tags=["颗粒记忆"],
         note="颗粒体系的历史依赖（记忆效应）实验证据。"),
    dict(title="Random Organization and Plastic Depinning",
         authors="D. J. Pine, J. P. Gollub, J. F. Brady, A. M. Leshansky",
         year=2005, venue="Nature 438, 997",
         tags=["颗粒", "临界"],
         note="随机组织化：循环驱动下体系自组织到临界点。"),
    dict(title="Dynamics of Viscous Fingering in a Hele-Shaw Cell",
         authors="P. G. Saffman, G. I. Taylor", year=1958, venue="Proc. R. Soc. A 245, 312",
         tags=["界面不稳定性"],
         note="Saffman-Taylor 不稳定性，界面动力学经典。"),
    dict(title="Phase Transition in the Ising Model and the Renormalization Group",
         authors="K. G. Wilson", year=1971, venue="Phys. Rev. B 4, 3174",
         tags=["重整化群", "临界"],
         note="重整化群：临界现象与普适类的统一语言。"),
    dict(title="Scaling Theory of Self-Similar Structures (renormalization in critical phenomena)",
         authors="L. P. Kadanoff", year=1966, venue="Physics 2, 263",
         tags=["标度理论"],
         note="Kadanoff 块自旋：重整化群的直觉来源。"),
    dict(title="Self-Organized Criticality: An Explanation of 1/f Noise",
         authors="P. Bak, C. Tang, K. Wiesenfeld", year=1987, venue="Phys. Rev. Lett. 59, 381",
         tags=["自组织临界"],
         note="自组织临界：系统自发走向临界态。"),
    dict(title="Theory of Stochastic Resonance",
         authors="B. McNamara, K. Wiesenfeld", year=1989, venue="Phys. Rev. A 39, 4854",
         tags=["随机共振"],
         note="噪声增强信号响应，非线性随机系统的经典结果。"),
    dict(title="Thermodynamics of Small Systems",
         authors="T. L. Hill", year=1963, venue="J. Chem. Phys. 39, 3255 / 专著",
         tags=["小系统热力学"],
         note="Hill 小系统热力学：给有限尺度体系建立非广延热力学（你在跟读的方向）。"),
    dict(title="Nano-thermodynamics: On the Minimal Length Scale of Thermodynamics",
         authors="T. L. Hill 传统与后续发展", year=2001, venue="Nano Lett. 1, 159",
         tags=["纳米热力学"],
         note="把 Hill 框架推向纳米尺度的代表性工作。"),
    dict(title="Kinetics of Phase Transition in a Finite System",
         authors="D. Reguera, J. M. Rubí, J. M. G. Vilar", year=2005, venue="J. Phys. Chem. B 109, 21502",
         tags=["有限尺度", "动力学"],
         note="有限尺度下的相变动力学与成核速率修正。"),
]


def _index_for(day=None):
    """按日期稳定选一篇（同一天永远是同一篇；隔天轮换）。"""
    day = day or dt.date.today()
    return day.toordinal() % len(CLASSICS)


def pick(day=None, offset=0):
    """取经典论文条目。

    offset=0 时按日期稳定选取（同一天同一篇）；
    offset>0 用于用户手动「换一篇」——每次点按钮 offset 递增，
    在典籍库里连续取下一篇（每天不限次数）。
    """
    day = day or dt.date.today()
    idx = (_index_for(day) + int(offset or 0)) % len(CLASSICS)
    item = dict(CLASSICS[idx])
    item['day'] = day.isoformat()
    item['index'] = idx
    item['key'] = f"{item['year']}_{item['title'][:40]}"
    return item


def pick_by_index(i):
    """按典籍库下标取条目（用于「加一篇」逐条累积）。"""
    item = dict(CLASSICS[int(i) % len(CLASSICS)])
    item['index'] = int(i) % len(CLASSICS)
    item['key'] = f"{item['year']}_{item['title'][:40]}"
    return item


def total():
    return len(CLASSICS)


# ---------------------------------------------------------------- 原文链接
# title → 原文地址。优先 DOI / arXiv 直链；老论文（1950s 前）多数没有 DOI，
# 用出版社、存档站或官方讲义页兜底。没登记到的条目由 link_of() 退回检索页。
LINK_MAP = {
    # --- 统计物理与随机过程的基础 ---
    "Equation of State Calculations by Fast Computing Machines":
        "https://doi.org/10.1063/1.1699114",
    "Simulating Physics with Computers": "https://doi.org/10.1007/BF02650179",
    "Brownian Motion in a Field of Force and the Diffusion Model of Chemical Reactions":
        "https://doi.org/10.1016/S0031-8914(40)90098-2",
    "The Fokker-Planck Equation: Methods of Solution and Applications":
        "https://doi.org/10.1007/978-3-642-61544-3",
    "Kinetics of Phase Transition in a Finite System":
        "https://doi.org/10.1021/jp052723p",
    "Phase Transition in the Ising Model and the Renormalization Group":
        "https://doi.org/10.1103/PhysRevB.4.3174",
    "Scaling Theory of Self-Similar Structures (renormalization in critical phenomena)":
        "https://doi.org/10.1080/00319106608059259",
    "Self-Organized Criticality: An Explanation of 1/f Noise":
        "https://doi.org/10.1103/PhysRevLett.59.381",
    "Theory of Stochastic Resonance": "https://doi.org/10.1103/PhysRevA.39.4854",
    "A Gallery of Fluid Motion": "https://doi.org/10.1146/annurev.fl.14.010182.000245",
    "Dynamics of Viscous Fingering in a Hele-Shaw Cell":
        "https://doi.org/10.1098/rspa.1958.0085",

    # --- 信息与热力学 ---
    "Irreversibility and Heat Generation in the Computing Process":
        "https://doi.org/10.1147/rd.53.0183",
    "Minimal Energy Cost for Thermodynamic Information Processing":
        "https://arxiv.org/abs/0909.5367",
    "Maxwell's Demon in Biochemical Signal Transduction":
        "https://arxiv.org/abs/1506.07994",
    "Thermodynamics of Small Systems": "https://doi.org/10.1063/1.1734110",
    "Nano-thermodynamics: On the Minimal Length Scale of Thermodynamics":
        "https://doi.org/10.1021/nl005518k",

    # --- 涨落定理与随机热力学 ---
    "Irreversibility and Generalized Fluctuation-Dissipation Theorem":
        "https://doi.org/10.1103/PhysRevLett.71.2401",
    "Equilibrium Information from Nonequilibrium Measurements":
        "https://arxiv.org/abs/cond-mat/9610209",
    "Entropy Production Fluctuation Theorem and the Nonequilibrium Work Relation":
        "https://arxiv.org/abs/cond-mat/9901352",
    "Entropy Production along a Stochastic Trajectory and an Integral Fluctuation Theorem":
        "https://arxiv.org/abs/cond-mat/0503686",
    "Stochastic Thermodynamics: Principles and Applications":
        "https://arxiv.org/abs/1205.4176",
    "Fluctuation Theorem for Stochastic Dynamics":
        "https://arxiv.org/abs/cond-mat/9707118",
    "Irreversibility and Fluctuation Theorem in Stationary Time Series":
        "https://arxiv.org/abs/cond-mat/0505632",
    "Thermodynamic Uncertainty Relation for Biomolecular Processes":
        "https://arxiv.org/abs/1501.05020",

    # --- 布朗马达 / 棘轮 / 分子马达 ---
    "The Feynman Lectures on Physics, Vol. I, Ch. 46 (Ratchet and Pawl)":
        "https://www.feynmanlectures.caltech.edu/I_46.html",
    "Forced Thermal Ratchets": "https://doi.org/10.1103/PhysRevLett.71.1477",
    "Modeling Molecular Motors": "https://doi.org/10.1103/RevModPhys.69.1269",
    "Brownian Motors: Noisy Transport far from Equilibrium":
        "https://arxiv.org/abs/cond-mat/0100549",

    # --- 颗粒物质 / 堵塞 / 玻璃 ---
    "Statistical Mechanics of Powder Compacts":
        "https://doi.org/10.1016/0378-4371(89)90323-3",
    "Granular Matter: A Tentative View": "https://doi.org/10.1103/RevModPhys.71.S374",
    "Jamming of Granular Matter": "https://doi.org/10.1038/24632",
    "Jamming at Zero Temperature and Zero Applied Stress: The Epitome of Disorder":
        "https://arxiv.org/abs/cond-mat/0304421",
    "Memory Effects in Granular Materials": "https://arxiv.org/abs/cond-mat/0008141",
    "Random Organization and Plastic Depinning": "https://doi.org/10.1038/nature04219",
}


# 只登记**真实论文本体页面**（出版社 DOI 页 / arXiv abs 页 / 官方讲义页）。
# 拿不到可靠论文页的条目干脆不登记 —— 界面会隐藏「原文」按钮，
# 而不是拿搜索引擎检索页凑数（点开必须是有效论文网页）。
NO_LINK_TITLES = {
    # 费曼 1959 演讲：原始站点已失效，检索到的镜像页无法确认稳定可达
    "There's Plenty of Room at the Bottom",
    # van Kampen 专著：只有出版社书页/馆藏检索页，非论文本体
    "Brownian Motion and Stochastic Theory of Irreversible Processes",
}


def link_of(item):
    """取一篇经典的论文网页地址；没有可靠地址时返回空字符串。

    调用方（小组件/网页）在拿不到地址时**隐藏「原文」按钮**。
    """
    t = item.get('title') or ''
    if t in NO_LINK_TITLES:
        return ''
    return LINK_MAP.get(t, '')
