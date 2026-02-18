import os
import json
from collections import deque
from PySide6.QtCore import QObject, Slot, Signal, QThread
from backend.command_router import CommandRouter
from backend.settings import Settings
from backend.services.chat_service import ChatService


class SystemWorker(QObject):
    finished = Signal(str)
    started = Signal()

    def __init__(self):
        super().__init__()
        self.router = CommandRouter()

    @Slot(str)
    def process(self, text):
        self.started.emit()
        result = self.router.route(text)
        self.finished.emit(json.dumps(result))

class AIWorker(QObject):
    started = Signal()
    tokenGenerated = Signal(str, str)
    finished = Signal(dict)

    def __init__(self, chat_service: ChatService):
        super().__init__()
        self.chat_service = chat_service
        self.chat_service.tokenGenerated.connect(self.tokenGenerated)

    @Slot(tuple)
    def process(self, request):
        self.started.emit()
        chat_id, prompt = request
        # print(f'CHAT ID: {chat_id} PROMPT: {prompt}')
        self.chat_service.send_message(chat_id, prompt)


class BackendBridge(QObject):
    systemSignal = Signal(str)
    systemStarted = Signal()
    systemResults = Signal(str)

    aiSignal = Signal(tuple)
    aiStarted = Signal()
    aiToken = Signal(str, str) # Streaming Listener
    aiResults = Signal(dict)

    newChatCreated = Signal()
    messagesLoaded = Signal(list)

    def __init__(self, current_tasks, settings: Settings, chat_service: ChatService):
        super().__init__()
        # ================== VARIABLES ==================
        self.current_tasks = current_tasks
        self.settings = settings
        self.chat_service = chat_service

        # ================== QTHREADS ==================
        self.system_thread = QThread()
        self.ai_thread = QThread()

        # ================== WORKERS ==================
        self.system_worker = SystemWorker()
        self.ai_worker = AIWorker(chat_service)

        # ================== QUEUES ==================
        self.system_queue = deque()
        self.ai_queue = deque()

        # ================== WORKER CONNECTIONS ==================
        self.system_worker.moveToThread(self.system_thread)
        self.ai_worker.moveToThread(self.ai_thread)

        # ================== SIGNAL CONNECTIONS ==================
        self.systemSignal.connect(self.system_worker.process)
        self.system_worker.started.connect(self.systemStarted)
        self.system_worker.finished.connect(self._on_system_finished)

        self.aiSignal.connect(self.ai_worker.process)
        self.ai_worker.started.connect(self.aiStarted)
        self.ai_worker.tokenGenerated.connect(self.aiToken)

        chat_service.messageFinished.connect(self._on_ai_finished)
        chat_service.chatMessageCreated.connect(self.newChatCreated)

        # ================== START THREADS ==================
        self.system_thread.start()
        self.ai_thread.start()

    def shutdown(self):
        self.ai_thread.quit()
        self.ai_thread.wait()
        self.system_thread.quit()
        self.system_thread.wait()

        # Delete workers explicitly
        self.system_worker.deleteLater()
        self.ai_worker.deleteLater()
        self.system_worker = None
        self.ai_worker = None

        self.ai_thread.deleteLater()
        self.system_thread.deleteLater()
        self.ai_thread = None
        self.system_thread = None


    # ============================================================
    #                    SYSTEM PROCESSES
    # ============================================================
    @Slot(str)
    def processSystemCommand(self, text: str):
        text = text.strip()
        # print(f"Command received from UI: {text}")
        self.system_queue.append(text)
        self._try_process_next()

    def _try_process_next(self):
        max_system = self.settings.get_settings()["max_tasks"]["system_tasks"]

        if (self.current_tasks["system"] < max_system and self.system_queue):
            next_task = self.system_queue.popleft()
            self.current_tasks["system"] += 1
            self.systemSignal.emit(next_task)

    def _on_system_finished(self, results):
        self.current_tasks["system"] -= 1
        self.systemResults.emit(results)
        self._try_process_next()

    # ============================================================
    #                      AI PROCESSES
    # ============================================================
    @Slot(int, str)
    def processAIRequest(self, chat_id: int, prompt: str):
        self.ai_queue.append((chat_id, prompt))
        # print(f"Prompt received from UI at Chat ID({chat_id}): {prompt}")
        self._try_process_next_ai()

    def _try_process_next_ai(self):
        ai_tasks = self.settings.get_settings()["max_tasks"]["ai_tasks"]

        if (self.current_tasks["ai"] < ai_tasks and self.ai_queue):
            next_task = self.ai_queue.popleft()
            self.current_tasks["ai"] += 1
            self.aiSignal.emit(next_task)
        
    def _on_ai_finished(self, results):
        # print("\n\nAI FINISHED SIGNAL RECEIVED\n\n")
        self.current_tasks["ai"] -= 1
        print(f"\n\nPrompt Complete: {results}")
        
        self.aiResults.emit({
            "chat_id": int(results.get("chat_id")) if results["success"] else "",
            "success": bool(results["success"]),
            "text": str(results.get("text", "")),
            "error": str(results.get("error", ""))
        })
        self._try_process_next_ai()

    # ============================================================
    #                    CHAT DATA-SIGNAL HANDLING
    # ============================================================
    @Slot(result="QVariantList")
    def getChats(self):
        chats = self.chat_service.system_db.get_chats()
        # print("CHATS BEFORE BRIDGE: ", chats)
        return chats if chats else []
    
    @Slot(int, result="QVariantList")
    def getMessages(self, chat_id):
        messages = self.chat_service.system_db.get_messages_by_chat(chat_id)
        # print("MESSAGES BRIDGE", messages, f"CHAT ID:", chat_id)
        self.messagesLoaded.emit(messages if messages else [])

    

