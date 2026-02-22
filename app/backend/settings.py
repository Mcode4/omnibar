import os
import json
from PySide6.QtCore import QObject, Slot, Signal

class Settings(QObject):
    settingsChanged = Signal()
    unsavedChanges = Signal(bool)

    def __init__(self, model_manager, config, system_db):
        super().__init__()
        self.model_manager = model_manager
        self.config = config
        self.db = system_db

        self._settings = {
            "user_settings": {
                "name": "Mcode4",
                "timezone": "UTC",
                "primary_language": "English"
            },
            "model_settings": {
                "thinking": {
                    "enabled": True,
                    "max_tokens": 1024,
                    "max_context": 4096,
                    "temperature": 0.3,
                    "top_k": 50,
                    "top_p": 0.9,
                    "min_p": 0.2,
                    "repetition_penalty": 2,
                    "mirostat_mode": 2
                },
                "instruct": {
                    "max_tokens": 1024,
                    "max_context": 4096,
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
                "use_emojis": False, # Planned
                # "stream_when": "thinking, instruct, or both"
            },
            "rag_settings": {
                "enabled": True,
                "weight": 0.7,
                "rerank": True,
                "min_score": 0.3
            },
            "embedding_settings": {
                "enabled": True,
                "top_max_embedding_scan": 5,
                "chunk_size": 512,
                "overlap": 50
            },
            "max_tasks": {
                "ai_tasks": 3,
                "system_tasks": 2,
                "async_tasks": 1
            },
            "summary_settings": {
                "max_messages": 8,
                "keep_fresh": 3, # Out of "max_message" keep (amount) fresh
                "summary_token_threshold": 2500
            },
            "tool_settings": {
                "search_files": {
                    "active": True,
                    "max_results": 10,
                    "search_path": os.path.expanduser("~"),
                    "restricted_paths": [],
                    "max_file_size_mb": 20,
                    "can_search_sub_directories": True
                },
                "web_search": {
                    "active": True,
                    "live_view": True
                }
            },
            "ui": {
                "theme": "light", # light mode
                "font-size": 14,
                "markdown": True
            },
            "error_popups": True,
            "debug": {
                "log_phases": True,
                "log_tokens": True,
                "log_rag": True,
                "log_tools": True,
                "save_log_to_file": False,
                "log_file_location": ""
            }
        }

        self._pending_changes = {}

    def get_settings(self):
        return self._settings

    def load_settings(self):
        raw = self.db.get_setting("settings_json")
        if not raw:
            return
        loaded = json.loads(raw)
        self.settingsChanged.emit()
        return self._deep_update(self._settings, loaded)
    
    def _deep_update(self, base, updates):
        for key, value in updates.items():
            if isinstance(value, dict) and key in base:
                self._deep_update(base[key], value)
            else:
                base[key] = value

    def save_settings(self):
        if self._pending_changes:
            for path, value in self._pending_changes.items():
                self._set(path, value)

            self.db.set_settings("settings_json", json.dumps(self._settings))
            self._pending_changes.clear()
            self.settingsChanged.emit()
            self.unsavedChanges.emit(False)
        return
    
    @Slot(str, result="QVariant")
    def get(self, path):
        keys = path.split(".")
        value = self._settings
        for key in keys:
            value = value.get(key, None)
            if value is None:
                return None
        return value
    
    @Slot(str, "QVariant")
    def pre_set(self, path, value):
        self._pending_changes[path] = value
        self.unsavedChanges.emit(True)
    
    @Slot(str, "QVariant")
    def _set(self, path, value):
        keys = path.split(".")
        ref = self._settings
        for key in keys[:-1]:
            ref = ref.setdefault(key, {})
        ref[keys[-1]] = value
        return

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
