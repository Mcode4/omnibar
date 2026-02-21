from PySide6.QtCore import Signal, QObject
from backend.databases.system_db import SystemDatabase
from backend.ai.orchestrator import Orchestrator

class ChatService(QObject):
    chatCreated = Signal(int, str)

    def __init__(self, system_db: SystemDatabase, orchestrator: Orchestrator):
        super().__init__()
        self.system_db = system_db
        self.orchestrator = orchestrator
        self.chat_cache = {}

        self.orchestrator.llm.titleSignal.connect(self.on_title_results)

    # ============================================================
    #                    PROMPT HANDLING
    # ============================================================
    def send_message(self, chat_id, prompt):
        if not chat_id or chat_id <= 0:
            chat_id = self.system_db.create_chat(prompt[:25])
            self.chatCreated.emit(chat_id, prompt[:25])

        user_msg_id = self.system_db.create_message(chat_id, "user", prompt)
        user_msg = self.system_db.get_message_by_id(user_msg_id)

        print("PREVIOUS CACHE:", self.chat_cache.get(chat_id, {}))
        history = self.system_db.get_messages_by_chat(chat_id)
        if chat_id in self.chat_cache:
            self.chat_cache[chat_id].append(user_msg)
        else:
            self.chat_cache[chat_id] = list(history)

        print("SEND MESSAGE IMPORTANCES: ", {
            "chat_cache": self.chat_cache,
            "chat_id": chat_id,
            "history": history
        })

        self.orchestrator.run(prompt, self.chat_cache[chat_id], chat_id=chat_id)

    # ============================================================
    #                    CACHING
    # ============================================================
    def get_messages(self, chat_id: int):
        if not chat_id:
            print("no chat_id")
        return self.chat_cache.get(chat_id, [])

    def append_message(self, chat_id: int, message: dict):
        if message:
            if not chat_id:
                print("no chat_id")
            else:
                self.system_db.create_message(chat_id, message["role"], message.get("content", ""))
                if chat_id not in self.chat_cache:
                    self.chat_cache[chat_id] = []
                self.chat_cache[chat_id].append(message)
        return self.chat_cache[chat_id]

    # ============================================================
    #                    ASSISTING CHAT WITH AI
    # ============================================================
    # def _generate_title(self, messages, chat_id):
    #     system_prompt="""
    #         In 5-20 words, create a summary of the chat so for.
    #         Add emoji(s) to the front of summary that best fit summary 
    #     """
    #     self.orchestrator.llm.generate(
    #         chat_id=chat_id,
    #         model_name="instruct",
    #         messages=messages,
    #         system_prompt=system_prompt,
    #         source="title"
    #     )

    def _maybe_summarize(self, messages: list, transfer):
        summary_settings = self.orchestrator.settings.get_settings()["summary_settings"]
        max_messages = summary_settings.get("max_message", 8)
        keep_fresh = summary_settings.get("keep_fresh", 3)
        if(len(messages) < max_messages): return
        
        total_tokens = sum(
            self.orchestrator.llm.estimate_tokens(m["content"])
            for m in messages
        )
        threshold = summary_settings.get("summary_token_threshold", 2500)
        if total_tokens < threshold:
            return
        to_summarize = messages[:-keep_fresh]

        return self.orchestrator.generate_summary(to_summarize, transfer)

    # def _run_summary(self, messages_to_summarize: list, transfer):
    #     from backend.ai.prompt_builder import PromptBuilder
    #     builder = PromptBuilder(self.orchestrator.llm, "instruct")
    #     builder.set_system_instructions("""
    #         Summarize the following conversation cleary and concisely.
    #         Preserve important facts, goals, decisions, and constraints.
    #         Do not invent information.
    #     """)
    #     builder.add_chat_history(messages_to_summarize)
    #     final_messages = builder.build(
    #         user_message="Create a memory summary of the above converstion"
    #     )
    #     self.orchestrator.llm.generate(
    #         chat_id=transfer["chat_id"],
    #         model_name="instruct",
    #         messages=final_messages,
    #         system_prompt="",
    #         source="summary",
    #         past_transfer=transfer,
    #     )

    def add_summary(self, summary, transfer):
        summary_settings = self.orchestrator.settings.get_settings()["summary_settings"]
        keep_fresh = summary_settings.get("keep_fresh", 3)

        chat_id = transfer["chat_id"]

        summarized_cache = self.chat_cache[chat_id][-keep_fresh:]
        summarized_cache.append({
            "role": "system",
            "content": summary
        })
        print(f"\n\n\nCHAT CACHE: {self.chat_cache}\n SUMMARIZED CACHE: {summarized_cache}\n\n\n")
        self.chat_cache[chat_id] = summarized_cache
        return
    
    def on_title_results(self, results, chat_id):
        if results["success"]:
            self.system_db.edit_chat_title(results["text"], chat_id)
        else:
            print(f"Failed to generate title: {results["error"]}")

    # ============================================================
    #                    TOKEN HANDLING FOR STREAMING
    # ============================================================
    # def _handle_token(self, phase, token, chat_id):
    #     print(f"STREAMING, TOKEN:{token}, CHAT ID:{chat_id}")
    #     self.tokenGenerated.emit(phase, token, chat_id)

    def cache_response(self, text, transfer):
        chat_id = transfer["chat_id"]
        chat_cache = self.chat_cache[chat_id]

        sys_msg_id = self.system_db.create_message(chat_id, "assistant", text)
        sys_msg = self.system_db.get_message_by_id(sys_msg_id)
        chat = self.system_db.get_chat_by_id(chat_id)

        chat_cache.append(sys_msg)
        self._maybe_summarize(chat_cache, transfer)
        if len(chat_cache) == 6 and not chat["has_title"]:
            self.orchestrator.generate_title(chat_cache, chat_id)
        return

    