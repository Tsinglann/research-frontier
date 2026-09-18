import QtQuick 2.15
import QtQuick.Layouts 1.15
import org.kde.kirigami 2.20 as Kirigami
import org.kde.plasma.components 3.0 as PC3

// 一行「标签 + 条 + 数值」，用于画像里的主题簇/期刊分布。
RowLayout {
    id: row
    property string label: ""
    property real value: 0
    property real maximum: 1
    property string valueText: ""
    property color barColor: Kirigami.Theme.highlightColor
    spacing: 6

    PC3.Label {
        text: row.label
        font.pixelSize: 13
        color: Kirigami.Theme.textColor
        opacity: 0.86
        Layout.preferredWidth: 104
        elide: Text.ElideRight
    }
    Rectangle {
        Layout.fillWidth: true
        Layout.preferredHeight: 8
        radius: 4
        color: Qt.rgba(Kirigami.Theme.textColor.r, Kirigami.Theme.textColor.g,
                       Kirigami.Theme.textColor.b, 0.12)
        Rectangle {
            height: parent.height
            radius: 4
            width: Math.max(3, parent.width * Math.min(1, row.value / Math.max(1, row.maximum)))
            color: row.barColor
        }
    }
    PC3.Label {
        text: row.valueText !== "" ? row.valueText : Math.round(row.value)
        font.pixelSize: 13
        font.family: "Noto Sans Mono"
        opacity: 0.72
        Layout.preferredWidth: 34
        horizontalAlignment: Text.AlignRight
    }
}
