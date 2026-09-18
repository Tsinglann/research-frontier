import QtQuick 2.15
import org.kde.kirigami 2.20 as Kirigami

// 半透明面板：不依赖 PlasmaCore 主题，避免不同 Plasma 版本的 API 差异。
//
// 注意：不要在这里重新声明 Rectangle 自带的属性名。
//   - `panel` 是 QtQuick.Controls Control 体系里的既有属性名，会和 Rectangle 冲突
//   - 曾把圆角写成 `property real radius: 14` + `radius: pane.radius`，同一属性被赋值两次，
//     会让整个组件加载失败（表现为主界面报 "Type GlassPane unavailable"）
// 因此这里只暴露新名字（panelColor / tintStrength），radius 直接用 Rectangle 自带的。
Rectangle {
    id: pane

    property real tintStrength: 1.0
    // 背景不透明度从 0.55 提到 0.86：半透明面板透过壁纸会让文字对比度不足
    // （用户反馈"蓝色字体和背景颜色相似，看不清"）。这里保证面板本身足够实。
    property color panelColor: Qt.rgba(Kirigami.Theme.backgroundColor.r * 0.92,
                                       Kirigami.Theme.backgroundColor.g * 0.92,
                                       Kirigami.Theme.backgroundColor.b * 0.92,
                                       Math.min(0.96, 0.90 * tintStrength))
    // 面板内容挂在这里；用 default alias 让调用方可以直接写子项
    default property alias content: inner.data

    // 边框从 0.14 提到 0.34：原来几乎看不见，各个卡片/面板糊成一片
    // （用户反馈「加上底部的边框，不然看不清」）。宽度也用 1.5 更明确。
    color: panelColor
    border.width: 1.5
    border.color: Qt.rgba(Kirigami.Theme.textColor.r, Kirigami.Theme.textColor.g,
                          Kirigami.Theme.textColor.b, 0.34)
    radius: 14

    Item {
        id: inner
        anchors.fill: parent
        anchors.margins: 1
    }
}
