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
        
        model_settings = self.settings.get_settings()["model_settings"].get(model_name, {})
        generate_settings = self.settings.get_settings()["generate_settings"]
        use_stream = generate_settings.get("streamer", True)
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
 
            prompt_tokens = len(messages)
            completion_tokens = len(full_response.split())

            results = {
                "success": True,
                "text": full_response.strip(),
                "prompt_tokens": prompt_tokens,
                "completion_tokens": completion_tokens,
                "total_tokens": prompt_tokens + completion_tokens
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
        
