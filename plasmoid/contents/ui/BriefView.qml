import QtQuick 2.15
import QtQuick.Layouts 1.15
import org.kde.kirigami 2.20 as Kirigami
import org.kde.plasma.components 3.0 as PC3
import "util.js" as U

// 前沿视图 = 简报（可点击展开）+ 入选论文卡片
Flickable {
    id: view
    property var brief: null
    property var papersDoc: null
    property var actions: null
    property var papers: papersDoc && papersDoc.papers ? papersDoc.papers : []
    // main.qml 注入：function(op, rank)
    property var actionCallback: null
    // main.qml 注入：function(paper)
    property var openPaperCallback: null
    // 简报是否展开（点卡片切换）
    property bool briefExpanded: false

    readonly property string briefMd: {
        if (!brief) return ""
        if (briefExpanded) return brief.markdown || brief.markdown_short || ""
        return brief.markdown_short || brief.markdown || ""
    }
    property var blocks: briefMd ? U.parseMarkdown(briefMd) : []

    function pkey(p) {
        if (!p) return ""
        return String(p.doi || p.arxiv || p.title || "").toLowerCase().slice(0, 120)
    }
    function isLiked(p) {
        if (!actions || !actions.likes) return false
        var k = pkey(p)
        return !!(k && actions.likes[k] !== undefined)
    }
    function isCollected(p) {
        if (!actions || !actions.collected) return false
        var k = pkey(p)
        return !!(k && actions.collected[k] !== undefined)
    }
    function actionMsg(p) {
        if (!actions || !actions.translations) return ""
        var t = actions.translations[pkey(p)]
        if (!t) return ""
        if (t.state === "running") return t.msg || "翻译准备中…"
        if (t.state === "ready") return "翻译项目已建好"
        if (t.state === "queued") return "已排队"
        if (t.state === "error") return "翻译失败"
        return ""
    }

    contentWidth: width
    contentHeight: col.implicitHeight + 10
    clip: true
    boundsBehavior: Flickable.StopAtBounds

    ColumnLayout {
        id: col
        width: view.width
        spacing: 9

        // ===== 头部统计 =====
        GlassPane {
            Layout.fillWidth: true
            implicitHeight: 74
            RowLayout {
                anchors.fill: parent
                anchors.margins: 13
                spacing: 16
                ColumnLayout {
                    spacing: 1
                    PC3.Label {
                        text: (view.brief && view.brief.picked_count !== undefined)
                              ? view.brief.picked_count : "—"
                        font.pixelSize: 24
                        font.weight: Font.DemiBold
                        color: root.accent
                    }
                    PC3.Label { text: "入选论文"; font.pixelSize: 11; opacity: 0.7 }
                }
                ColumnLayout {
                    spacing: 1
                    PC3.Label {
                        text: (view.brief && view.brief.candidate_count !== undefined)
                              ? view.brief.candidate_count : "—"
                        font.pixelSize: 24
                        font.weight: Font.DemiBold
                        opacity: 0.85
                    }
                    PC3.Label { text: "抓取候选"; font.pixelSize: 11; opacity: 0.7 }
                }
                ColumnLayout {
                    spacing: 1
                    PC3.Label {
                        text: (view.brief && view.brief.window_days !== undefined)
                              ? (view.brief.window_days + " 天") : "—"
                        font.pixelSize: 24
                        font.weight: Font.DemiBold
                        opacity: 0.85
                    }
                    PC3.Label { text: "时间窗口"; font.pixelSize: 11; opacity: 0.7 }
                }
                Item { Layout.fillWidth: true }
                ColumnLayout {
                    spacing: 1
                    PC3.Label {
                        Layout.alignment: Qt.AlignRight
                        text: (view.brief && view.brief.generated_text)
                              ? view.brief.generated_text : "未生成"
                        font.pixelSize: 12
                        font.family: "Noto Sans Mono"
                        opacity: 0.85
                    }
                    PC3.Label {
                        Layout.alignment: Qt.AlignRight
                        text: (view.brief && view.brief.elapsed_sec !== undefined)
                              ? ("用时 " + view.brief.elapsed_sec + "s · "
                                 + (view.brief.model_synth || "")) : ""
                        font.pixelSize: 10
                        opacity: 0.55
                    }
                }
            }
        }

        // ===== 生成失败提示 =====
        GlassPane {
            Layout.fillWidth: true
            implicitHeight: errCol.implicitHeight + 22
            visible: !!(view.brief && view.brief.error && view.brief.error.length > 0)
            ColumnLayout {
                id: errCol
                anchors.fill: parent
                anchors.margins: 12
                PC3.Label { text: "⚠ 综合简报生成失败"; font.pixelSize: 13; font.weight: Font.DemiBold }
                PC3.Label {
                    Layout.fillWidth: true
                    text: (view.brief && view.brief.error) ? view.brief.error : ""
                    font.pixelSize: 12
                    wrapMode: Text.WordWrap
                    opacity: 0.8
                }
            }
        }

        // ===== 简报卡片（可点击展开）=====
        GlassPane {
            id: briefCard
            Layout.fillWidth: true
            implicitHeight: briefCol.implicitHeight + 26
            tintStrength: view.briefExpanded ? 1.15 : 1.0

            ColumnLayout {
                id: briefCol
                anchors.fill: parent
                anchors.margins: 14
                spacing: 6

                // 点击提示行
                RowLayout {
                    Layout.fillWidth: true
                    spacing: 7
                    PC3.Label {
                        text: view.briefExpanded ? "▴ 收起" : "▾ 点击展开完整简报"
                        font.pixelSize: 12
                        font.weight: Font.DemiBold
                        color: root.accent
                    }
                    PC3.Label {
                        Layout.fillWidth: true
                        text: view.briefExpanded
                              ? "趋势判断 · 完整看点 · 可切入的问题"
                              : "当前只显示本周期看点；点开看趋势判断与全文"
                        font.pixelSize: 11
                        opacity: 0.55
                        elide: Text.ElideRight
                    }
                }

                Repeater {
                    model: view.blocks
                    delegate: Loader {
                        Layout.fillWidth: true
                        property var blk: modelData
                        sourceComponent: {
                            if (blk.kind === "h2") return h2Comp
                            if (blk.kind === "h3") return h3Comp
                            if (blk.kind === "li") return liComp
                            if (blk.kind === "rule") return ruleComp
                            return pComp
                        }
                    }
                }

                PC3.Label {
                    Layout.fillWidth: true
                    visible: !view.briefExpanded
                    text: "▸ 更多内容见顶栏 🌐 浏览器版（日历回顾 · 历史对比）"
                    font.pixelSize: 11
                    opacity: 0.5
                    wrapMode: Text.WordWrap
                    horizontalAlignment: Text.AlignHCenter
                }
            }

            // 整卡可点：展开/收起
            MouseArea {
                anchors.fill: parent
                cursorShape: Qt.PointingHandCursor
                onClicked: view.briefExpanded = !view.briefExpanded
            }
        }

        // ===== 入选论文（并入简报下方）=====
        PC3.Label {
            Layout.fillWidth: true
            Layout.topMargin: 3
            visible: view.papers.length > 0
            text: "📄 入选论文 · " + view.papers.length + " 篇"
            font.pixelSize: 14
            font.weight: Font.DemiBold
            color: root.accent
        }

        Repeater {
            model: view.papers
            delegate: PaperCard {
                Layout.fillWidth: true
                paper: modelData
                liked: view.isLiked(modelData)
                collected: view.isCollected(modelData)
                actionMsg: view.actionMsg(modelData)
                actionCallback: view.actionCallback
                openPaperCallback: view.openPaperCallback
            }
        }

        PC3.Label {
            Layout.fillWidth: true
            visible: view.papers.length === 0
            text: "还没有论文数据。等每周自动更新，或用命令行 update.py all --force。"
            font.pixelSize: 12
            opacity: 0.65
            wrapMode: Text.WordWrap
            horizontalAlignment: Text.AlignHCenter
        }
    }

    Component {
        id: h2Comp
        RowLayout {
            spacing: 7
            Rectangle { width: 3; height: 15; radius: 2; color: root.accent }
            PC3.Label {
                text: U.texToUnicode(blk.text)
                font.pixelSize: 15
                font.weight: Font.DemiBold
                color: root.accent
            }
            Item { Layout.fillWidth: true }
        }
    }
    Component {
        id: h3Comp
        PC3.Label {
            text: U.texToUnicode(blk.text)
            font.pixelSize: 13
            font.weight: Font.DemiBold
            opacity: 0.94
        }
    }
    Component {
        id: liComp
        RowLayout {
            spacing: 7
            PC3.Label {
                text: "▸"
                font.pixelSize: 12
                color: root.accent
                Layout.alignment: Qt.AlignTop
            }
            PC3.Label {
                Layout.fillWidth: true
                text: blk.text
                font.pixelSize: 13
                lineHeight: 1.35
                wrapMode: Text.WordWrap
                opacity: 0.94
            }
        }
    }
    Component {
        id: pComp
        PC3.Label {
            Layout.fillWidth: true
            text: U.texToUnicode(blk.text)
            font.pixelSize: 13
            lineHeight: 1.35
            wrapMode: Text.WordWrap
            opacity: 0.9
        }
    }
    Component {
        id: ruleComp
        Rectangle {
            Layout.fillWidth: true
            Layout.topMargin: 3
            height: 1
            color: Qt.rgba(Kirigami.Theme.textColor.r, Kirigami.Theme.textColor.g,
                           Kirigami.Theme.textColor.b, 0.14)
        }
    }
}
