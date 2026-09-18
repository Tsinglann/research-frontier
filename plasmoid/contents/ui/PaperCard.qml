import QtQuick 2.15
import QtQuick.Layouts 1.15
import org.kde.kirigami 2.20 as Kirigami
import org.kde.plasma.components 3.0 as PC3
import "util.js" as U

GlassPane {
    id: card
    property var paper: null
    property bool expanded: false
    // 动作状态（由 main.qml 注入）
    property bool liked: false
    property bool collected: false
    property string actionMsg: ""
    property bool actionOk: true
    // 动作回调：main.qml 注入 function(op, rank)
    property var actionCallback: null
    // 打开原文回调：main.qml 注入 function(paper)
    property var openPaperCallback: null
    implicitHeight: body.implicitHeight + actionBarHeight + 18
    tintStrength: card.expanded ? 1.15 : 0.95

    // 按钮栏占用的高度（正文必须让出这块，否则文字会压在按钮下面）
    readonly property int actionBarHeight: 44

    ColumnLayout {
        id: body
        anchors.left: parent.left
        anchors.right: parent.right
        anchors.top: parent.top
        anchors.bottom: parent.bottom
        anchors.leftMargin: 12
        anchors.rightMargin: 12
        anchors.topMargin: 12
        anchors.bottomMargin: card.actionBarHeight + 4
        spacing: 6

        // 标题行
        RowLayout {
            Layout.fillWidth: true
            spacing: 7
            Rectangle {
                width: 22; height: 22; radius: 6
                color: Qt.rgba(U.scoreColor(card.paper ? card.paper.score : 0).r,
                               U.scoreColor(card.paper ? card.paper.score : 0).g,
                               U.scoreColor(card.paper ? card.paper.score : 0).b, 0.20)
                PC3.Label {
                    anchors.centerIn: parent
                    text: card.paper ? card.paper.rank : ""
                    font.pixelSize: 14
                    font.weight: Font.DemiBold
                    color: U.scoreColor(card.paper ? card.paper.score : 0)
                }
            }
            PC3.Label {
                Layout.fillWidth: true
                text: card.paper ? U.texToUnicode(card.paper.title) : ""
                font.pixelSize: 15
                font.weight: Font.DemiBold
                wrapMode: Text.WordWrap
                maximumLineCount: card.expanded ? 6 : 2
                elide: Text.ElideRight
                lineHeight: 1.2
            }
            PC3.Label {
                text: card.expanded ? "▴" : "▾"
                font.pixelSize: 13
                opacity: 0.5
            }
        }

        // 元信息
        RowLayout {
            Layout.fillWidth: true
            Layout.leftMargin: 29
            spacing: 6
            PC3.Label {
                Layout.fillWidth: true
                text: (card.paper ? card.paper.author_text : "") + " — "
                      + (card.paper ? card.paper.journal : "")
                font.pixelSize: 12
                opacity: 0.62
                elide: Text.ElideRight
            }
            Rectangle {
                height: 15
                width: dateText.implicitWidth + 10
                radius: 7
                color: Qt.rgba(1,1,1,0.06)
                PC3.Label {
                    id: dateText
                    anchors.centerIn: parent
                    text: card.paper ? card.paper.date : ""
                    font.pixelSize: 11
                    font.family: "Noto Sans Mono"
                    opacity: 0.72
                }
            }
            Rectangle {
                height: 15
                width: typeText.implicitWidth + 10
                radius: 7
                visible: card.paper && card.paper.is_preprint
                color: Qt.rgba(0.95, 0.60, 0.20, 0.16)
                PC3.Label {
                    id: typeText
                    anchors.centerIn: parent
                    text: "预印本"
                    font.pixelSize: 11
                    color: "#f0932b"
                }
            }
        }

        // 命中方向
        RowLayout {
            Layout.fillWidth: true
            Layout.leftMargin: 29
            visible: !!(card.paper && card.paper.why && card.paper.why.length > 0)
            spacing: 4
            PC3.Label {
                text: "命中 " + (card.paper ? card.paper.why.slice(0, 4).join(" · ") : "")
                font.pixelSize: 11
                opacity: 0.5
                elide: Text.ElideRight
                Layout.fillWidth: true
            }
            PC3.Label {
                text: card.paper ? ("★ " + card.paper.score) : ""
                font.pixelSize: 11
                font.family: "Noto Sans Mono"
                color: U.scoreColor(card.paper ? card.paper.score : 0)
                opacity: 0.85
            }
            PC3.Label {
                visible: card.paper && card.paper.citations !== null
                      && card.paper.citations !== undefined
                text: (card.paper && card.paper.citations !== null && card.paper.citations !== undefined)
                      ? ("引用 " + card.paper.citations) : ""
                font.pixelSize: 11
                font.family: "Noto Sans Mono"
                opacity: 0.45
            }
        }

        // 中文简介
        ColumnLayout {
            Layout.fillWidth: true
            Layout.leftMargin: 29
            Layout.topMargin: 1
            visible: !!(card.paper && (card.paper.summary_short || card.paper.summary))
            spacing: 3
            Repeater {
                model: card.paper ? U.summaryLines(card.paper.summary_short || card.paper.summary) : []
                delegate: RowLayout {
                    Layout.fillWidth: true
                    spacing: 5
                    PC3.Label {
                        text: "·"
                        font.pixelSize: 14
                        color: root.accent
                        Layout.alignment: Qt.AlignTop
                    }
                    PC3.Label {
                        Layout.fillWidth: true
                        text: modelData
                        font.pixelSize: 13
                        lineHeight: 1.26
                        wrapMode: Text.WordWrap
                        opacity: 0.9
                    }
                }
            }
        }

        // 展开后的原文摘要 + 链接
        ColumnLayout {
            Layout.fillWidth: true
            Layout.leftMargin: 29
            visible: card.expanded
            spacing: 4
            Rectangle {
                Layout.fillWidth: true
                height: 1
                color: Qt.rgba(Kirigami.Theme.textColor.r, Kirigami.Theme.textColor.g,
                               Kirigami.Theme.textColor.b, 0.10)
            }
            PC3.Label {
                Layout.fillWidth: true
                text: card.paper ? U.texToUnicode(card.paper.abstract_short || card.paper.abstract) : ""
                font.pixelSize: 12
                lineHeight: 1.24
                wrapMode: Text.WordWrap
                opacity: 0.62
                maximumLineCount: 6
                elide: Text.ElideRight
            }
            RowLayout {
                Layout.fillWidth: true
                spacing: 10
                Repeater {
                    model: {
                        var p = card.paper
                        if (!p) return []
                        var out = []
                        if (p.arxiv) out.push({ t: "arXiv:" + p.arxiv, u: "https://arxiv.org/abs/" + p.arxiv })
                        if (p.doi) out.push({ t: "DOI", u: "https://doi.org/" + p.doi })
                        if (p.pdfurl) out.push({ t: "PDF", u: p.pdfurl })
                        if (out.length === 0 && p.url) out.push({ t: "原文", u: p.url })
                        return out
                    }
                    delegate: PC3.Label {
                        text: modelData.t
                        font.pixelSize: 12
                        color: Kirigami.Theme.linkColor
                        font.underline: linkMouse.containsMouse
                        MouseArea {
                            id: linkMouse
                            anchors.fill: parent
                            hoverEnabled: true
                            cursorShape: Qt.PointingHandCursor
                            onClicked: Qt.openUrlExternally(modelData.u)
                        }
                    }
                }
        Item { Layout.fillWidth: true }
                PC3.Label {
                    text: "完整简介见浏览器版"
                    font.pixelSize: 11
                    opacity: 0.42
                }
            }
        }
    }

    // 按钮栏顶部的分隔线：让"操作区"和"内容区"在视觉上分开
    Rectangle {
        id: actionSeparator
        anchors.left: parent.left
        anchors.right: parent.right
        anchors.bottom: actionBar.top
        anchors.leftMargin: 12
        anchors.rightMargin: 12
        anchors.bottomMargin: 5
        height: 1
        color: Qt.rgba(Kirigami.Theme.textColor.r, Kirigami.Theme.textColor.g,
                       Kirigami.Theme.textColor.b, 0.18)
    }

    // ===== 操作按钮：翻译 / 收藏 / 点赞 =====
    RowLayout {
        id: actionBar
        anchors.left: parent.left
        anchors.right: parent.right
        anchors.bottom: parent.bottom
        anchors.leftMargin: 12
        anchors.rightMargin: 10
        anchors.bottomMargin: 8
        anchors.topMargin: 6
        spacing: 8

        PC3.Button {
            text: "📖 翻译"
            font.pixelSize: 12
            implicitHeight: 30
            PC3.ToolTip.text: "下载原文并建立翻译项目（后台进行）"
            PC3.ToolTip.visible: hovered
            onClicked: if (card.actionCallback) card.actionCallback("translate", card.paper.rank)
        }
        PC3.Button {
            text: card.collected ? "★ 已收藏" : "☆ 收藏"
            font.pixelSize: 12
            implicitHeight: 30
            PC3.ToolTip.text: "加入 Zotero「研究前沿app收藏」分类"
            PC3.ToolTip.visible: hovered
            onClicked: if (card.actionCallback)
                           card.actionCallback(card.collected ? "uncollect" : "collect",
                                               card.paper.rank)
        }
        PC3.Button {
            text: card.liked ? "👍 已赞" : "👍 点赞"
            font.pixelSize: 12
            implicitHeight: 30
            PC3.ToolTip.text: "告诉抓取器这类论文你感兴趣，会影响后续排序"
            PC3.ToolTip.visible: hovered
            onClicked: if (card.actionCallback)
                           card.actionCallback(card.liked ? "unlike" : "like", card.paper.rank)
        }
        PC3.Button {
            text: "🔗 全文"
            font.pixelSize: 12
            implicitHeight: 30
            PC3.ToolTip.text: "在浏览器打开这篇论文（优先 PDF / DOI / arXiv）"
            PC3.ToolTip.visible: hovered
            onClicked: if (card.openPaperCallback) card.openPaperCallback(card.paper)
        }
        Item { Layout.fillWidth: true }
        PC3.Label {
            visible: card.actionMsg !== ""
            text: card.actionMsg
            font.pixelSize: 11
            color: card.actionOk ? Kirigami.Theme.positiveTextColor : "#f5a623"
            elide: Text.ElideRight
            Layout.maximumWidth: 170
        }
    }

    // 只覆盖正文区域：点正文展开/收起，点按钮不触发
    MouseArea {
        anchors.left: parent.left
        anchors.right: parent.right
        anchors.top: parent.top
        anchors.bottom: actionSeparator.top
        acceptedButtons: Qt.LeftButton
        cursorShape: Qt.PointingHandCursor
        onClicked: card.expanded = !card.expanded
    }
}
