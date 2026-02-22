import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

ColumnLayout {
    id: chatPage
    anchors.fill: parent
    spacing: 10

    property int chatId: -1
    // property int streamingIndex: -1
    
    property bool processing: false
    property bool thinking: false
    property bool tooling: false

    ListModel { id: messageModel }

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
            }
        }
        // Processing Indicator
        Label {
            visible: root.processing
            text: "⚙️ Processing..."
            color: "gray"
        }

        // Loading Indicator
        Label {
            visible: root.thinking
            text: "🤔 Thinking..."
            color: "gray"
        }

        Label {
            visible: root.tooling
            text: "🛠️ Using tools..."
            color: "gray"
        }
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

        backend.processAIRequest(chatPage.chatId, input)
        inputField.text = ""
    }

    function loadMessages(chatId) {
        console.log("BEFORE LOADING MESSAGES ID:", chatPage.chatId)
        chatPage.chatId = chatId
        console.log("LOADING ID:", chatId, "CHAT ID NOW:", chatPage.chatId)
        if(chatId === -1) {
            messageModel.clear()
            return
        }
        backend.messageActions("get", chatId)
    }

    // Backend Connections
    Connections {
        target: backend

        // Loading
        function onMessagesData(messages) {
            // console.log("\n\n\nLOADED MESSAGES\n\n\n")
            if(!messages) return
            messageModel.clear()

            messages.forEach(m => {
                messageModel.append({
                    role: m.role === "user" ? "You" : "Omni",
                    content: m.content
                })
            })
        }

        // Phases
         function onAiStarted() {
            ChatState.setProcessing(chatPage.chatId, true)
            ChatState.setStreamTokens(chatPage.chatId, "")
            ChatState.setStreamIndex(chatPage.chatId, -1)

            console.log(`\n\n\n\n\nMODEL STARTED...\n
                PROCESSING STATE: ${ChatState.isProcessing(chatPage.chatId)}\n
                PROCESSING: ${processing}\n
            \n\n\n\n\n`)
        }
        function onModelThinking(index) {
            ChatState.setThinking(index, true)

            console.log(`\n\n\n\n\nMODEL THINKING...
                THINKING STATE: ${ChatState.isThinking(index)}
                THINKING: ${thinking}\n
            \n\n\n\n\n`)
        }
        function onModelTooling(index) {
            ChatState.setTooling(index, true)

            console.log(`\n\n\n\n\nMODEL TOOLING...
                TOOLING STATE: ${ChatState.isTooling(index)}\n
                TOOLING: ${tooling}\n
            \n\n\n\n\n`)
        }

        // Streaming and Responses
        function onAiTokens(phase, token, chat_id) {
            if (chat_id !== chatPage.chatId) {
                console.log(`NOT STREAMING: STERAMING ON ID: ${chat_id} CHAT ID: ${chatPage.chatId}`)
                return
            }

            if (phase === "thinking") {
                console.log("STREAMING ERROR: PHASE: THINKING")
                return
            }

            // ChatState.setProcessing(result.chat_id, false)
            // ChatState.setThinking(result.chat_id, false)
            // ChatState.setTooling(result.chat_id, false)

            let streamingIndex = ChatState.streamIndex(chatPage.chatId)

            if (streamingIndex === -1) {
                console.log("INDEX === -1", streamingIndex)
                messageModel.append({
                    role: "Omni",
                    content: token
                })

                // streamingIndex = messageModel.count - 1
                ChatState.setStreamIndex(chatPage.chatId, messageModel.count - 1)
                console.log("INDEX SET TO LAST MODEL INDEX", streamingIndex)
                return
            }

            
            // let existing = messageModel.get(streamingIndex).content
            // let updated = existing + token
            let existing = ChatState.streamTokens(chatPage.chatId) || ""
            let updated = existing + token
            ChatState.setStreamTokens(chatPage.chatId, updated)
            console.log(`MESSAGES APPENDING: INDEX: ${streamingIndex} CONTENT: ${updated}`)
            messageModel.set(streamingIndex, {
                role: "Omni",
                content: updated,
                streaming: true
            })
        }

        function onAiResults(result) {
            ChatState.setProcessing(result.chat_id, false)
            ChatState.setThinking(result.chat_id, false)
            ChatState.setTooling(result.chat_id, false)
            console.log("\n\n\n\n\nMODEL FINISH\n")
            console.log(`PROCESSING: ${ChatState.isProcessing(result.chat_id)}, THINKING: ${ChatState.isThinking(result.chat_id)}, TOOLING: ${ChatState.isTooling(result.chat_id)}\n`)
            if(result.use_stream) {
                ChatState.setStreamTokens(result.chat_id, "")
                // ChatState.setStreamIndex(result.chat_id, -1)
                // console.log(`USED STREAM TRUE, STREAM TOKENS: ${ChatState.streamTokens(result.chat_id)} STREAM INDEX: ${ChatState.streamIndex(result.chat_id)}\n\n\n\n\n`)
                return
            }

            if(result.success) {
                console.log("RESULTS ON FINISHED, USE STREAM:", result.use_stream)
                messageModel.append({
                        role: "Omni",
                        content: result.text
                    })
            } else {
                messageModel.append({
                    role: "Omni",
                    content: "Error: " + result.error
                })
            }
            
        }
    }
    
    Connections {
        target: ChatState

        function onStateChanged(id) {
            if (id !== chatPage.chatId)
                return

            processing = ChatState.isProcessing(id)
            thinking = ChatState.isThinking(id)
            tooling = ChatState.isTooling(id)
        }
    }

    Component.onCompleted: {
        console.log("COMPONENT COMPLETE")

        console.log("ChatState object:", ChatState)
    }
}