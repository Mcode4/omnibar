from backend.ai.llm_engine import LLMEngine
from backend.ai.identity_manager import IdentityManager

class PromptBuilder:
    def __init__(self, llm_engine: LLMEngine, model_name: str, identity_text: str = ""):
        self.llm = llm_engine
        self.model_name = model_name
        self.budget = self.llm.compute_budget(model_name)
        self.identity_text = identity_text

        self._memory_blocks = []
        self._rag_blocks = []
        self._chat_messages = []
        self._reasoning = ""
        self._system_instruction = ""

    # ============================================================
    #                    SYSTEM
    # ============================================================
    def set_system_instructions(self, text: str):
        instructions = text.strip()
        if not instructions.endswith((".", "?", "!")):
            instructions += "."
        self._system_instruction = instructions

    # ============================================================
    #                    MEMORY
    # ============================================================
    def add_memory(self, memories: list):
        token_used = 0
        for m in memories:
            tokens = self.llm.estimate_tokens(m)
            if token_used + tokens > self.budget["memory"]:
                break
            self._memory_blocks.append(m)
            token_used += tokens

    # ============================================================
    #                    RAG
    # ============================================================
    def add_rag(self, rag_chunks: list):
        token_used = 0
        for chunk in rag_chunks:
            tokens = self.llm.estimate_tokens(chunk)
            if token_used + tokens > self.budget["rag"]:
                break
            self._rag_blocks.append(chunk)
            token_used += tokens

    # ============================================================
    #                    CHAT HISTORY
    # ============================================================
    def add_chat_history(self, messages: list):
        token_used = 0
        trimmed = []
        for m in reversed(messages):
            tokens = self.llm.estimate_tokens(m["content"])
            if token_used + tokens > self.budget["chat"]:
                break
            trimmed.insert(0, m)
            token_used += tokens

        self._chat_messages = trimmed

    # ============================================================
    #                    REASONING
    # ============================================================
    def set_reasoning(self, reasoning_text: str):
        self._reasoning = reasoning_text[: self.budget["thinking"]]

    # ============================================================
    #                    BUILD
    # ============================================================
    def build(self, user_message: str):
        system_sections = []

        if self.identity_text:
            system_sections.append(self.identity_text)

        if self._memory_blocks:
            system_sections.append(
                "Long-Term Memory:\n" +
                "\n".join(f"- {m}" for m in self._memory_blocks)
            )
        if self._rag_blocks:
            system_sections.append(
                "Relevant Context:\n" +
                "\n".join(self._rag_blocks)
            )
        if self._reasoning:
            system_sections.append(
                "Internal Reasoning:\n" + self._reasoning
            )

        system_text = "\n\n".join(system_sections)
        if self._system_instruction:
            system_text = self._system_instruction + "\n\n" + system_text

        messages = []
        if system_text.strip():
            messages.append({
                "role": "system",
                "content": system_text.strip()
            })
        messages.extend(self._chat_messages)
        messages.append({
            "role": "user",
            "content": user_message
        })

        return messages
