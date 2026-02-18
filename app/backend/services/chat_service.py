from PySide6.QtCore import Signal, QObject
import threading
from backend.databases.system_db import SystemDatabase
from backend.databases.user_db import UserDatabase
from backend.ai.orchestrator import Orchestrator

class ChatService(QObject):
    tokenGenerated = Signal(str, str)
    messageFinished = Signal(dict)
    chatCreated = Signal()

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
            self.chatCreated.emit()

        history = self.system_db.get_messages_by_chat(chat_id)
        
        if chat_id not in self.chat_cache:
            self.chat_cache[chat_id] = history
            

        user_msg_id = self.system_db.create_message(chat_id, "user", prompt)
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
            system_prompt="""
                In 5-20 words, create a summary of the chat so for.
                Add emoji(s) to the front of summary that best fit summary 
            """
            self.orchestrator.llm.generate(
                model_name="instruct",
                messages=messages,
                system_prompt=system_prompt,
                source="title"
            )
            self.orchestrator.llm.titleSignal.connect(on_title_results)
        def on_title_results(results):
            if results["success"]:
                self.system_db.edit_chat_title(results["text"], chat_id)
            else:
                print(f"Failed to generate title: {results["error"]}")
        
        threading.Thread(target=worker, daemon=True).start()

    def _maybe_summarize(self, messages: list):
        summary_settings = self.orchestrator.settings.get_settings()["summary_settings"]
        max_messages = summary_settings.get("max_message", 8)
        if(len(messages) < max_messages): return
        
        total_tokens = sum(
            self.orchestrator.llm.estimate_tokens(m["content"])
            for m in messages
        )
        threshold = summary_settings.get("summary_token_threshold", 2500)
        if total_tokens < threshold:
            return
        to_summarize = messages[:summary_settings.get("keep_fresh", 3)]

        return self._run_summary(to_summarize)

    def _run_summary(self, messages_to_summarize: list):
        from backend.ai.prompt_builder import PromptBuilder
        builder = PromptBuilder(self.orchestrator.llm, "instruct")
        builder.set_system_instructions("""
            Summarize the following conversation cleary and concisely.
            Preserve important facts, goals, decisions, and constraints.
            Do not invent information.
        """)
        builder.add_chat_history(messages_to_summarize)
        final_messages = builder.build(
            user_message="Create a memory summary of the above converstion"
        )
        self.orchestrator.llm.generate(
            model_name="instruct",
            messages=final_messages,
            system_prompt="",
            source="summary"
        )
        

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
            self._maybe_summarize(self.chat_cache[chat_id])
            self.chat_cache[chat_id].append(sys_msg)
            if(len(self.chat_cache[chat_id]) == 2):
                self._generate_title_async(self.chat_cache[chat_id], chat_id)
        
            self.messageFinished.emit({
                "success": True,
                "chat_id": chat_id,
                "text": text,
                "prompt_tokens": results["prompt_tokens"],
                "completion_tokens": results["completion_tokens"],
                "total_tokens": results["total_tokens"],
                "use_stream": results["use_stream"]
            })