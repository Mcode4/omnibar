import os
import json
from collections import deque
from PySide6.QtCore import QObject, Slot, Signal, QThread
from backend.command_router import CommandRouter


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
    tokenGenerated = Signal(str, str, int)
    finished = Signal(dict)

    chatCreated = Signal(int, str)
    messagesLoaded = Signal(list)

    chatData = Signal(list)
    chatActionFinished = Signal()

    messageData = Signal(list)
    messageActionFinished = Signal()

    def __init__(self, system_db, user_db, settings, model_manager, rag_pipeline):
        super().__init__()
        self.system_db = system_db
        self.user_db = user_db
        self.settings = settings
        self.model_manager = model_manager
        self.rag_pipeline = rag_pipeline

        self.chat_service = None
        self.orchestrator = None

    @Slot()
    def initialize(self):
        from backend.ai.llm_engine import LLMEngine
        from backend.ai.orchestrator import Orchestrator
        from backend.services.chat_service import ChatService

        llm = LLMEngine(self.model_manager, self.settings)
        orchestrator = Orchestrator(
            llm,
            self.rag_pipeline,
            self.settings,
            self.user_db,
            None
        )
        chat_service = ChatService(
            self.system_db,
            orchestrator
        )

        orchestrator.chat_service = chat_service
        self.chat_service = chat_service
        self.orchestrator = orchestrator

        llm.tokenGenerated.connect(self.tokenGenerated)
        llm.generationFinished.connect(self._handle_finished)
        chat_service.chatCreated.connect(self.chatCreated)

    # ============================================================
    #                    AI PROMPTING/HANDLING
    # ============================================================
    @Slot(tuple)
    def process(self, request):
        self.started.emit()
        chat_id, prompt = request
        # print(f'CHAT ID: {chat_id} PROMPT: {prompt}')
        self.chat_service.send_message(chat_id, prompt)

    def _handle_finished(self, phase, results, transfer):
        if not results["success"]:
            self.finished.emit(results)
            return
        
        # ================== INTERNAL FINISHED PROMPTS ==================
        if phase == "summary":
            summary_text = results["text"]
            if summary_text and summary_text.strip():
                self.chat_service.add_summary(summary_text, transfer)
                embedding = self.rag_pipeline.embedding_engine.embed(summary_text)
                self.user_db.add_memory_with_embedding(
                    type="summary",
                    category="conversation",
                    content=summary_text,
                    embedding=embedding,
                    source="ai",
                    importance=2,
                    confidence=0.9
                )
            return
        
        elif phase == "thinking":
            self.orchestrator.handle_thinking_prompt(results, transfer)
            return
        
        # ================== EXTERNAL FINISHED PROMPTS ==================
        elif phase in ("instruct", "tool"):
            text = results["text"]
            chat_id = transfer["chat_id"]

            self.chat_service.cache_response(text, transfer)
            self.finished.emit({
                "success": True,
                "chat_id": chat_id,
                "text": text,
                "prompt_tokens": results["prompt_tokens"],
                "completion_tokens": results["completion_tokens"],
                "total_tokens": results["total_tokens"],
                "use_stream": results["use_stream"]
            })
            return 

    # ============================================================
    #                    CHAT DATA-SIGNAL HANDLING
    # ============================================================
    def handle_chat_actions(self, action_tuple):
        action, id, data = action_tuple
        print("CHAT ACTION RECIEVED IN HANDLER", {action, id, data})
        if action == "get":
            chats = self._get_chats()
            print("SUCCESS, EMITTING GET FOR CHAT ACTION")
            self.chatData.emit(chats)
            return
        
        elif id is None:
            return
        
        elif action == "update":
            if not data:
                return
            if len(data) > 25:
                title = data[:25]
            else:
                title = data
            self.system_db.edit_chat_title(title, id, has_title=True)
            self.chatActionFinished.emit()
            return
        
        else:
            self._remove_chat(id)
            self.chatActionFinished.emit()
            return
        
    def handle_message_actions(self, action_tuple):
        action, id, data = action_tuple
        if id is None:
            return
        if action == "get":
            messages = self._get_messages(id)
            self.messageData.emit(messages)
            return
        
        elif data is None:
            return
        
        elif action == "update":
            # No generate function yet
            return
        
    # @Slot(result="QVariantList")
    def _get_chats(self):
        chats = self.chat_service.system_db.get_chats()
        print("CHATS BEFORE BRIDGE: ", chats)
        return chats if chats else []
    
    # @Slot(int, result="QVariantList")
    def _get_messages(self, chat_id):
        messages = self.chat_service.system_db.get_messages_by_chat(chat_id)
        print("MESSAGES BRIDGE", messages, f"CHAT ID:", chat_id)
        return messages

    # @Slot(int)
    def _remove_chat(self, chat_id):
        removed_chat = self.chat_service.system_db.delete_chat(chat_id)
        print(f"\n\n\nREMOVED CHAT: {removed_chat} CHAT ID: {chat_id}\n\n\n")



class BackendBridge(QObject):
    systemSignal = Signal(str)
    systemStarted = Signal()
    systemResults = Signal(str)

    aiSignal = Signal(tuple)
    aiStarted = Signal()
    aiTokens = Signal(str, str, int) # Streaming Listener
    aiResults = Signal(dict)

    modelThinking = Signal(int)
    modelTooling = Signal(int)
    phaseState = Signal(dict)

    chatCreated = Signal(int, str)

    chatAction = Signal(tuple)
    chatsData = Signal(list)
    chatActionsFinished = Signal()

    messageAction = Signal(tuple)
    messagesData = Signal(list)
    messageActionsFinished = Signal()

    def __init__(self, current_tasks, settings, system_db, user_db, model_manager, rag_pipeline):
        super().__init__()
        # ================== VARIABLES ==================
        self.current_tasks = current_tasks
        self.settings = settings
        self.system_db = system_db
        self.user_db = user_db
        self.model_manager = model_manager
        self.rag_pipeline = rag_pipeline
        # self.chat_service = chat_service

        # ================== QTHREADS ==================
        self.system_thread = QThread()
        self.ai_thread = QThread()

        # ================== WORKERS ==================
        self.system_worker = SystemWorker()

        self.ai_worker = AIWorker(
            self.system_db,
            self.user_db,
            self.settings,
            self.model_manager,
            self.rag_pipeline
        )

        # ================== QUEUES ==================
        self.system_queue = deque()
        self.ai_queue = deque()

        # ================== WORKER CONNECTIONS ==================
        self.system_worker.moveToThread(self.system_thread)

        self.ai_worker.moveToThread(self.ai_thread)
        self.rag_pipeline.moveToThread(self.ai_thread) #QObjects only moveToThread

        # ================== THREAD CONNECTIONS ==================
        self.ai_thread.started.connect(self.ai_worker.initialize)

        # ================== SIGNAL CONNECTIONS ==================
        self.systemSignal.connect(self.system_worker.process)
        self.system_worker.started.connect(self.systemStarted)
        self.system_worker.finished.connect(self._on_system_finished)

        self.aiSignal.connect(self.ai_worker.process)
        self.ai_worker.started.connect(self.aiStarted)
        self.ai_worker.tokenGenerated.connect(self.aiTokens)
        self.ai_worker.finished.connect(self._on_ai_finished)
        self.ai_worker.chatCreated.connect(self.chatCreated)

        self.chatAction.connect(self.ai_worker.handle_chat_actions)
        self.ai_worker.chatData.connect(self.chatsData)
        self.ai_worker.chatActionFinished.connect(self.chatActionsFinished)

        self.messageAction.connect(self.ai_worker.handle_message_actions)
        self.ai_worker.messageData.connect(self.messagesData)
        self.ai_worker.messageActionFinished.connect(self.messageActionsFinished)

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

        self.phase_state = {}


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
        
        self.aiResults.emit(results)
        self._try_process_next_ai()
    
    # ============================================================
    #                    CHAT PROCESSES
    # ============================================================
    @Slot(str)
    @Slot(str, int)
    @Slot(str, int, str)
    def chatActions(self, action, id=None, data=None):
        print("\n\nACTION RECEIVED", {action, id, data})
        if action in ("get", "update", "delete"):
            print("forwarding chat action...")
            self.chatAction.emit(( action, id, data ))
        else:
            return
    
    @Slot(str)
    @Slot(str, int)
    @Slot(str, int, dict)
    def messageActions(self, action, id=None, data=None):
        print("\n\nACTION RECEIVED", {action, id, data})
        if action in ("get", "regenerate"):
            print("forwarding message action...")
            self.messageAction.emit((action, id, data))
    