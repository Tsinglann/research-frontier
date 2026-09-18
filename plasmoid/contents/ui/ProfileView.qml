import QtQuick 2.15
import QtQuick.Layouts 1.15
import org.kde.kirigami 2.20 as Kirigami
import org.kde.plasma.components 3.0 as PC3
import "util.js" as U

Flickable {
    id: view
    property var profile: null

    contentWidth: width
    contentHeight: col.implicitHeight + 8
    clip: true
    boundsBehavior: Flickable.StopAtBounds

    function reload() { /* 由 main.qml 赋值 profile 即可 */ }

    ColumnLayout {
        id: col
        width: view.width
        spacing: 8

        // ===== 研究纲领 =====
        GlassPane {
            Layout.fillWidth: true
            implicitHeight: agendaCol.implicitHeight + 22
            ColumnLayout {
                id: agendaCol
                anchors.fill: parent
                anchors.margins: 11
                spacing: 7
                RowLayout {
                    Layout.fillWidth: true
                    PC3.Label {
                        text: "🧭 研究纲领"
                        font.pixelSize: 15
                        font.weight: Font.DemiBold
                    }
                    Item { Layout.fillWidth: true }
                    PC3.Label {
                        text: view.profile ? (view.profile.library.items + " 篇文献") : ""
                        font.pixelSize: 13
                        opacity: 0.6
                    }
                }
                Flow {
                    Layout.fillWidth: true
                    spacing: 5
                    Repeater {
                        model: view.profile ? view.profile.agenda : []
                        delegate: Rectangle {
                            height: 20
                            width: tagText.implicitWidth + 14
                            radius: 10
                            color: Qt.rgba(Kirigami.Theme.highlightColor.r,
                                           Kirigami.Theme.highlightColor.g,
                                           Kirigami.Theme.highlightColor.b, 0.16)
                            border.width: 1
                            border.color: Qt.rgba(Kirigami.Theme.highlightColor.r,
                                                  Kirigami.Theme.highlightColor.g,
                                                  Kirigami.Theme.highlightColor.b, 0.34)
                            PC3.Label {
                                id: tagText
                                anchors.centerIn: parent
                                text: modelData
                                font.pixelSize: 13
                                color: Kirigami.Theme.textColor
                            }
                        }
                    }
                }
                PC3.Label {
                    Layout.fillWidth: true
                    visible: !!(view.profile && view.profile.recent_titles && view.profile.recent_titles.length > 0)
                    text: "近期在追：" + (view.profile ? U.firstSentence(view.profile.recent_titles[0]) : "")
                    font.pixelSize: 12
                    opacity: 0.55
                    wrapMode: Text.WordWrap
                    maximumLineCount: 2
                    elide: Text.ElideRight
                }
            }
        }

        // ===== 主题簇分布 =====
        GlassPane {
            Layout.fillWidth: true
            implicitHeight: clusterCol.implicitHeight + 22
            ColumnLayout {
                id: clusterCol
                anchors.fill: parent
                anchors.margins: 11
                spacing: 6
                PC3.Label { text: "📊 主题分布"; font.pixelSize: 12; font.weight: Font.DemiBold }
                Repeater {
                    model: view.profile ? view.profile.clusters : []
                    delegate: BarRow {
                        Layout.fillWidth: true
                        label: modelData.name
                        value: modelData.count
                        maximum: (view.profile?.clusters?.length > 0)
                                 ? view.profile.clusters[0].count : 1
                        valueText: modelData.pct + "%"
                        barColor: Qt.rgba(0.30, 0.62, 0.88, 0.85)
                    }
                }
            }
        }

        // ===== 核心术语 =====
        GlassPane {
            Layout.fillWidth: true
            implicitHeight: termsCol.implicitHeight + 22
            ColumnLayout {
                id: termsCol
                anchors.fill: parent
                anchors.margins: 11
                spacing: 6
                PC3.Label { text: "🔬 核心术语"; font.pixelSize: 12; font.weight: Font.DemiBold }
                Flow {
                    Layout.fillWidth: true
                    spacing: 5
                    Repeater {
                        model: view.profile ? view.profile.top_terms.slice(0, 18) : []
                        delegate: Rectangle {
                            height: 19
                            width: tText.implicitWidth + 12
                            radius: 9
                            color: Qt.rgba(U.scoreColor(modelData.score * 0.35).r,
                                           U.scoreColor(modelData.score * 0.35).g,
                                           U.scoreColor(modelData.score * 0.35).b, 0.14)
                            PC3.Label {
                                id: tText
                                anchors.centerIn: parent
                                text: modelData.term
                                font.pixelSize: 13
                                opacity: 0.9
                            }
                        }
                    }
                }
            }
        }

        // ===== 常读期刊 =====
        GlassPane {
            Layout.fillWidth: true
            implicitHeight: journalCol.implicitHeight + 22
            ColumnLayout {
                id: journalCol
                anchors.fill: parent
                anchors.margins: 11
                spacing: 6
                PC3.Label { text: "📚 常读期刊"; font.pixelSize: 12; font.weight: Font.DemiBold }
                Repeater {
                    model: view.profile ? view.profile.journals.slice(0, 10) : []
                    delegate: BarRow {
                        Layout.fillWidth: true
                        label: modelData.name
                        value: modelData.count
                        maximum: (view.profile?.journals?.length > 0)
                                 ? view.profile.journals[0].count : 1
                        barColor: Qt.rgba(0.36, 0.76, 0.53, 0.8)
                    }
                }
            }
        }

        // ===== 跟进中的笔记 =====
        GlassPane {
            Layout.fillWidth: true
            implicitHeight: notesCol.implicitHeight + 22
            visible: !!(view.profile && view.profile.notes && view.profile.notes.length > 0)
            ColumnLayout {
                id: notesCol
                anchors.fill: parent
                anchors.margins: 11
                spacing: 5
                RowLayout {
                    Layout.fillWidth: true
                    PC3.Label { text: "📝 跟进中的笔记"; font.pixelSize: 12; font.weight: Font.DemiBold }
                    Item { Layout.fillWidth: true }
                    PC3.Label {
                        text: (view.profile ? view.profile.notes.length : 0) + " 篇"
                        font.pixelSize: 13
                        opacity: 0.6
                    }
                }
                Repeater {
                    model: view.profile ? view.profile.notes.slice(0, 7) : []
                    delegate: RowLayout {
                        Layout.fillWidth: true
                        spacing: 6
                        PC3.Label {
                            text: modelData.recent ? "●" : "○"
                            font.pixelSize: 11
                            color: modelData.recent ? Kirigami.Theme.positiveTextColor
                                                    : Kirigami.Theme.textColor
                            opacity: modelData.recent ? 1.0 : 0.4
                        }
                        PC3.Label {
                            Layout.fillWidth: true
                            text: modelData.name
                            font.pixelSize: 13
                            elide: Text.ElideRight
                            opacity: 0.88
                        }
                        PC3.Label {
                            text: modelData.mtime_text
                            font.pixelSize: 12
                            font.family: "Noto Sans Mono"
                            opacity: 0.5
                        }
                    }
                }
            }
        }
    }
}
