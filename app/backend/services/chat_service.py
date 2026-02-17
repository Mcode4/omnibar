from PySide6.QtCore import Signal, QObject
import threading
from backend.databases.system_db import SystemDatabase
from backend.databases.user_db import UserDatabase
from backend.ai.orchestrator import Orchestrator

class ChatService(QObject):
    tokenGenerated = Signal(str, str)
    messageFinished = Signal(dict)
    chatMessageCreated = Signal()

    def __init__(self, system_db: SystemDatabase, user_db: UserDatabase, orchestrator: Orchestrator):
        super().__init__()
        self.system_db = system_db
        self.user_db = user_db
        self.orchestrator = orchestrator
        self.chat_cache = {}
        self._current_chat_id = None

        self.orchestrator.llm.token_generated.connect(self._handle_token)
        self.orchestrator.llm.generation_finished.connect(self._handle_finished)

    # ============================================================
    #                    PROMPT HANDLING
    # ============================================================
    def send_message(self, chat_id, prompt):
        if not chat_id or chat_id == 0:
            chat_id = self.system_db.create_chat(prompt[:40])

        history = self.system_db.get_messages_by_chat(chat_id)
        
        if chat_id not in self.chat_cache:
            self.chat_cache[chat_id] = history
            

        user_msg_id = self.system_db.create_message(chat_id, "user", prompt)
        self.chatMessageCreated.emit()
        user_msg = self.system_db.get_message_by_id(user_msg_id)
        self.chat_cache[chat_id].append(user_msg)
        self._current_chat_id = chat_id

        print("SEND MESSAGE IMPORTANCES: ", {
            "chat_cache": self.chat_cache,
            "chat_id": chat_id,
            "_current_chat_id": self._current_chat_id,
            "history": history
        })

        self.orchestrator.run(prompt, self.chat_cache[chat_id])

    # ============================================================
    #                    ASSISTING CHAT WITH AI
    # ============================================================
    def _generate_title_async(self, messages, chat_id):
        def worker():
            self.orchestrator.llm.generate(
                model_name="instruct",
                messages=messages,
                system_prompt="""
                    In 5-20 words, create a summary of the chat so for.
                    Add emoji(s) to the front of summary that best fit summary 
                """,
                source="title"
            )
        def on_title_results(results):
            if results["success"]:
                self.system_db.edit_chat_title(results["text"], chat_id)
            else:
                print(f"Failed to generate title: {results["error"]}")
        
        threading.Thread(target=worker, daemon=True).start()
        self.orchestrator.llm.titleSignal.connect(on_title_results)

    def _maybe_summarize(self, messages, chat_id):
        max_messages = self.orchestrator.settings.get_settings().get("max_messages", 12)
        summarize = self.orchestrator.settings.get_settings().get("summarize_messages", True)

        if(len(messages) <= max_messages):
            return messages
        
        def worker():
            if(summarize):
                self.orchestrator.llm.generate(
                    model_name="instruct",
                    messages=messages,
                    system_prompt="""
                        Summarize this conversation clearly and concisely.
                        Preserve key decisions, facts, and context.
                    """,
                    source="summary"
                )
        def on_summary_results(results):
            if(results["success"]):
                summarized_text = results["text"]

                self.chat_cache[chat_id] = [{
                    "role": "system",
                    "content": summarized_text
                }]

                summary_embedding = self.orchestrator.rag.embedding_engine.embed(summarized_text)[0]
                self.user_db.add_memory_with_embedding(
                    type_="conversation_summary",
                    category="chat",
                    content="chat",
                    embedding=summary_embedding,
                    importance=2
                )
            else:
                print(f"Summary failed: {summarize["error"]}")

        threading.Thread(target=worker, daemon=True).start()
        self.orchestrator.llm.summarySignal.connect(on_summary_results)

    # ============================================================
    #                    TOKEN HANDLING FOR STREAMING
    # ============================================================
    def _handle_token(self, phase, token):
        stream_when = self.orchestrator.settings.get_settings()["generate_settings"]["stream_when"]
        stream_thinking = True if stream_when == "both" or stream_when == "thinking" else False
        stream_instruct = True if stream_when == "both" or stream_when == "instruct" else False

        if (phase == "thinking" and stream_thinking) or (phase == "instruct" and stream_instruct):
            self.tokenGenerated.emit(phase, token)

    def _handle_finished(self, phase, results):
        if not results["success"]:
            self.messageFinished.emit(results)
            return
        
        if phase == "instruct":
            text = results["text"]

            chat_id = self._current_chat_id
            sys_msg_id = self.system_db.create_message(chat_id, "assistant", text)
            sys_msg = self.system_db.get_message_by_id(sys_msg_id)
            self.chat_cache[chat_id].append(sys_msg)
            self._maybe_summarize(self.chat_cache[chat_id], chat_id)
        
            self.messageFinished.emit({
                "success": True,
                "chat_id": chat_id,
                "text": text
            })