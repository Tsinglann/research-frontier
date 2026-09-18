import QtQuick 2.15
import QtQuick.Layouts 1.15
import org.kde.kirigami 2.20 as Kirigami
import org.kde.plasma.components 3.0 as PC3
import "util.js" as U

// 经典论文回顾：每天一篇开山之作 + 简短中文解读
Flickable {
    id: view
    property var brief: null
    property var classic: brief && brief.classic ? brief.classic : null
    // 「换一篇」：每次点都在典籍库里顺延一篇（每天不限次数）
    signal newClassic()

    contentWidth: width
    contentHeight: col.implicitHeight + 8
    clip: true
    boundsBehavior: Flickable.StopAtBounds

    ColumnLayout {
        id: col
        width: view.width
        spacing: 9

        PC3.Label {
            Layout.fillWidth: true
            visible: !view.classic || !view.classic.title
            text: "今天还没有经典回顾。点 ↻ 更新，或等每天 06:00 的自动更新。"
            font.pixelSize: 13
            opacity: 0.7
            wrapMode: Text.WordWrap
            horizontalAlignment: Text.AlignHCenter
        }

        GlassPane {
            Layout.fillWidth: true
            visible: !!(view.classic && view.classic.title)
            implicitHeight: body.implicitHeight + 26
            tintStrength: 1.1

            ColumnLayout {
                id: body
                anchors.fill: parent
                anchors.margins: 14
                spacing: 9

                RowLayout {
                    Layout.fillWidth: true
                    spacing: 8
                    PC3.Button {
                        text: "🎲 换一篇"
                        font.pixelSize: 12
                        implicitHeight: 30
                        PC3.ToolTip.text: "在典籍库里顺延下一篇（每天不限次数）"
                        PC3.ToolTip.visible: hovered
                        onClicked: view.newClassic()
                    }
                    Rectangle {
                        height: 24
                        width: yl.implicitWidth + 16
                        radius: 12
                        color: Qt.rgba(0.96, 0.65, 0.14, 0.22)
                        PC3.Label {
                            id: yl
                            anchors.centerIn: parent
                            text: view.classic ? ("" + view.classic.year) : ""
                            font.pixelSize: 14
                            font.weight: Font.DemiBold
                            color: "#f5a623"
                        }
                    }
                    Item { Layout.fillWidth: true }
                    PC3.Label {
                        visible: !!(view.classic && view.classic.cached)
                        text: "缓存"
                        font.pixelSize: 11
                        opacity: 0.4
                    }
                }

                PC3.Label {
                    Layout.fillWidth: true
                    text: view.classic ? view.classic.title : ""
                    font.pixelSize: 18
                    font.weight: Font.DemiBold
                    wrapMode: Text.WordWrap
                    lineHeight: 1.25
                }

                PC3.Label {
                    Layout.fillWidth: true
                    text: view.classic ? ((view.classic.authors || "") + "\n" + (view.classic.venue || "")) : ""
                    font.pixelSize: 12
                    opacity: 0.66
                    wrapMode: Text.WordWrap
                    lineHeight: 1.3
                }

                // 领域标签
                Flow {
                    Layout.fillWidth: true
                    spacing: 6
                    visible: !!(view.classic && view.classic.tags && view.classic.tags.length > 0)
                    Repeater {
                        model: view.classic ? view.classic.tags : []
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
                                font.pixelSize: 12
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
                    text: view.classic ? (view.classic.note || "") : ""
                    font.pixelSize: 13
                    opacity: 0.8
                    wrapMode: Text.WordWrap
                    lineHeight: 1.35
                }

                Repeater {
                    model: view.classic ? U.summaryLines(view.classic.review) : []
                    delegate: RowLayout {
                        Layout.fillWidth: true
                        spacing: 7
                        PC3.Label {
                            text: "·"
                            font.pixelSize: 15
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
                    Layout.topMargin: 2
                    text: "完整回顾与历史日历见浏览器版 →"
                    font.pixelSize: 12
                    opacity: 0.5
                }
            }
        }
    }
}
