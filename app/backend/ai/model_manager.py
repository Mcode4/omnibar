import os
from backend.ai.vision_manager import VisionManager
from backend.settings import Settings

class ModelManager:
    def __init__(self, vision_manager: VisionManager, settings: Settings):
        self.models = {}
        self.templates = {}
        self.active_models = set()
        self.vision_model = vision_manager
        self.settings = settings

    def get_model(self, model_name):
        if not model_name in self.active_models:
            return
        return self.models[model_name]

    # ============================================================
    #                    MODEL LOADING
    # ============================================================
    def load_model(self, name: str, path: str, model_type="llama", **kwargs):
        if name in self.models:
            print(f"{name} already loaded")
            return self.models[name]
        
        if model_type == "llama":
            import llama_cpp
            model = llama_cpp.Llama(
                model_path=path, n_ctx=self.settings.get_settings()["model_settings"][name].get("max_context", 4096),
            **kwargs)
        elif model_type == "vision":
            self.vision_model.load(path)
            model = self.vision_model.model
        elif model_type == "embedding":
            from sentence_transformers import SentenceTransformer
            model = SentenceTransformer(path)
        else:
            raise ValueError("Unknown model type:", {name, model_type, path})
        
        self.templates[name] = (path, model_type)
        self.models[name] = model
        self.active_models.add(name)
        print(f"{name} loaded")
        return model
    
    def reload_model(self, model_name, **kwargs):
        if not self.models[model_name]:
            print(f"Model: {model_name} isn't loaded")
            return
        
        print(f'KWARGS {kwargs}')
        self.unload_model(model_name)
        print(f"ACTIVE MODELS: {self.active_models}")

        path, model_type = self.templates[model_name]
        self.load_model(model_name, path, model_type, **kwargs)
        print("Reload successful")
    
    def unload_model(self, name: str):
        # Unload model to free RAM
        if name in self.models:
            del self.models[name]
            self.active_models.discard(name)
            print(f"{name} unloaded")
    
    def load_models_from_config(self, config, base_path="models"):
        for m in config.get("models", []):
            name = m["name"]
            backend = m.get("backend", "llama-cpp")
            model_path = m["model"]

            params = m.get("parameters", {})

            model_type = "llama" if backend == "llama-cpp" else backend
            self.load_model(name, path=model_path, model_type=model_type, **params)
