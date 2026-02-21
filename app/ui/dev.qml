import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import "components"

Item {
    id: root
    anchors.fill: parent

    property int currentPage: 0
    property bool sidebarVisible: true
    property int initialIndex: -1

    RowLayout {
        anchors.fill: parent

        // 1. Icon Sidebar
        Rectangle {
            id: sidebar
            width: 60
            color: "#222"
            Layout.fillHeight: true

            Column {
                anchors.centerIn: parent
                spacing: 10

                Repeater {
                    model: [
                        { icon: "Icons/chat.svg" },
                        { icon: "Icons/notebook.svg" },
                        { icon: "Icons/database.svg" },
                        { icon: "Icons/logs.svg" },
                        { icon: "Icons/settings.svg" }
                    ]

                    delegate: SidebarButton {
                        buttonIcon: modelData.icon
                        checked: currentPage === index
                        onClicked: {
                            if(currentPage === index) {
                                sidebarVisible = !sidebarVisible
                            } else {
                                currentPage = index
                                sidebarVisible = true
                            }
                        }
                    }
                }
            }
        }
        

        // 2. Sidebar Context
        Rectangle {
            id: sidebarContext
            property bool allowed: currentPage < 2
            
            width: (sidebarVisible && allowed) ? 220 : 0
            visible: allowed
            color: "#222"
            Layout.fillHeight: true

            Behavior on width {
                NumberAnimation { duration: 200; easing.type: InOutQuad }
            }

            Loader {
                id: sidebarLoader
                anchors.fill: parent
                source: {
                    switch (currentPage) {
                        case 0: return "pages/Chat/ChatSidebar.qml"
                        case 1: return "pages/Notes/NotesSidebar.qml"
                        case 2: return "pages/Database/DatabaseSidebar.qml"
                        case 3: return "pages/Logs/LogsSidebar.qml"
                        case 4: return "pages/Settings/SettingsSidebar.qml"
                    }
                }
                onLoaded: {
                    if (!item) return

                    if (currentPage === 0 && item.chatSelected) {
                        item.chatSelected.connect(function(chat_id) {
                            Qt.callLater(function() {
                                root.initialIndex = chat_id

                                if (mainLoader.item && mainLoader.item.loadMessages) {
                                    mainLoader.item.loadMessages(chat_id)
                                }
                            })
                        })

                        // item.onChatCreated.connect(function(chat_id) {
                        //     Qt.callLater(function () {
                        //         if (mainLoader.item && mainLoader.item.updateNewChat) {
                        //             mainLoader.item.updateNewChat(chat_id)
                        //         }
                        //     })
                        // })
                    }
                }

            }
        }

        // 3. Main Content
        Loader {
            id: mainLoader
            Layout.fillWidth: true
            Layout.fillHeight: true
            source: {
                switch (currentPage) {
                    case 0: return "pages/Chat/ChatPage.qml"
                    case 1: return "pages/Notes/NotesPage.qml"
                    case 2: return "pages/Database/DatabasePage.qml"
                    case 3: return "pages/Logs/LogsPage.qml"
                    case 4: return "pages/Settings/SettingsPage.qml"
                }
            }
            onLoaded: {
                // if(!item) return
                
                // if(item.loadMessages && item.loadMessages.id) {
                //     item.loadMessages.id = root.initialIndex
                // }
            }
        }
    }
}
