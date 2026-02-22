from PySide6.QtCore import QObject, Signal, Slot

class ChatState(QObject):
    stateChanged = Signal(int)
    def __init__(self):
        super().__init__()
        self._thinking = {}
        self._processing = {}
        self._tooling = {}
        self._stream_tokens = {}
        self._stream_index = {}

    # ============================================================
    #                    GETTERS
    # ============================================================
    @Slot(int, result=bool)
    def isThinking(self, chat_id):
        return self._thinking.get(chat_id, False)
    
    @Slot(int, result=bool)
    def isProcessing(self, chat_id):
        return self._processing.get(chat_id, False)
    
    @Slot(int, result=bool)
    def isTooling(self, chat_id):
        return self._tooling.get(chat_id, False)
    
    @Slot(int, result=str)
    def streamTokens(self, chat_id):
        return self._stream_tokens.get(chat_id, "")
    
    @Slot(int, result=int)
    def streamIndex(self, chat_id):
        return self._stream_index.get(chat_id, -1)
    
    # ============================================================
    #                    SETTERS
    # ============================================================
    @Slot(int, bool)
    def setThinking(self, chat_id, value):
        self._thinking[chat_id] = value
        self._processing[chat_id] = False
        self._tooling[chat_id] = False

        self.stateChanged.emit(chat_id)
        return self._thinking[chat_id]

    @Slot(int, bool)
    def setProcessing(self, chat_id, value):
        self._processing[chat_id] = value
        self._thinking[chat_id] = False
        self._tooling[chat_id] = False

        self.stateChanged.emit(chat_id)
        return self._processing[chat_id]

    @Slot(int, bool)
    def setTooling(self, chat_id, value):
        self._tooling[chat_id] = value
        self._thinking[chat_id] = False
        self._processing[chat_id] = False

        self.stateChanged.emit(chat_id)
        return self._tooling[chat_id]

    @Slot(int, str)   
    def setStreamTokens(self, chat_id, value):
        self._stream_tokens[chat_id] = value

        # self.stateChanged.emit(chat_id)
        return self._stream_tokens[chat_id]

    @Slot(int, int)
    def setStreamIndex(self, chat_id, value):
        self._stream_index[chat_id] = value

        # self.stateChanged.emit(chat_id)
        return self._stream_index[chat_id]