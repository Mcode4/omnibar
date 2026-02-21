from PySide6.QtCore import QObject, Signal
from backend.ai.model_manager import ModelManager
from backend.settings import Settings
from backend.tools.tool_registry import get_available_tools


class LLMEngine(QObject):
    tokenGenerated = Signal(str, str, int)
    generationFinished = Signal(str, dict, dict)

    modelThinking = Signal(int)
    modelTooling = Signal(int)

    titleSignal = Signal(dict, int)
    toolSignal = Signal(int, list)

    def __init__(self, model_manager: ModelManager, settings: Settings):
        super().__init__()
        self.model_manager = model_manager
        self.settings = settings

    def generate(self, model_name: str, messages: list, system_prompt: str, chat_id: int,  source: str, phase="instruct", past_transfer = None, tool_choice="auto"):
        # Label Signals
        if source == "tool": self.modelTooling.emit(chat_id)
        elif phase == "thinking": self.modelThinking.emit(chat_id)

        # Model Configurations
        model = self.model_manager.get_model(model_name)
        model_settings = self.settings.get_settings()["model_settings"][model_name]
        generate_settings = self.settings.get_settings()["generate_settings"]
        use_stream = generate_settings.get("streamer", True)

        # Prompt Trimming
        if system_prompt:
            messages = [{"role": "system", "content": system_prompt}] + messages

        messages = self.trim_messages_to_budget(messages, model_name)

        transfer = {
            "chat_id": chat_id,
            "phase": phase,
            "source": source,
            "messages": messages
        }
        if past_transfer:
            transfer = past_transfer

        # No Model Error Handling
        if not model:
            if source == "chat":
                self.generationFinished.emit(phase, {
                    "success": False, 
                    "error": "Model not loaded"
                }, transfer)
            elif source == "title":
                self.titleSignal.emit({
                    "success": False, 
                    "error": "Model not loaded"
                }, chat_id)
            elif source == "summary":
                self.generationFinished.emit({
                    "success": False, 
                    "error": "Model not loaded"
                }, transfer)
            else:
                print("Model not loaded from unknown source: ", source)
            return
        
        try:
            model.reset() # Model Reset For Multiple Prompts
            
            # Streaming Prompt. Exclused Non-Chat Prompts
            if use_stream and source in ("chat", "tool") and phase != "thinking":
                full_response = self._streaming_generation(
                    model=model, 
                    model_settings=model_settings, 
                    messages=messages, 
                    phase=phase, 
                    chat_id=chat_id, 
                    tool_choice=tool_choice
                )
            else:
                full_response = self._default_generation(
                    model=model, 
                    model_settings=model_settings, 
                    messages=messages,  
                    chat_id=chat_id, 
                    tool_choice=tool_choice
                )

            if full_response is None:
                return

            prompt_text = "".join(m["content"] for m in messages)
            prompt_tokens = self.estimate_tokens(prompt_text)
            completion_tokens = self.estimate_tokens(full_response)

            results = {
                "success": True,
                "text": full_response.strip() if phase != "tool" else "Results: " + full_response.strip(),
                "prompt_tokens": prompt_tokens,
                "completion_tokens": completion_tokens,
                "total_tokens": prompt_tokens + completion_tokens,
                "use_stream": use_stream
            }

        except Exception as e:
            results = {
                "success": False,
                "error": str(e)
            }

        # Result Designations
        if source == "chat":
            self.generationFinished.emit(phase, results, transfer)
        elif source == "title":
            self.titleSignal.emit(results, chat_id)
        elif source == "summary":
            self.generationFinished.emit(source, results, transfer)
        elif source == "tool":
            self.generationFinished.emit(source, results, transfer)
        else:
            print("UNKNOWN SOURCE: ", source)

    # ============================================================
    #                    LLM GENERATION FUNCTIONS
    # ============================================================
    def _streaming_generation(self, model, model_settings, messages, phase, chat_id, tool_choice):
        full_response = ""
        tool_calls_buffer = {}

        for chunk in model.create_chat_completion(
            messages=messages,
            max_tokens=model_settings.get("max_tokens", 512),
            temperature=model_settings.get("temperature", 0.1),
            top_k=model_settings.get("top_k", 50),
            top_p=model_settings.get("top_p", 0.1),
            min_p=model_settings.get("min_p", 0.2),
            repeat_penalty=model_settings.get("repetition_penalty", 1.05),
            mirostat_mode=model_settings.get("mirostat_mode", 0),
            stream=True,
            tools=get_available_tools(),
            tool_choice=tool_choice
        ):
            delta = chunk["choices"][0]["delta"] # Streaming Chunk

            # Chunk Deciphering
            if "content" in delta:
                token = delta["content"]
                full_response += token
                print(f"\nSTREAMING, PHASE:{phase}, TOKEN:{token}, CHAT ID:{chat_id}")
                self.tokenGenerated.emit(phase, token, chat_id)

            if "tool_calls" in delta:
                for tool_delta in delta["tool_calls"]:
                    index = tool_delta["index"]

                    if index not in tool_calls_buffer:
                        tool_calls_buffer[index] = {
                            "id": tool_delta.get("id"),
                            "function": {
                                "name": "",
                                "arguments": ""
                            }
                        }
                    if "function" in tool_delta:
                        fn = tool_delta["function"]
                        if "name" in fn:
                            tool_calls_buffer[index]["function"]["name"] = fn["name"]
                        if "arguments" in fn:
                            tool_calls_buffer[index]["function"]["arguments"] += fn["arguments"]

        # After Deciphering Chunks. If Tool Call 
        if tool_calls_buffer:
            tool_calls = list(tool_calls_buffer.values())
            print("\n\n\n\n\nTOOL CALLED: ", tool_calls, "\n\n\n\n\n")
            self.toolSignal.emit(chat_id, tool_calls)
            return None
        return full_response
    
    def _default_generation(self, model, model_settings, messages, chat_id, tool_choice):
        output = model.create_chat_completion(
            messages=messages,
            max_tokens=model_settings.get("max_tokens", 512),
            temperature=model_settings.get("temperature", 0.1),
            top_k=model_settings.get("top_k", 50),
            top_p=model_settings.get("top_p", 0.1),
            min_p=model_settings.get("min_p", 0.2),
            repeat_penalty=model_settings.get("repetition_penalty", 1.05),
            mirostat_mode=model_settings.get("mirostat_mode", 0),
            stream=False,
            tools=get_available_tools(),
            tool_choice=tool_choice
        )
        
        message = output["choices"][0]["message"]
        # If Tool Call
        if "tool_calls" in message:
            tool_calls = message["tool_calls"]
            print("\n\n\n\n\nTOOL CALLED: ", tool_calls, "\n\n\n\n\n")
            self.toolSignal.emit(chat_id, tool_calls)
            return None

        full_response = message["content"]
        return full_response
        
    # ============================================================
    #                    TOKEN HANDLING
    # ============================================================
    def estimate_tokens(self, text: str) -> int:
        return int(len(text.split()) * 1.3)
    
    def trim_messages_to_budget(self, messages, model_name):
        model_settings = self.settings.get_settings()["model_settings"][model_name]
        max_context = model_settings.get("max_content", 4096)
        max_tokens = model_settings.get("max_tokens", 1024)

        # print("TRIMMING", {
        #     "mesages": messages,
        #     "max_context": max_context,
        #     "max_tokens": max_tokens
        # })
        budget = max_context - max_tokens
        total = 0

        trimmed = []

        for msg in reversed(messages):
            tokens = self.estimate_tokens(msg["content"])
            if total + tokens > budget:
                break
            trimmed.append(msg)
            total += tokens

        # print("TRIMMED", trimmed)
        return list(reversed(trimmed))
    
    def compute_budget(self, model_name):
        model_settings = self.settings.get_settings()["model_settings"][model_name]
        max_context = model_settings.get("max_context", 4096)
        max_tokens = model_settings.get("max_tokens", 512)
        available = max_context - max_tokens

        return {
            "system": int(available * 0.05),
            "chat": int(available * 0.35),
            "rag": int(available * 0.25),
            "memory": int(available * 0.15),
            "thinking": int(available * 0.15),
            "total_input_budget": int(available)
        }
    
