from PySide6.QtCore import QObject, Signal
from backend.ai.model_manager import ModelManager
from backend.settings import Settings

class LLMEngine(QObject):
    token_generated = Signal(str, str)
    generation_finished = Signal(str, dict)
    titleSignal = Signal(dict)
    summarySignal = Signal(dict)

    def __init__(self, model_manager: ModelManager, settings: Settings):
        super().__init__()
        self.model_manager = model_manager
        self.settings = settings

    def generate(self, model_name: str, messages: list, system_prompt: str, source: str, phase="instruct"):
        model = self.model_manager.get_model(model_name)
        model_settings = self.settings.get_settings()["model_settings"]
        generate_settings = self.settings.get_settings()["generate_settings"]
        use_stream = generate_settings.get("streamer", True)

        messages = self.trim_messages_to_budget(
            messages,
            system_prompt,
            max_context = model_settings[model_name].get("max_context", 4096),
            max_tokens = model_settings[model_name].get("max_tokens", 512)
        )

        if not model:
            if source == "chat":
                self.generation_finished.emit(phase, {
                    "success": False, 
                    "error": "Model not loaded"
                })
            elif source == "title":
                self.titleSignal.emit({
                    "success": False, 
                    "error": "Model not loaded"
                })
            elif source == "summary":
                self.summarySignal.emit({
                    "success": False, 
                    "error": "Model not loaded"
                })
            else:
                print("Model not loaded from unknown source: ", source)
            return
        
        try:
            model.reset()
            # self.model_manager.reload_model(model_name, n_ctx=max_context)
            if use_stream and source == "chat":
                full_response = ""

                for chunk in model.create_chat_completion(
                    messages=messages,
                    max_tokens=model_settings.get("max_tokens", 512),
                    temperature=model_settings.get("temperature", 0.1),
                    top_k=model_settings.get("top_k", 50),
                    top_p=model_settings.get("top_p", 0.1),
                    min_p=model_settings.get("min_p", 0.2),
                    repeat_penalty=model_settings.get("repetition_penalty", 1.05),
                    mirostat_mode=model_settings.get("mirostat_mode", 0),
                    stream=True
                ):
                    delta = chunk["choices"][0]["delta"]
                    if "content" in delta:
                        token = delta["content"]
                        full_response += token
                        self.token_generated.emit(phase, token)
            else:
                output = model.create_chat_completion(
                    messages=messages,
                    max_tokens=model_settings.get("max_tokens", 512),
                    temperature=model_settings.get("temperature", 0.1),
                    top_k=model_settings.get("top_k", 50),
                    top_p=model_settings.get("top_p", 0.1),
                    min_p=model_settings.get("min_p", 0.2),
                    repat_penalty=model_settings.get("repetition_penalty", 1.05),
                    mirostat_mode=model_settings.get("mirostat_mode", 0),
                    stream=False
                )
                full_response = output["choices"][0]["message"]["content"]
 
            prompt_tokens = self.estimate_tokens(m["content"] for m in messages)
            completion_tokens = self.estimate_tokens(full_response)

            results = {
                "success": True,
                "text": full_response.strip(),
                "prompt_tokens": prompt_tokens,
                "completion_tokens": completion_tokens,
                "total_tokens": prompt_tokens + completion_tokens,
                "no_stream": True
            }

        except Exception as e:
            results = {
                "success": False,
                "error": str(e)
            }
        if source == "chat":
            self.generation_finished.emit(phase, results)
        elif source == "title":
            self.titleSignal.emit(results)
        elif source == "summary":
            self.summarySignal.emit(results)
        else:
            print("UNKNOWN SOURCE: ", source)
        
    # ============================================================
    #                    TOKEN HANDLING
    # ============================================================
    def estimate_tokens(self, text: str) -> int:
        return int(len(text.split()) * 1.3)
    
    def trim_messages_to_budget(self, messages, system_propmt, max_context, max_tokens):
        budget = max_context - max_tokens
        total = self.estimate_tokens(system_propmt)

        trimmed = []

        for msg in reversed(messages):
            tokens = self.estimate_tokens(msg["content"])
            if total + tokens > budget:
                break
            trimmed.insert(0, msg)
            total += tokens

        return trimmed
    
    def compute_budget(self, model_name):
        settings = self.settings.get_settings()["model_settings"][model_name]
        context_size = settings.get("content_size", 4096)
        max_output = settings.get("max_token", 512)
        available = context_size - max_output

        return {
            "system": int(available * 0.05),
            "chat": int(available * 0.35),
            "rag": int(available * 0.25),
            "memory": int(available * 0.15),
            "thinking": int(available * 0.15),
            "total_input_budget": int(available)
        }
    
