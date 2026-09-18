import QtQuick 2.15
import QtQuick.Layouts 1.15
import org.kde.kirigami 2.20 as Kirigami
import org.kde.plasma.components 3.0 as PC3
import org.kde.plasma.core as PlasmaCore
import org.kde.plasma.plasma5support 2.0 as P5S
import org.kde.plasma.plasmoid 2.0
import "util.js" as U

PlasmoidItem {
    id: root

    // 沿用桌面壁纸底色，让面板有"透过玻璃"的感觉
    Plasmoid.backgroundHints: PlasmaCore.Types.NoBackground

    // 高度翻倍（560 → 1120）、宽度略增以适配放大后的字号
    implicitWidth: 460
    implicitHeight: 1120
    Layout.preferredWidth: 460
    Layout.preferredHeight: 1120

    // ===== 后端路径（install.sh 会替换 @DATA_DIR@）=====
    readonly property string dataDir: "@DATA_DIR@"
    readonly property string updateCmd: "@PROJECT_DIR@/update.py"
    readonly property string pythonBin: "/usr/bin/python3"

    // ===== 状态 =====
    property var profile: null
    property var papersDoc: null
    property var brief: null
    property var actionsData: null
    property int lastUpdateTs: 0
    property string tab: "brief"
    property bool busy: false
    property string busyMsg: ""

    // ⚠ Kirigami.Theme.highlightColor 在暗色主题下是**偏暗的蓝**，拿它当文字色
    // 会和半透明面板糊在一起（用户反馈"本周期看点等蓝色字体看不清"）。
    // 所以统一改成明确的亮青蓝，供所有标题/链接文字使用。
    readonly property color accent: "#6cc7ff"

    readonly property int newCount: (papersDoc && papersDoc.count) ? papersDoc.count : 0

    // ===== 数据读取 =====
    // 注意：Plasma 的 QML 里 XMLHttpRequest 读 file:// 会被安全策略拒绝，
    // 而且是静默失败（不报错，界面直接空白）。因此统一走 P5S.DataSource
    // 的 executable 引擎：用 shell 把 JSON 打出来，再在 QML 侧解析。
    // 这也是本机 researchfrontier 部件验证过的可用路径。
    property string loadErr: ""

    // 诊断日志：写到 runtime/qml_debug.log，便于在 journal 之外排查
    // （GUI 部件出错时的唯一可靠观察点；确认稳定后可留着——开销极小）
    function dbg(msg) {
        // 只走 journal（file:// 在 Plasma 的 QML 里写不出去，试过无效）。
        // 排查时看：journalctl --user -u plasma-plasmashell.service | grep researchwatch
        console.log("[researchwatch] " + msg)
    }

    function ingest(name, data) {
        var out = (data && data.stdout) ? String(data.stdout) : ""
        // 只记关键一行：数据链路是否通（排查时唯一可信判据）
        root.dbg("ingest " + name + ": " + out.length + " 字节")
        if (out.trim().length === 0) {
            return
        }
        var obj = null
        try { obj = JSON.parse(out) }
        catch (e) {
            root.loadErr = name + ": JSON 解析失败"
            root.dbg("  → JSON 解析失败: " + e)
            return
        }
        root.loadErr = ""
        if (name === "profile") {
            var gen = obj.generated || 0
            if (root.profile && gen && root.profile.generated === gen) {
                    return
            }
            // 每个数组字段都要兜底：定时任务正在更新 profile.json 时，
            // 视图侧的 .slice() / .length 一旦读到 undefined 就会抛 TypeError
            // （实测：服务运行期间部件刷新会刷一屏 "Cannot read property 'items' of undefined"）
            root.profile = {
                "generated": obj.generated || 0,
                "generated_text": obj.generated_text || "—",
                "agenda": obj.agenda || [],
                "clusters": obj.clusters || [],
                "top_terms": obj.top_terms || [],
                "top_words": obj.top_words || [],
                "journals": obj.journals || [],
                "years": obj.years || [],
                "recent_titles": obj.recent_titles || [],
                "notes": obj.notes || [],
                "library": obj.library || {"items": 0, "with_abstract": 0,
                                           "with_pdf": 0, "with_doi": 0,
                                           "recent_12y": 0, "collections": []}
            }
        } else if (name === "actions") {
            root.actionsData = {
                "likes": obj.likes || {},
                "collected": obj.collected || {},
                "translations": obj.translations || {}
            }
            root.dbg("  actions: 赞 " + Object.keys(root.actionsData.likes).length
                     + " · 收藏 " + Object.keys(root.actionsData.collected).length)
            return
        } else if (name === "papers") {
            var pgen = obj.generated || 0
            var list = obj.papers || []
            if (root.papersDoc && pgen && root.papersDoc.generated === pgen) {
                    return
            }
            var list = obj.papers || []
            var clean = []
            for (var i = 0; i < list.length; ++i) {
                var p = list[i] || {}
                clean.push({
                    "rank": p.rank || (i + 1),
                    "title": p.title || "(无标题)",
                    "author_text": p.author_text || "",
                    "authors": p.authors || [],
                    "journal": p.journal || p.source || "",
                    "date": p.date || "",
                    "doi": p.doi || "",
                    "arxiv": p.arxiv || "",
                    "url": p.url || "",
                    "pdfurl": p.pdfurl || "",
                    "citations": (p.citations === undefined ? null : p.citations),
                    "score": p.score || 0,
                    "why": p.why || [],
                    "is_preprint": !!p.is_preprint,
                    "abstract": p.abstract || "",
                    "summary": p.summary || "",
                    "summary_short": p.summary_short || p.summary || "",
                    "abstract_short": p.abstract_short || p.abstract || "",
                    "summary_model": p.summary_model || "",
                    "summary_cached": !!p.summary_cached
                })
            }
            root.papersDoc = {
                "generated": obj.generated || 0,
                "generated_text": obj.generated_text || "—",
                "window_days": obj.window_days || 0,
                "count": obj.count || clean.length,
                "papers": clean
            }
            if (obj.generated) root.lastUpdateTs = obj.generated
        } else if (name === "brief") {
            var bgen = obj.generated || 0
            if (root.brief && bgen && root.brief.generated === bgen) {
                    return
            }
            // 字段兜底：QML 里给 Label 赋 undefined 会刷一屏 "Unable to assign" 警告
            root.brief = {
                "generated": obj.generated || 0,
                "generated_text": obj.generated_text || "—",
                "elapsed_sec": obj.elapsed_sec || 0,
                "window_days": obj.window_days || 0,
                "picked_count": obj.picked_count || 0,
                "candidate_count": obj.candidate_count || 0,
                "new_count": obj.new_count || 0,
                "model_synth": obj.model_synth || "",
                "markdown": obj.markdown || "",
                "markdown_short": obj.markdown_short || obj.markdown || "",
                "error": obj.error || "",
                "classic": root.normClassic(obj.classic),
                "classic_list": (obj.classic_list || []).map(root.normClassic)
            }
            if (obj.generated) root.lastUpdateTs = obj.generated
        }
        console.log("[researchwatch] loaded " + name)
    }

    // 路径必须和上面 DataSource 的 connectedSources 完全一致！
    // 曾经这里还留着旧的 collectCmd 写法，结果 Component.onCompleted 里的
    // loadAll() 会先用旧命令把源冲成空、再装载，最终数据被覆盖成 0 篇。
    function dataPath(kind) {
        return "/bin/cat " + dataDir + "/" + kind + ".json"
    }

    function reload(kind) {
        var ds = kind === "profile" ? dsProfile
               : (kind === "papers" ? dsPapers
               : (kind === "actions" ? dsActions : dsBrief))
        var src = dataPath(kind)
        ds.disconnectSource(src)
        ds.connectSource(src)
    }

    // 归一化一篇经典（字段齐全，避免视图读到 undefined）
    function normClassic(c) {
        if (!c) return null
        return {
            "title": c.title || "", "authors": c.authors || "",
            "year": c.year || "", "venue": c.venue || "",
            "tags": c.tags || [], "note": c.note || "",
            "review": c.review || "", "url": c.url || "",
            "key": c.key || "", "cached": !!c.cached
        }
    }

    function loadAll() {
        reload("profile")
        reload("papers")
        reload("brief")
        reload("actions")
    }

    Component.onCompleted: {
        console.log("[researchwatch] data dir: " + dataDir)
        loadAll()
    }

    // 产物更新后自动重读：定时任务 06:00 跑完后最多 2 分钟就会刷上来
    // （collect.sh 有指纹比对，没变化时静默，所以这个频率不浪费）
    Timer {
        interval: 120000
        running: true
        repeat: true
        onTriggered: root.loadAll()
    }

    // cat 会保留文件原文；文件不存在时输出空串，ingest 会安全忽略。
    // 注意路径必须与 reload() 里拼出来的完全一致（踩过这个坑：数据会被冲成空）
    P5S.DataSource {
        id: dsActions
        engine: "executable"
        connectedSources: ["/bin/cat @DATA_DIR@/actions.json"]
        interval: 120000
        onNewData: function (src, data) { root.ingest("actions", data) }
    }
    P5S.DataSource {
        id: dsProfile
        engine: "executable"
        connectedSources: ["/bin/cat @PROJECT_DIR@/runtime/profile.json"]
        interval: 120000
        onNewData: function (src, data) { root.ingest("profile", data) }
    }
    P5S.DataSource {
        id: dsPapers
        engine: "executable"
        connectedSources: ["/bin/cat @PROJECT_DIR@/runtime/papers.json"]
        interval: 120000
        onNewData: function (src, data) { root.ingest("papers", data) }
    }
    P5S.DataSource {
        id: dsBrief
        engine: "executable"
        connectedSources: ["/bin/cat @PROJECT_DIR@/runtime/brief.json"]
        interval: 120000
        onNewData: function (src, data) { root.ingest("brief", data) }
    }

    // 手动更新：调用后端（会联网 + 调 DeepSeek，耗时几十秒）
    P5S.DataSource {
        id: dsUpdate
        engine: "executable"
        connectedSources: []
        onNewData: function (src, data) {
            root.busy = false
            root.busyMsg = ""
            console.log("[researchwatch] update finished")
            root.loadAll()
        }
    }

    // 打开浏览器版（日历回顾网页）。走 collect.sh open，避免在 QML 里拼长路径。
    P5S.DataSource {
        id: dsOpen
        engine: "executable"
        connectedSources: []
        onNewData: function (src, data) {
            var out = (data && data.stdout) ? String(data.stdout).trim() : ""
            console.log("[researchwatch] open → " + out)
            if (out.indexOf("MISSING") === 0) {
                root.busyMsg = "还没有生成网页版，先点 ↻ 更新一次"
            }
        }
    }

    // ===== 用户动作（翻译 / 收藏 / 点赞）=====
    // 都走 action.py（独立进程）：翻译是长任务，收藏要写 Zotero 库，
    // 点赞要落盘给抓取用 —— 放在 QML 里做不了，也不该阻塞界面。
    P5S.DataSource {
        id: dsAction
        engine: "executable"
        connectedSources: []
        onNewData: function (src, data) {
            var out = (data && data.stdout) ? String(data.stdout).trim() : ""
            console.log("[researchwatch] action → " + out)
            // 动作完成后重新读状态（顺带刷翻译进度）
            root.loadAll()
        }
    }

    readonly property string actionCmd: "@PROJECT_DIR@/action.py"
    // ⚠️ 这个属性曾经被补丁误删，导致 connectSource(undefined) 静默失败、
    // 点 🌐 图标毫无反应。QML 对 undefined 不做类型检查，所以一定要小心。
    readonly property string openCmd: "@PROJECT_DIR@/plasmoid/contents/scripts/collect.sh open"

    function runAction(op, rank) {
        var cmd = pythonBin + " " + actionCmd + " " + op + " " + rank
        console.log("[researchwatch] runAction " + op + " #" + rank)
        dsAction.connectSource(cmd)
    }

    function openBrowser() {
        console.log("[researchwatch] openBrowser → " + openCmd)
        dsOpen.connectSource(openCmd)
    }

    // 用系统浏览器打开任意 URL（经典论文的「原文」按钮用它）
    function openUrl(url) {
        if (!url) return
        console.log("[researchwatch] openUrl → " + url)
        Qt.openUrlExternally(url)
    }

    // 「全文」按钮：直接在浏览器打开这篇论文的网页。
    // 优先 DOI（出版社页面），其次 arXiv，最后抓取时的原始 url。
    function openPaper(paper) {
        if (!paper) return
        var target = ""
        if (paper.pdfurl) target = paper.pdfurl
        else if (paper.doi) target = "https://doi.org/" + paper.doi
        else if (paper.arxiv) target = "https://arxiv.org/abs/" + paper.arxiv
        else if (paper.url) target = paper.url
        if (!target) {
            console.log("[researchwatch] openPaper: 该论文没有可用链接")
            return
        }
        console.log("[researchwatch] openPaper → " + target)
        Qt.openUrlExternally(target)
    }

    function runUpdate() {
        if (root.busy) return
        root.busy = true
        root.busyMsg = "正在抓取论文并生成简报…（约 1–2 分钟）"
        var cmd = pythonBin + " " + updateCmd + " all"
        dsUpdate.connectSource(cmd)
    }

    // ===== 界面 =====
    ColumnLayout {
        anchors.fill: parent
        anchors.margins: 6
        spacing: 7

        // ---------- 顶栏 ----------
        GlassPane {
            Layout.fillWidth: true
            implicitHeight: 46
            tintStrength: 1.2
            RowLayout {
                anchors.fill: parent
                anchors.leftMargin: 12
                anchors.rightMargin: 6
                spacing: 7

                PC3.Label {
                    text: "🔭 研究前沿"
                    font.pixelSize: 18
                    font.weight: Font.DemiBold
                }
                Rectangle {
                    height: 17
                    width: agoLabel.implicitWidth + 12
                    radius: 8
                    color: Qt.rgba(Kirigami.Theme.highlightColor.r, Kirigami.Theme.highlightColor.g,
                                   Kirigami.Theme.highlightColor.b, 0.15)
                    PC3.Label {
                        id: agoLabel
                        anchors.centerIn: parent
                        text: U.ago(root.lastUpdateTs)
                        font.pixelSize: 12
                        color: Kirigami.Theme.textColor
                        opacity: 0.85
                    }
                }
                Item { Layout.fillWidth: true }

                PC3.BusyIndicator {
                    visible: root.busy
                    running: root.busy
                    Layout.preferredWidth: 18
                    Layout.preferredHeight: 18
                }
                // 浏览器版入口：放在「研究前沿 · N 分钟前」右侧的互联网图标
                // （用户要求：不要底部那一整条栏，图标就够了）
                PC3.ToolButton {
                    id: webButton
                    Layout.preferredWidth: 32
                    Layout.preferredHeight: 32
                    contentItem: Text {
                        text: "🌐"
                        font.pixelSize: 18
                        horizontalAlignment: Text.AlignHCenter
                        verticalAlignment: Text.AlignVCenter
                    }
                    background: Rectangle {
                        radius: 8
                        color: webButton.hovered
                               ? Qt.rgba(Kirigami.Theme.textColor.r,
                                         Kirigami.Theme.textColor.g,
                                         Kirigami.Theme.textColor.b, 0.14)
                               : "transparent"
                        border.width: webButton.hovered ? 1.5 : 0
                        border.color: Qt.rgba(Kirigami.Theme.textColor.r,
                                              Kirigami.Theme.textColor.g,
                                              Kirigami.Theme.textColor.b, 0.30)
                    }
                    PC3.ToolTip.text: "在浏览器打开完整版（日历回顾 · 完整简报 · 全部论文详情）"
                    PC3.ToolTip.visible: hovered
                    onClicked: root.openBrowser()
                }
            }
        }

        // ---------- 更新提示条 ----------
        Rectangle {
            Layout.fillWidth: true
            visible: root.busy
            implicitHeight: busyLabel.implicitHeight + 12
            radius: 9
            color: Qt.rgba(Kirigami.Theme.highlightColor.r, Kirigami.Theme.highlightColor.g,
                           Kirigami.Theme.highlightColor.b, 0.18)
            PC3.Label {
                id: busyLabel
                anchors.fill: parent
                anchors.margins: 6
                text: root.busyMsg
                font.pixelSize: 13
                wrapMode: Text.WordWrap
                horizontalAlignment: Text.AlignHCenter
                verticalAlignment: Text.AlignVCenter
            }
        }

        // ---------- 标签栏 ----------
        RowLayout {
            Layout.fillWidth: true
            spacing: 5
            TabButton {
                text: "前沿"
                badge: root.newCount
                active: root.tab === "brief"
                onClicked: root.tab = "brief"
            }
            TabButton {
                text: "经典"
                active: root.tab === "classic"
                onClicked: root.tab = "classic"
            }
            TabButton {
                text: "画像"
                active: root.tab === "profile"
                onClicked: root.tab = "profile"
            }
            Item { Layout.fillWidth: true }
            // 加载状态：读不到数据时明确显示，避免"界面空白但无报错"这种坑
            Rectangle {
                height: 17
                width: statusLabel.implicitWidth + 12
                radius: 8
                color: {
                    if (root.loadErr !== "") return Qt.rgba(0.94, 0.35, 0.31, 0.20)
                    if (root.papersDoc && root.profile && root.brief)
                        return Qt.rgba(0.30, 0.75, 0.45, 0.18)
                    return Qt.rgba(0.95, 0.65, 0.20, 0.18)
                }
                PC3.Label {
                    id: statusLabel
                    anchors.centerIn: parent
                    font.pixelSize: 12
                    text: {
                        if (root.loadErr !== "") return "⚠ " + root.loadErr
                        if (!root.papersDoc) return "读取中…"
                        return "✓ " + root.papersDoc.count + " 篇 · "
                             + (root.brief ? root.brief.generated_text : "无简报")
                    }
                }
            }
        }

        // ---------- 视图 ----------
        Loader {
            Layout.fillWidth: true
            Layout.fillHeight: true
            sourceComponent: {
                if (root.tab === "brief") return briefComp
                if (root.tab === "classic") return classicComp
                return profileComp
            }
        }
    }

    Component {
        id: briefComp
        BriefView {
            brief: root.brief
            papersDoc: root.papersDoc
            actions: root.actionsData
            actionCallback: root.runAction
            openPaperCallback: root.openPaper
        }
    }
    Component {
        id: classicComp
        ClassicView {
            brief: root.brief
            openUrlCallback: root.openUrl
            onNewClassic: root.runAction("newclassic", 0)
        }
    }
    Component {
        id: profileComp
        ProfileView { profile: root.profile }
    }
}
