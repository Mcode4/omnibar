import sys
import os
import yaml
import importlib
import argparse

from PySide6.QtWidgets import QApplication
from PySide6.QtQml import QQmlApplicationEngine
from PySide6.QtCore import QFileSystemWatcher, QUrl

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
# ARG PARSER
# ============================================================
parser = argparse.ArgumentParser()
parser.add_argument("--dev", "--d", "--dev-mode", action="store_true")
args = parser.parse_args()

# ============================================================
# DEV MODE
# ============================================================
DEV_MODE = args.dev

# ============================================================
# LOADING YAML CONFIG
# ============================================================
DEFAULT_CONFIG_PATH = os.path.join("config", "models.yaml")
USER_CONFIG_PATH = os.path.expanduser("~/.local/share/omnimanager/models.yaml")

def load_config():
    path = USER_CONFIG_PATH if os.path.exists(USER_CONFIG_PATH) else DEFAULT_CONFIG_PATH
    with open(path, "r") as f:
        return yaml.safe_load(f)

config = load_config()


# ============================================================
# SYSTEM CONFIG
# ============================================================
device_setting = config.get("system", {}).get("device", "auto")
forced = None if device_setting == "auto" else device_setting

device_manager = DeviceManager(forced_device=forced)
device = device_manager.get_device()


# ============================================================
# APP INIT
# ============================================================
app = QApplication(sys.argv)
engine = QQmlApplicationEngine()

qml_file = os.path.join(os.path.dirname(__file__), "ui", "main.qml")

# Global references (important for hot reload)
current_tasks = {"ai": 0, "system": 0}
system_db = None
db = None
vision_manager = None
model_manager = None
settings = None
llm_engine = None
embedding_engine = None
rag_pipeline = None
orchestrator = None
chat_service = None
bridge = None


# ============================================================
# BACKEND CREATION (Reusable for hot reload)
# ============================================================
def create_backend():
    global system_db, db
    global vision_manager, model_manager, settings
    global llm_engine, embedding_engine, rag_pipeline
    global orchestrator, chat_service, bridge

    print("🚀 Creating backend...")

    db_paths = config.get("databases", {})
    system_db = SystemDatabase(
        db_paths.get("system", os.path.expanduser("~/.local/share/omnimanager/system.db"))
    )
    db = Database(
        db_paths.get("user", os.path.expanduser("~/.local/share/omnimanager/system.db"))
    )

    vision_manager = VisionManager(device)

    model_manager = ModelManager(vision_manager)
    model_manager.load_models_from_config(config)

    settings = Settings(model_manager, config)
    settings.load_settings()

    llm_engine = LLMEngine(model_manager, settings)

    embedding_engine = EmbeddingEngine(
        next((m for m in config.get("models", []) if m.get("backend") == "embedding"), None)
    )

    rag_pipeline = RAGPipeline(db, embedding_engine, settings)

    orchestrator = Orchestrator(
        llm_engine, rag_pipeline, settings, system_db, user_db=db
    )

    chat_service = ChatService(system_db, db, orchestrator)

    # Shutdown old bridge if exists
    if bridge:
        try:
            bridge.shutdown()
        except Exception:
            pass

    bridge = BackendBridge(current_tasks, settings, chat_service)

    engine.rootContext().setContextProperty("backend", bridge)
    engine.rootContext().setContextProperty("settings", settings)

    print("✅ Backend ready")


# ============================================================
# QML LOAD / RELOAD
# ============================================================
def load_qml():
    engine.load(QUrl.fromLocalFile(qml_file))


def reload_qml():
    print("🔄 Reloading QML...")
    engine.clearComponentCache()

    for obj in engine.rootObjects():
        obj.deleteLater()

    load_qml()


# ============================================================
# BACKEND RELOAD (DEV MODE)
# ============================================================
def reload_backend():
    print("🔄 Reloading backend (no window restart)...")

    # Reload backend package safely
    import backend
    importlib.reload(backend)

    create_backend()


# ============================================================
# INITIAL STARTUP
# ============================================================
create_backend()
load_qml()

app.aboutToQuit.connect(lambda: bridge.shutdown())


# ============================================================
# DEV MODE FILE WATCHER
# ============================================================
if DEV_MODE:
    print("🟢 DEV MODE ENABLED")

    watcher = QFileSystemWatcher()
    files_to_watch = []

    project_root = os.path.dirname(os.path.abspath(__file__))

    for root, _, files in os.walk(project_root):
        for f in files:
            if f.endswith((".py", ".qml")):
                files_to_watch.append(os.path.join(root, f))

    watcher.addPaths(files_to_watch)

    def on_file_changed(path):
        print(f"⚡ File changed: {path}")

        if path.endswith(".py"):
            reload_backend()
        elif path.endswith(".qml"):
            reload_qml()

    watcher.fileChanged.connect(on_file_changed)
    watcher.directoryChanged.connect(on_file_changed)


# ============================================================
# RUN APPLICATION
# ============================================================
exit_code = app.exec()

if DEV_MODE:
    print("🔄 main.py exited (DEV mode)")
else:
    if not engine.rootObjects():
        sys.exit(-1)

    sys.exit(exit_code)
