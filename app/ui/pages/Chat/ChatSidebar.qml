import QtQuick
import QtQuick.Controls
import QtQuick.Layouts


ColumnLayout {
    id: root
    signal chatSelected(int chat_id)

    ListModel { id: chatModel }

    ListView {
        id: chatList
        currentIndex: -1
        Layout.fillWidth: true
        Layout.fillHeight: true
        model: chatModel

        delegate: Rectangle {
            width: chatList.width
            height: 50
            color: chatList.currentIndex === index ? '#333' : "#222"

            Text {
                anchors.centerIn: parent
                text: model.title
                color: "white"
                elide: Text.ElideRight
            }

            MouseArea {
                anchors.fill: parent
                onClicked: {
                    // console.log("Clicked, index", index)
                    loadMessages(index)
                    chatList.currentIndex = index
                    root.chatSelected(model.id)
                }
            }
        }
    }

    function loadChats() {
        chatModel.clear()
        let chats = backend.getChats()

        for(let i=0; i<chats.length; i++) {
            chatModel.append(chats[i])
        }
    }

    function loadMessages(id) {
        let messages = backend.getMessages(id)
        // console.log("MESSAGES RETURNED:", messages)
    }

    Connections {
        target: backend

        function onNewChatCreated() {
            loadChats()
        }
    }

    Component.onCompleted: loadChats()
}