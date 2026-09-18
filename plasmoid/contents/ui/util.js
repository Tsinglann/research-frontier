.pragma library

function fmtTime(ts) {
    if (!ts) return "—"
    var d = new Date(ts * 1000)
    return d.toLocaleDateString(Qt.locale(), Locale.ShortFormat) + " " +
           pad(d.getHours()) + ":" + pad(d.getMinutes())
}

function pad(n) { return (n < 10 ? "0" : "") + n }

function ago(ts) {
    if (!ts) return "从未更新"
    var s = Math.floor(Date.now() / 1000) - ts
    if (s < 60) return "刚刚"
    if (s < 3600) return Math.floor(s / 60) + " 分钟前"
    if (s < 86400) return Math.floor(s / 3600) + " 小时前"
    return Math.floor(s / 86400) + " 天前"
}

// 返回 QColor：既能直接赋给 color 属性，也能取 .r/.g/.b 做半透明底色
function scoreColor(s) {
    if (s >= 12) return Qt.rgba(0.88, 0.35, 0.31, 1)   // 极高相关
    if (s >= 8)  return Qt.rgba(0.94, 0.58, 0.17, 1)   // 高
    if (s >= 5)  return Qt.rgba(0.29, 0.62, 0.88, 1)   // 中
    return Qt.rgba(0.50, 0.55, 0.55, 1)                // 低
}

// 极简 markdown 解析：支持 ## 标题 / - 列表 / **加粗** / 普通段落
function parseMarkdown(md) {
    var out = []
    if (!md) return out
    var lines = String(md).split("\n")
    for (var i = 0; i < lines.length; i++) {
        var raw = lines[i]
        var l = raw.trim()
        if (l.length === 0) continue
        if (l.indexOf("### ") === 0) { out.push({ kind: "h3", text: clean(l.slice(4)) }); continue }
        if (l.indexOf("## ") === 0) { out.push({ kind: "h2", text: clean(l.slice(3)) }); continue }
        if (l.indexOf("# ") === 0) { out.push({ kind: "h2", text: clean(l.slice(2)) }); continue }
        if (l.indexOf("---") === 0) { out.push({ kind: "rule", text: "" }); continue }
        var m = l.match(/^(?:[-*+]|\d+[.、)])\s+(.*)$/)
        if (m) { out.push({ kind: "li", text: clean(m[1]) }); continue }
        out.push({ kind: "p", text: clean(l) })
    }
    return out
}

function clean(s) {
    return String(s)
        .replace(/\*\*(.+?)\*\*/g, "$1")
        .replace(/`(.+?)`/g, "$1")
        .replace(/\*(.+?)\*/g, "$1")
        .replace(/\[(.+?)\]\((.+?)\)/g, "$1")
        .trim()
}

// 3 句简介 → 行数组
function summaryLines(summary) {
    if (!summary) return []
    var parts = String(summary).split("\n")
    var out = []
    for (var i = 0; i < parts.length; i++) {
        var t = parts[i].trim()
        if (t.length === 0) continue
        if (t.indexOf("{") === 0) continue
        out.push(texToUnicode(t.replace(/^\d+[.、)]\s*/, "")))
    }
    return out
}

function firstSentence(s) {
    if (!s) return ""
    var t = String(s).replace(/\s+/g, " ").trim()
    var idx = t.search(/[。！？.!?]/)
    return idx > 0 && idx < 200 ? t.slice(0, idx + 1) : (t.length > 160 ? t.slice(0, 160) + "…" : t)
}


// ---------------------------------------------------------------- LaTeX → Unicode
// 小组件没有公式排版引擎，这里把常见 LaTeX 降级成 Unicode，保证可读。
// 网页版有完整 KaTeX，精度不受影响。
var _SYM = {
    alpha: "α", beta: "β", gamma: "γ", delta: "δ", epsilon: "ε", varepsilon: "ε",
    zeta: "ζ", eta: "η", theta: "θ", vartheta: "ϑ", iota: "ι", kappa: "κ",
    lambda: "λ", mu: "μ", nu: "ν", xi: "ξ", pi: "π", rho: "ρ", sigma: "σ",
    tau: "τ", upsilon: "υ", phi: "φ", varphi: "φ", chi: "χ", psi: "ψ", omega: "ω",
    Gamma: "Γ", Delta: "Δ", Theta: "Θ", Lambda: "Λ", Xi: "Ξ", Pi: "Π",
    Sigma: "Σ", Upsilon: "Υ", Phi: "Φ", Psi: "Ψ", Omega: "Ω",
    times: "×", cdot: "·", div: "÷", pm: "±", mp: "∓", leq: "≤", le: "≤",
    geq: "≥", ge: "≥", neq: "≠", ne: "≠", approx: "≈", sim: "∼", simeq: "≃",
    propto: "∝", equiv: "≡", ll: "≪", gg: "≫", infty: "∞", partial: "∂",
    nabla: "∇", to: "→", rightarrow: "→", leftarrow: "←", Rightarrow: "⇒",
    Leftrightarrow: "⇔", leftrightarrow: "↔", mapsto: "↦", in: "∈", notin: "∉",
    subset: "⊂", subseteq: "⊆", cup: "∪", cap: "∩", emptyset: "∅",
    sum: "Σ", prod: "Π", int: "∫", oint: "∮", sqrt: "√", angle: "∠",
    perp: "⊥", parallel: "∥", forall: "∀", exists: "∃", neg: "¬",
    land: "∧", lor: "∨", oplus: "⊕", otimes: "⊗", langle: "⟨", rangle: "⟩",
    lvert: "|", rvert: "|", lVert: "‖", rVert: "‖", hbar: "ℏ", ell: "ℓ",
    dagger: "†", star: "⋆", circ: "∘", bullet: "•", prime: "′",
    ldots: "…", cdots: "⋯", dots: "…", quad: " ", qquad: "  ",
    mathbb: "", mathcal: "", mathrm: "", mathbf: "", mathit: "",
    text: "", operatorname: "", boldsymbol: "", vec: "", hat: "", bar: "",
    left: "", right: "", big: "", Big: "", bigg: "", Bigg: ""
};

var _SUP = { "0":"⁰","1":"¹","2":"²","3":"³","4":"⁴","5":"⁵","6":"⁶","7":"⁷","8":"⁸","9":"⁹",
             "+":"⁺","-":"⁻","=":"⁼","(":"⁽",")":"⁾","n":"ⁿ","i":"ⁱ","a":"ᵃ","b":"ᵇ" };
var _SUB = { "0":"₀","1":"₁","2":"₂","3":"₃","4":"₄","5":"₅","6":"₆","7":"₇","8":"₈","9":"₉",
             "+":"₊","-":"₋","=":"₌","(":"₍",")":"₎","a":"ₐ","e":"ₑ","i":"ᵢ","j":"ⱼ",
             "k":"ₖ","l":"ₗ","m":"ₘ","n":"ₙ","o":"ₒ","p":"ₚ","r":"ᵣ","s":"ₛ","t":"ₜ",
             "u":"ᵤ","v":"ᵥ","x":"ₓ" };

function _mapSeq(s, table) {
    var out = "";
    for (var i = 0; i < s.length; ++i) {
        var ch = s.charAt(i);
        out += (table[ch] !== undefined) ? table[ch] : ch;
    }
    return out;
}

// 把一段文本里的 $...$ / \(...\) / $$...$$ 转成 Unicode 近似
function texToUnicode(input) {
    if (!input) return "";
    var t = String(input);

    // 1) 去定界符 + 处理各级括号
    t = t.replace(/\$\$([^$]+?)\$\$/g, "$1");
    t = t.replace(/\\\(([^)]+?)\\\)/g, "$1");
    t = t.replace(/\$([^$\n]+?)\$/g, "$1");

    // 2) \frac{a}{b} → (a)/(b)
    t = t.replace(/\\frac\s*\{([^{}]*)\}\s*\{([^{}]*)\}/g, "($1)/($2)");
    t = t.replace(/\\tfrac\s*\{([^{}]*)\}\s*\{([^{}]*)\}/g, "($1)/($2)");

    // 3) \sqrt{x} → √(x)
    t = t.replace(/\\sqrt\s*\{([^{}]*)\}/g, "√($1)");

    // 4) ^ 与 _（支持 {..} 与单字符）
    t = t.replace(/\^\s*\{([^{}]*)\}/g, function (m, g) { return _mapSeq(g, _SUP); });
    t = t.replace(/\^\s*(\S)/g, function (m, g) { return _mapSeq(g, _SUP); });
    t = t.replace(/_\s*\{([^{}]*)\}/g, function (m, g) { return _mapSeq(g, _SUB); });
    t = t.replace(/_\s*(\S)/g, function (m, g) { return _mapSeq(g, _SUB); });

    // 5) 命令 → 符号（长的先替，避免 \varphi 被 \phi 抢先）
    var keys = Object.keys(_SYM).sort(function (a, b) { return b.length - a.length; });
    for (var k = 0; k < keys.length; ++k) {
        var name = keys[k];
        t = t.split("\\" + name).join(_SYM[name]);
    }

    // 6) 剩下的 \{ \} \, \; 之类
    t = t.replace(/\\([{},;!:\s])/g, "$1");
    t = t.replace(/[{}]/g, "");          // 清掉残余花括号
    t = t.replace(/[ \t]{2,}/g, " ");
    return t.trim();
}
