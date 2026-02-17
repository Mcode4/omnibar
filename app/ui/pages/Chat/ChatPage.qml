import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
// import QtQuick.Markdown 2.0

ColumnLayout {
    anchors.fill: parent
    spacing: 10

    property bool aiStreaming: false
    property bool isThinking: false
    property bool isProcessing: false

    property int streamingIndex: -1
    property int chatId: 0

    // Chat Log
    ScrollView {
        Layout.fillWidth: true
        Layout.fillHeight: true

        ListView {
            id: messageList
            Layout.fillHeight: true
            Layout.fillWidth: true
            model: messageModel
            onCountChanged: messageList.positionViewAtEnd()

            delegate: Text {
                width: messageList.width
                wrapMode: Text.Wrap
                textFormat: Text.MarkdownText

                text: "**" + role + ":** " + content

                font.family: "Segoe UI, Noto Color Emoji, Arial"
                font.pixelSize: 14

                Component.onCompleted: {
                    console.log("ROLE:", role)
                    console.log("CONTENT:", content)
                    console.log("TYPE:", typeof content)
                }

                // TextArea {
                //     id: chatLog
                //     readOnly: true
                //     wrapMode: Text.Wrap
                //     text: ""
                // }
            }
        }
    }

    ListModel { id: messageModel }

    // Processing Indicator
    Label {
        visible: isProcessing
        text: "Processing..."
        color: "gray"
    }

    // Loading Indicator
    Label {
        visible: isThinking
        text: "Thinking..."
        color: "lightgreen"
    }

    // Item { Layout.fillHeight: true }

    // Input Row
    RowLayout {
        Layout.fillWidth: true

        TextField {
            id: inputField
            Layout.fillWidth: true
            placeholderText: "Type a message..."

            onAccepted: sendMessage()
        }

        Button {
            text: "Send"
            onClicked: sendMessage()
        }
    }

    function sendMessage() {
        let input = inputField.text.trim()
        if(input === "") return

        messageModel.append({
            role: "You",
            content: inputField.text
        })

        backend.processAIRequest(chatId, input)
        inputField.text = ""
    }

    // Backend Connections
    Connections {
        target: backend

        function onAiStarted() {
            isProcessing = true
        }

        function onAiToken(phase, token) {
            isProcessing = false

            if(phase === "thinking"){
                isThinking = true
                return
            } 
            else {
                if(streamingIndex === -1){
                    messageModel.append({
                        role: "Omni",
                        content: ""
                    })
                    streamingIndex = messageModel.count - 1
                }
            }

            let current = messageModel.get(streamingIndex)
            
            messageModel.set(streamingIndex, {
                role: "Omni",
                content: current.content + token
            })
        }

        function onAiResults(result) {
           console.log("RESULT:", result)

           isThinking = false
           isProcessing = false

           if(result.success) {
            if(streamingIndex === -1) {
                messageModel.append({
                    role: "Omni",
                    content: result.text
                })
            } 

            if (result.chat_id && result.chat_id !== chatId)  {
                chatId = result.chat_id
            }
           } else {
            messageModel.append({
                role: "Omni",
                content: "Error: " + result.error
            })
           }
           streamingIndex = -1
        }

        function onMessagesLoaded(messages) {
            console.log("MESSAGE RESULTS", messages)

            // messages.forEach(m => {
            //     messageModel.append({
            //         role: m.role === ""
            //     })
            // })
        }
    }
}