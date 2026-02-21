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
                        focusToCurrentChat()
                    })
                    currentId = -1
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
                backend.chatActions("get")

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
                        // root.loadMessages(model.id)
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
                        if(currentId === -1) currentId = 0
                        console.log("INDEX DELETING", index)

                        if(index === 0) Qt.callLater(()=> focusToCurrentChat())
                        let chat = chatModel.get(index)
                        
                        console.log("CHAT", chat)
                        backend.chatActions("delete", chat.id)
                        chatModel.remove(index, 1)
                    }
                }
            }
        }
    }

    function focusToCurrentChat() {
        chatList.currentIndex = 0
        chatList.positionViewAtIndex(0, ListView.Beginning)

        let firstChat = chatModel.get(0)
        root.currentId = firstChat.id
        console.log("FOCUSED ID: ", firstChat.id)
        root.chatSelected(firstChat.id)
        return firstChat.id
        
    }

    function loadMessages(chatId) {
        let messages = backend.messageActions("get", chatId)
        // console.log("MESSAGES RETURNED:", messages)
    }

    Connections {
        target: backend

        function onChatsData(chats) {
            chatModel.clear()

            chats.forEach(c => {
                console.log("\n\n\n\n CHATS:",c)
                chatModel.append(c)
            })

            Qt.callLater(function() {
                currentId = focusToCurrentChat()
                loadMessages(currentId)
            })
        }
        
        function onChatCreated(chatId, title) {
            console.log('CURRENT ID BEFORE:', currentId, "CHAT ID:", chatId)
            chatModel.remove(0)
            chatModel.insert(0, {
                id: chatId,
                title: title
            })
            currentId = chatId
            console.log('CURRENT ID AFTER:', currentId, "CHAT ID:", chatId)

            Qt.callLater(function() {
                
                focusToCurrentChat()
            })
            
        }
    }
    Component.onCompleted: {
        backend.chatActions("get")
    }
}