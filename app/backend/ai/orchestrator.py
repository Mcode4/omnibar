import threading
from backend.ai.llm_engine import LLMEngine
from backend.ai.rag_pipeline import RAGPipeline
from backend.settings import Settings
from backend.databases.system_db import SystemDatabase
from backend.databases.user_db import UserDatabase

class Orchestrator:
    def __init__(self, llm_engine: LLMEngine, rag_pipeline: RAGPipeline, settings: Settings, system_db: SystemDatabase, user_db: UserDatabase):
        super().__init__()
        self.llm = llm_engine
        self.rag = rag_pipeline
        self.settings = settings
        self.system_db = system_db
        self.user_db = user_db

        self._pending_messages = None
        self._final_system_prompt = None

        self.llm.generation_finished.connect(self._handle_generation_finished)

    # ============================================================
    #                    PROMPT HANDLING
    # ============================================================
    def need_thinking(self, prompt: str) -> bool:
        trigger_words = [
            "think", "compare", "analyze", "design",
            "plan", "architecture", "why", "debug",
            "optimize", "how would", "can you",
            "how come", "understand", "vision", "image",
            "feel", "what is", "search", "results", "files",
            "name", "location", "address", "where", "who",
            "when", "time", "create", "detail", "specific",
            "depend", "depends", "detailed",
            "question", "predict", "prediction", "predictions", 
            "tell", "think", "check", "out of", "all of", "do you"
        ]

        word_count = len(prompt.split())
        question_count = 0

        if word_count > 40:
            return True
        
        if prompt.count("?") > 1:
            return True

        for word in trigger_words:
            if word in prompt.lower():
                return True
        return False
    
    def run(self, prompt: str, cached_history: list):
        system_tokens = self.llm.compute_budget("thinking")["system"]
        chat_tokens = self.llm.compute_budget("instruct")["chat"]

        messages = []
        for msg in cached_history:
            messages.append({
                "role": msg["role"],
                "content": msg["content"],
                "created_at": msg["created_at"]
            })

        if self.need_thinking(prompt):
            return self._thinking_flow(messages, system_prompt=f"Think step by step in under {system_tokens} tokens.")
        else: 
            return self._fast_flow(messages, system_prompt=f"Provide a clear and helpful message under {chat_tokens} tokens.") 
        

    # ============================================================
    #                    PROMPT TO AI
    # ============================================================
    def _fast_flow(self, messages: list, system_prompt="You are a helpful assistant.", source="chat"):
        self.llm.generate(
            model_name="instruct",
            messages=messages[-6:],
            system_prompt=system_prompt,
            source=source
        )
    
    def _thinking_flow(self, messages: list, system_prompt: str = "Think step by step before answering", system_prompt2: str = "Provide a clear structure answer.", source="chat"):
        self._pending_messages = messages
        self._final_system_prompt = system_prompt2
        
        self.llm.generate(
            model_name="thinking",
            messages=messages[-6:],
            system_prompt=system_prompt,
            phase="thinking",
            source=source
        )

    # ============================================================
    #                    THINKING PROMPT
    # ============================================================
    def _handle_generation_finished(self, phase, results, source="chat"):
        if not results["success"]:
            return
        
        if phase == "thinking":
            budget = self.llm.compute_budget("instruct")
            reasoning_text = results["text"][:budget["thinking"]]

            reasoning_text = results["text"]
            messages = []
            for m in self._pending_messages:
                message_token = 0 
                if self.llm.estimate_tokens(message_token + m["content"]) < budget["chat"]:
                    messages.append({"role": m["role", "content": m["content"]]})

            retrieved = self.rag.retrieve(messages)

            context = "\n\nRelevant Context:\n "
            if retrieved:
                rag_token_budget = budget["rag"]
                rag_tokens = 0
                for chunk in retrieved:
                    chunk_tokens = self.llm.estimate_tokens(chunk["text"])
                    if rag_tokens + chunk_tokens > rag_token_budget:
                        break
                    context += chunk["text"] + "\n"
                    rag_tokens += chunk_tokens

                for chunk in retrieved:
                    context += chunk["text"] + "\n"

            query_embedding = self.rag.embedding_engine.embed(
                messages[-1]["content"]
            )

            memories = self.user_db.search_memory_by_embedding(
                query_embedding,
                limit=3
            )

            memory_context = ""
            for m in memories:
                if self.llm.estimate_tokens(memory_context + m["content"]) < budget["memory"]:
                    memory_context += f"- {m['content']}\n"
            
            conversation_context = ""
            for m in messages:
                if self.llm.estimate_tokens(conversation_context + m["content"]) < budget["system"]:
                    conversation_context += f"{m['role']}: {m['content']}"

            final_prompt = f"""
            Long-Term Memory:
            {memory_context[:600]}

            Recent Conversation:
            {conversation_context}

            Key Reasoning:
            {reasoning_text}

            Relevant Context:
            {context}

            Provide a clear structured answer in under {self.settings.get_settings()["model_settings"]["instruct"].get("max_tokens", 512)} tokens.
            """
            print("\n--- FINAL PROMPT ---\n")
            print(final_prompt)
            print("\n--------------------\n")

            self.llm.generate(
                model_name="instruct",
                messages=[
                    {"role": "system", "content": final_prompt},
                    {"role": "user", "content": messages[-1]["content"]},
                ],
                system_prompt=self._final_system_prompt,
                source=source
            )