import QtQuick
import QtQuick.Controls
import QtQuick.Layouts


ColumnLayout {
    id: root
    signal chatSelected(int chat_id)
    property int currentId: 0
    property bool newChatActive: false

    anchors.fill: parent
    

    ListModel { id: chatModel }

    RowLayout {
        Layout.fillWidth: true
        anchors.margins: 6
        spacing: 6

        Button {
            id: addChatButton
            Layout.fillWidth: true
            height: 30
            onClicked: {
                console.log("CLICK")
                if(!newChatActive && currentId !== -1) {
                    chatModel.insert(0, {
                        id: -1,
                        title: "New Chat"
                    })
                    Qt.callLater(function() {
                        chatList.positionViewAtIndex(-1, ListView.Beginning)
                        currentIndex = 0
                        root.currentId = -1
                        root.chatSelected(-1)
                    })
                }
            }

            Text {
                anchors.centerIn: parent
                text: "Add"
            }
        }
        Button {
            id: refreshChatButton
            Layout.fillWidth: true
            height: 30
            onClicked: {
                loadChats(true)
            }

            Text {
                anchors.centerIn: parent
                text: "Refresh"
            }
        }
    }

    ListView {
        id: chatList
        currentIndex: -1
        Layout.fillWidth: true
        Layout.fillHeight: true
        clip: true
        model: chatModel

        

        delegate: Item {
            width: chatList.width
            height: 50
            

            Rectangle {
                anchors.fill: parent
                color: chatList.currentIndex === index ? '#333' : "#222"
            }

            RowLayout {
                anchors.fill: parent
                anchors.margins: 8
                spacing: 6

                MouseArea {
                    Layout.fillWidth: true
                    Layout.fillHeight: true
                    onClicked: {
                        chatList.currentIndex = index
                        root.currentId = model.id
                        root.chatSelected(model.id)
                    }

                    Text {
                        anchors.verticalCenter: parent.verticalCenter
                        text: model.title
                        color: "white"
                        elide: Text.ElideRight
                    }
                }

                Button {
                    text: "✕"
                    Layout.preferredWidth: 30
                    onClicked: {
                        let chat = chatModel.get(index)
                        console.log("CHAT", chat)
                        backend.remove_chat(chat.id)
                        chatModel.remove(index, 1)
                    }
                }
            }
        }
    }

    function loadChats(check) {
        if (!check) return
        chatModel.clear()
        let chats = backend.getChats()

        for(let i=0; i<chats.length; i++) {
            console.log("CHATS APPENDING", chats[i])
            chatModel.append(chats[i])
        }

        Qt.callLater(function() {
            chatList.currentIndex = 0
            chatList.positionViewAtIndex(0, ListView.Beginning)

            let firstChat = chatModel.get(0)
            root.currentId = firstChat.id
            root.chatSelected(firstChat.id)
        })
    }

    function loadMessages(id) {
        let messages = backend.getMessages(id)
        // console.log("MESSAGES RETURNED:", messages)
    }

    Connections {
        target: backend
        
    }
    Component.onCompleted: loadChats(true)
}