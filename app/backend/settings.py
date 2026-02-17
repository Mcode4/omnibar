from PySide6.QtCore import QObject, Slot

class Settings(QObject):
    def __init__(self, model_manager, config):
        super().__init__()
        self.model_manager = model_manager
        self.config = config

        self._settings = {
            "model_settings": {
                "thinking": {
                    "enabled": True,
                    "max_tokens": 1024,
                    "max_context": 1024,
                    "temperature": 0.3,
                    "top_k": 50,
                    "top_p": 0.9,
                    "min_p": 0.2,
                    "repetition_penalty": 2,
                    "mirostat_mode": 2
                },
                "instruct": {
                    "max_tokens": 1024,
                    "max_context": 1024,
                    "temperature": 0.25,
                    "top_k": 50,
                    "top_p": 0.9,
                    "min_p": 0.2,
                    "repetition_penalty": 1.5,
                    "mirostat_mode": 0
                }
            },
            "generate_settings": {
                "streamer": True,
                "stream_when": "both",
                "use_md": True,
                "use_emojis": False, # Planned
                # "stream_when": "thinking, instruct, or both"
            },
            "embedding_settings": {
                "top_max_embedding_scan": 5,
                "chunk_size": 512,
                "overlap": 50
            },
            "max_tasks": {
                "ai_tasks": 3,
                "system_tasks": 2,
                "async_tasks": 1
            },
            "max_messages": 12,
            "summarize_messages": True,
            "error_popups": True
        }

    def load_settings(self):
        # Cleanly access db and load all saved setting values
        return
    
    def get_settings(self):
        return self._settings

    @Slot(str, bool)
    def toggle_model(self, model_name: str, enabled: bool):
        if enabled:
            model_info = next((m for m in self.config.get("models", []) if m["name"] == model_name), None)
            if model_info:
                backend = model_info.get("backend", "llama-cpp")
                path = model_info["model"]
                model_type = "llama" if backend == "llama-cpp" else backend
                params = model_info.get("parameters", {})

                self.model_manager.load_model(
                    name=model_name,
                    path=path,
                    model_type=model_type,
                    **params
                )
        else:
            self.model_manager.unload_model(model_name)
