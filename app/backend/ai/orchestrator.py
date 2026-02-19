import threading
from backend.ai.llm_engine import LLMEngine
from backend.ai.rag_pipeline import RAGPipeline
from backend.settings import Settings
from backend.databases.system_db import SystemDatabase
from backend.databases.user_db import UserDatabase
from backend.ai.prompt_builder import PromptBuilder
from backend.ai.identity_manager import IdentityManager

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
        identity = IdentityManager()
        identity_text = identity.get_identity()
        self.llm.generate(
            model_name="instruct",
            messages=messages[-6:],
            system_prompt=identity.get_identity() + "\n" + system_prompt,
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
    def _handle_generation_finished(self, phase, results):
        if not results["success"]:
            return
        
        if phase == "summary":
            if not results["sucess"]:
                print(f"\n\nSUMMARY FAILED: {results["error"]}\n\n")
                return
            summary_text = results["text"]
            if summary_text.strip():
                embedding = self.rag.embedding_engine.embed(summary_text)
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
        
        if phase == "thinking":
            reasoning_text = results["text"]
            identity = IdentityManager()
            builder = PromptBuilder(self.llm, "instruct", identity_text=identity.get_identity())
            builder.set_system_instructions(
                f"Provide a clear, structed answer in under "
                f"{self.settings.get_settings()["model_settings"]["instruct"]["max_tokens"]} tokens."
                f"Do not halllucinate. {self._final_system_prompt}"
            )

            # Chat history
            builder.add_chat_history(self._pending_messages)

            # RAG
            retrieved = self.rag.retrieve(self._pending_messages)
            if retrieved:
                builder.add_rag(chunk["text"] for chunk in retrieved)

            # Memory
            query_embedding = self.rag.embedding_engine.embed(
                self._pending_messages[-1]["content"]
            )
            summary_memories = self.user_db.search_memory_by_embedding(
                query_embedding,
                limit=2,
                type_filter="summary"
            )
            fact_memories = self.user_db.search_memory_by_embedding(
                query_embedding,
                limit=3,
                type_filter="fact"
            )
            builder.add_memory([m["content"] for m in summary_memories + fact_memories])
            
            # Reasoning
            builder.set_reasoning(reasoning_text)

            final_messages = builder.build(
                user_message=self._pending_messages[-1]["content"]
            )

            self.llm.generate(
                model_name="instruct",
                messages=final_messages,
                system_prompt="",
                source="chat"
            )