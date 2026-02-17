import threading
from backend.ai.llm_engine import LLMEngine
from backend.ai.rag_pipeline import RAGPipeline
from backend.settings import Settings
from backend.db.system_db import SystemDatabase
from backend.db.user_db import UserDatabase

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
        messages = []
        for msg in cached_history:
            messages.append({
                "role": msg["role"],
                "content": msg["content"],
                "created_at": msg["created_at"]
            })

        if self.need_thinking(prompt):
            return self._thinking_flow(messages)
        else: 
            return self._fast_flow(messages) 
        

    # ============================================================
    #                    PROMPT TO AI
    # ============================================================
    def _fast_flow(self, messages: list, system_prompt="You are a helpful assistant"):
        self.llm.generate(
            model_name="instruct",
            messages=messages,
            system_prompt=system_prompt
        )
    
    def _thinking_flow(self, messages: list, system_prompt: str = "Think step by step before answering", system_prompt2: str = "Provide a clear structure answer."):
        self._pending_messages = messages
        self._final_system_prompt = system_prompt2
        
        self.llm.generate(
            model_name="thinking",
            messages=messages,
            system_prompt=system_prompt,
            phase="thinking"
        )

    # ============================================================
    #                    THINKING PROMPT
    # ============================================================
    def _handle_generation_finished(self, phase, results):
        if not results["success"]:
            return
        
        if phase == "thinking":
            reasoning_text = results["text"]
            messages = self._pending_messages

            retrieved = self.rag.retrieve(messages)

            context = ""
            if retrieved:
                context = "\n\nRelevant Context:\n"
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
                memory_context += f"- {m['content']}\n"

            final_prompt = f"""
            Relevant Long-Term Memory: {memory_context}
            User Messages: {messages}
            Reasoning: {reasoning_text}
            {context}
            Provide a final clear answer.
            """

            print("\n--- FINAL PROMPT ---\n")
            print(final_prompt)
            print("\n--------------------\n")

            self.llm.generate(
                model_name="instruct",
                messages=[{"role": "system", "content": final_prompt}],
                system_prompt=self._final_system_prompt
            )