import QtQuick 2.15
import org.kde.kirigami 2.20 as Kirigami
import org.kde.plasma.components 3.0 as PC3

Rectangle {
    id: btn
    property string text: ""
    property bool active: false
    property int badge: 0
    signal clicked()

    implicitHeight: 26
    implicitWidth: label.implicitWidth + 20 + (badge > 0 ? 18 : 0)
    radius: 13
    color: btn.active
           ? Qt.rgba(Kirigami.Theme.highlightColor.r, Kirigami.Theme.highlightColor.g,
                     Kirigami.Theme.highlightColor.b, 0.85)
           : (mouse.containsMouse
              ? Qt.rgba(Kirigami.Theme.textColor.r, Kirigami.Theme.textColor.g,
                        Kirigami.Theme.textColor.b, 0.10)
              : "transparent")
    border.width: btn.active ? 0 : 1.5
    border.color: Qt.rgba(Kirigami.Theme.textColor.r, Kirigami.Theme.textColor.g,
                          Kirigami.Theme.textColor.b, 0.32)

    Behavior on color { ColorAnimation { duration: 120 } }

    Row {
        id: row
        anchors.centerIn: parent
        spacing: 5
        PC3.Label {
            id: label
            text: btn.text
            font.pixelSize: 14
            font.weight: btn.active ? Font.DemiBold : Font.Normal
            color: btn.active ? Kirigami.Theme.highlightedTextColor : Kirigami.Theme.textColor
            anchors.verticalCenter: parent.verticalCenter
        }
        Rectangle {
            visible: btn.badge > 0
            width: 15; height: 15; radius: 8
            color: Qt.rgba(Kirigami.Theme.positiveTextColor.r, Kirigami.Theme.positiveTextColor.g,
                           Kirigami.Theme.positiveTextColor.b, 0.22)
            PC3.Label {
                anchors.centerIn: parent
                text: btn.badge
                font.pixelSize: 12
                font.weight: Font.DemiBold
                color: Kirigami.Theme.positiveTextColor
            }
        }
    }

    MouseArea {
        id: mouse
        anchors.fill: parent
        hoverEnabled: true
        cursorShape: Qt.PointingHandCursor
        onClicked: btn.clicked()
    }
}
