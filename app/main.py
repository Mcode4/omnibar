import sys
import os
import yaml
from PySide6.QtWidgets import QApplication
from PySide6.QtQml import QQmlApplicationEngine
from backend.bridge import BackendBridge
from backend.db.user_db import UserDatabase as Database
from backend.db.system_db import SystemDatabase
from backend.ai.model_manager import ModelManager
from backend.settings import Settings
from backend.ai.llm_engine import LLMEngine
from backend.ai.embeddings_engine import EmbeddingEngine
from backend.ai.rag_pipeline import RAGPipeline
from backend.ai.orchestrator import Orchestrator
from backend.services.chat_service import ChatService
from backend.system.device_manager import DeviceManager
from backend.ai.vision_manager import VisionManager

# ============================================================
#                      LOADING YAML CONFIG
# ============================================================
DEFAULT_CONFIG_PATH = os.path.join("config", "models.yaml")
USER_CONFIG_PATH = os.path.expanduser("~/.local/share/omnimanager/models.yaml")

def load_config():
    # Priority: user config > default config
    path = USER_CONFIG_PATH if os.path.exists(USER_CONFIG_PATH) else DEFAULT_CONFIG_PATH
    with open(path, "r") as f:
        return yaml.safe_load(f)

config = load_config()

# ============================================================
#                      SYSTEM CONFIG
# ============================================================
device_setting = config.get("system", {}).get("device", "auto")
forced = None if device_setting == "auto" else device_setting

device_manager = DeviceManager(forced_device=forced)
device = device_manager.get_device()

# ============================================================
#                      APP
# ============================================================
app = QApplication(sys.argv)
current_tasks = { "ai": 0, "system": 0}

db_paths = config.get("databases", {})
system_db = SystemDatabase(db_paths.get("system", os.path.expanduser("~/.local/share/omnimanager/system.db")))
db = Database(db_paths.get("user", os.path.expanduser("~/.local/share/omnimanager/system.db")))

vision_manager = VisionManager(device)
model_manager = ModelManager(vision_manager)
model_manager.load_models_from_config(config)

settings = Settings(model_manager, config)
settings.load_settings()

llm_engine = LLMEngine(model_manager, settings)
embedding_engine = EmbeddingEngine(next((m for m in config.get("models", []) if m.get("backend") == "embedding"), None))
rag_pipeline = RAGPipeline(db, embedding_engine, settings)

orchestrator = Orchestrator(llm_engine, rag_pipeline, settings, system_db, user_db=db)
chat_service = ChatService(system_db, db, orchestrator)
bridge = BackendBridge(current_tasks, settings, chat_service)

engine = QQmlApplicationEngine()
engine.rootContext().setContextProperty("backend", bridge)
engine.rootContext().setContextProperty("settings", settings)

app.aboutToQuit.connect(bridge.shutdown)

qml_file = os.path.join(os.path.dirname(__file__), "ui", "main.qml")
engine.load(qml_file)


if not engine.rootObjects():
    sys.exit(-1)

sys.exit(app.exec())