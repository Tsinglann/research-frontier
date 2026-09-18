import QtQuick 2.15
import QtQuick.Layouts 1.15
import org.kde.kirigami 2.20 as Kirigami
import org.kde.plasma.components 3.0 as PC3

Flickable {
    id: view
    property var papersDoc: null
    property var papers: papersDoc?.papers || []

    contentWidth: width
    contentHeight: col.implicitHeight + 8
    clip: true
    boundsBehavior: Flickable.StopAtBounds

    ColumnLayout {
        id: col
        width: view.width
        spacing: 7

        PC3.Label {
            Layout.fillWidth: true
            visible: view.papers.length === 0
            text: "还没有论文数据。点 ↻ 立即更新，或等每天 06:00 的自动更新。"
            font.pixelSize: 13
            opacity: 0.6
            wrapMode: Text.WordWrap
            horizontalAlignment: Text.AlignHCenter
        }

        Repeater {
            model: view.papers
            delegate: PaperCard {
                Layout.fillWidth: true
                paper: modelData
            }
        }
    }
}
