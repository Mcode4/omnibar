import QtQuick
import QtQuick.Controls

ApplicationWindow {
    id: devRoot
    visible: true
    width: 1000
    height: 600
    title: "OmniManager (Dev)"

    Loader {
        id: devLoader
        anchors.fill: parent
        source: "dev.qml"
        asynchronous: true
    }

    function reloadMain() {
        // console.log("🔄 Reloading dev.qml only")
        devLoader.source = ""
        devLoader.source = "dev.qml?t=" + Date.now()
    }
}