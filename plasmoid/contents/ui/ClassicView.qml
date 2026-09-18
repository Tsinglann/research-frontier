import QtQuick 2.15
import QtQuick.Layouts 1.15
import org.kde.kirigami 2.20 as Kirigami
import org.kde.plasma.components 3.0 as PC3
import "util.js" as U

// 经典论文回顾：当天**累积**的经典列表（点「加一篇」会越来越长），
// 每篇都带「原文」按钮跳到论文网页。
Flickable {
    id: view
    property var brief: null
    // 当天累积列表；后端没给 classic_list 时退回单篇 classic（兼容旧数据）
    property var classics: {
        if (brief && brief.classic_list && brief.classic_list.length > 0)
            return brief.classic_list
        return (brief && brief.classic) ? [brief.classic] : []
    }
    // 回调由 main.qml 注入
    property var openUrlCallback: null

    contentWidth: width
    contentHeight: col.implicitHeight + 10
    clip: true
    boundsBehavior: Flickable.StopAtBounds

    ColumnLayout {
        id: col
        width: view.width
        spacing: 10

        // 头部：篇数 + 「加一篇」
        RowLayout {
            Layout.fillWidth: true
            spacing: 8
            PC3.Label {
                text: "📜 经典回顾 · 已累积 " + view.classics.length + " 篇"
                font.pixelSize: 14
                font.weight: Font.DemiBold
                color: root.accent
            }
            Item { Layout.fillWidth: true }
            PC3.Button {
                text: "🎲 加一篇"
                font.pixelSize: 12
                implicitHeight: 30
                PC3.ToolTip.text: "再添加一篇开山之作（累积，不替换；每天不限次数）"
                PC3.ToolTip.visible: hovered
                onClicked: view.newClassic()
            }
        }

        PC3.Label {
            Layout.fillWidth: true
            visible: view.classics.length === 0
            text: "还没有经典回顾。等每天 06:00 更新，或点上面的「加一篇」。"
            font.pixelSize: 12
            opacity: 0.7
            wrapMode: Text.WordWrap
            horizontalAlignment: Text.AlignHCenter
        }

        Repeater {
            model: view.classics
            delegate: GlassPane {
                Layout.fillWidth: true
                implicitHeight: itemBody.implicitHeight + 26
                tintStrength: 1.05

                ColumnLayout {
                    id: itemBody
                    anchors.fill: parent
                    anchors.margins: 14
                    spacing: 8

                    RowLayout {
                        Layout.fillWidth: true
                        spacing: 8
                        Rectangle {
                            height: 24
                            width: yl.implicitWidth + 16
                            radius: 12
                            color: Qt.rgba(0.96, 0.65, 0.14, 0.22)
                            PC3.Label {
                                id: yl
                                anchors.centerIn: parent
                                text: "" + (modelData.year || "")
                                font.pixelSize: 13
                                font.weight: Font.DemiBold
                                color: "#f5a623"
                            }
                        }
                        PC3.Label {
                            text: (index + 1) + " / " + view.classics.length
                            font.pixelSize: 11
                            opacity: 0.45
                        }
                        Item { Layout.fillWidth: true }
                        PC3.Button {
                            text: "🔗 原文"
                            font.pixelSize: 12
                            implicitHeight: 30
                            PC3.ToolTip.text: "在浏览器打开这篇经典论文"
                            PC3.ToolTip.visible: hovered
                            onClicked: if (view.openUrlCallback)
                                           view.openUrlCallback(modelData.url)
                        }
                    }

                    PC3.Label {
                        Layout.fillWidth: true
                        text: U.texToUnicode(modelData.title || "")
                        font.pixelSize: 16
                        font.weight: Font.DemiBold
                        wrapMode: Text.WordWrap
                        lineHeight: 1.25
                    }

                    PC3.Label {
                        Layout.fillWidth: true
                        text: (modelData.authors || "") + "\n" + (modelData.venue || "")
                        font.pixelSize: 12
                        opacity: 0.66
                        wrapMode: Text.WordWrap
                        lineHeight: 1.3
                    }

                    Flow {
                        Layout.fillWidth: true
                        spacing: 6
                        visible: !!(modelData.tags && modelData.tags.length > 0)
                        Repeater {
                            model: modelData.tags || []
                            delegate: Rectangle {
                                height: 21
                                width: tagText.implicitWidth + 14
                                radius: 10
                                color: Qt.rgba(1, 1, 1, 0.07)
                                border.width: 1
                                border.color: Qt.rgba(1, 1, 1, 0.13)
                                PC3.Label {
                                    id: tagText
                                    anchors.centerIn: parent
                                    text: modelData
                                    font.pixelSize: 11
                                    opacity: 0.8
                                }
                            }
                        }
                    }

                    Rectangle {
                        Layout.fillWidth: true
                        height: 1
                        color: Qt.rgba(Kirigami.Theme.textColor.r, Kirigami.Theme.textColor.g,
                                       Kirigami.Theme.textColor.b, 0.14)
                    }

                    PC3.Label {
                        Layout.fillWidth: true
                        text: modelData.note || ""
                        font.pixelSize: 12
                        opacity: 0.8
                        wrapMode: Text.WordWrap
                        lineHeight: 1.35
                    }

                    Repeater {
                        model: U.summaryLines(modelData.review)
                        delegate: RowLayout {
                            Layout.fillWidth: true
                            spacing: 7
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
                                lineHeight: 1.4
                                wrapMode: Text.WordWrap
                                opacity: 0.92
                            }
                        }
                    }

                    PC3.Label {
                        Layout.fillWidth: true
                        visible: !modelData.review
                        text: "（这篇的回顾还没生成，点「加一篇」后会自动补上）"
                        font.pixelSize: 11
                        opacity: 0.5
                    }
                }
            }
        }

        PC3.Label {
            Layout.fillWidth: true
            visible: view.classics.length > 0
            text: "▸ 完整简报与历史日历见顶栏 🌐 浏览器版"
            font.pixelSize: 11
            opacity: 0.5
            wrapMode: Text.WordWrap
            horizontalAlignment: Text.AlignHCenter
        }
    }

    // 「加一篇」信号
    signal newClassic()
}
