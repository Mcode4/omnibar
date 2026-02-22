import os
import PySide6

qt_path = os.path.join(os.path.dirname(PySide6.__file__), "Qt", "lib")
os.environ["LD_LIBRARY_PATH"] = qt_path

import sys
import yaml
import importlib
import argparse
import time
import gc
import pkgutil

from PySide6.QtWidgets import QApplication
from PySide6.QtQml import QQmlApplicationEngine
from PySide6.QtCore import QFileSystemWatcher, QUrl, QTimer

from backend.bridge import BackendBridge
from backend.databases.user_db import UserDatabase as Database
from backend.databases.system_db import SystemDatabase
from backend.ai.model_manager import ModelManager
from backend.settings import Settings
from backend.ai.llm_engine import LLMEngine
from backend.ai.embeddings_engine import EmbeddingEngine
from backend.ai.rag_pipeline import RAGPipeline
from backend.ai.orchestrator import Orchestrator
from backend.services.chat_service import ChatService
from backend.system.device_manager import DeviceManager
from backend.ai.vision_manager import VisionManager
from state.chat_state import ChatState

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
dev_qml_file = os.path.join(os.path.dirname(__file__), "ui", "DevRoot.qml")

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
chat_state = None


# Load DevRoot first (holds the Loader)
if DEV_MODE:
    engine.load(QUrl.fromLocalFile(dev_qml_file))
    if not engine.rootObjects():
        sys.exit(-1)
    root = engine.rootObjects()[0]
else:
    engine.load(QUrl.fromLocalFile(qml_file))
    if not engine.rootObjects():
        sys.exit(-1)
    root = engine.rootObjects()[0]  # main window


# ============================================================
# BACKEND CREATION
# ============================================================
def create_backend():
    global system_db, db
    global vision_manager, model_manager, settings
    global llm_engine, embedding_engine, rag_pipeline
    global orchestrator, chat_service, bridge, chat_state

    print("🚀 Creating backend...")

    db_paths = config.get("databases", {})
    

    vision_manager = VisionManager(device)
    

    embedding_engine = EmbeddingEngine(
        next((m for m in config.get("models", []) if m.get("backend") == "embedding"), None)
    )

def create_backend():
    global bridge, chat_state

    print("🚀 Creating backend...")

    db_paths = config.get("databases", {})

    vision_manager = VisionManager(device)

    embedding_engine = EmbeddingEngine(
        next((m for m in config.get("models", []) if m.get("backend") == "embedding"), None)
    )

    def build_services():
        system_db = SystemDatabase(
            db_paths.get("system", os.path.expanduser("~/.local/share/omnimanager/system.db"))
        )

        user_db = Database(
            db_paths.get("user", os.path.expanduser("~/.local/share/omnimanager/system.db"))
        )

        settings = Settings(None, config, system_db)
        settings.load_settings()

        model_manager = ModelManager(vision_manager, settings)
        model_manager.load_models_from_config(config)
        settings.model_manager = model_manager

        rag_pipeline = RAGPipeline(user_db, embedding_engine, settings)

        return {
            "current_tasks": current_tasks,
            "settings": settings,
            "system_db": system_db,
            "user_db": user_db,
            "model_manager": model_manager,
            "rag_pipeline": rag_pipeline
        }

    if bridge:
        try:
            bridge.shutdown()
        except Exception:
            pass

    bridge = BackendBridge(build_services)

    chat_state = ChatState()

    engine.rootContext().setContextProperty("backend", bridge)
    engine.rootContext().setContextProperty("ChatState", chat_state)

    print("✅ Backend ready")

# ============================================================
# INITIAL BACKEND
# ============================================================
create_backend()


# ============================================================
# DEV MODE FILE WATCHER
# ============================================================
if DEV_MODE:
    watcher = QFileSystemWatcher()
    files_to_watch = []

    for root_dir, _, files in os.walk(os.path.dirname(os.path.abspath(__file__))):
        for f in files:
            if f.endswith((".py", ".qml")) and f not in ("DevRoot.qml",):
                files_to_watch.append(os.path.join(root_dir, f))

    watcher.addPaths(files_to_watch)

    # ============================================================
    # CLEAR/RELOADING OLD FILES
    # ============================================================
    def clear_backend():
        global system_db, db, vision_manager, model_manager, settings
        global llm_engine, embedding_engine, rag_pipeline
        global orchestrator, chat_service, bridge

        print("🗑️ Clearing old backend objects...")

        print("\n\nBEFORE CLEAN", {system_db, db, vision_manager, model_manager, settings,
              llm_engine, embedding_engine, rag_pipeline,
              orchestrator, chat_service, bridge})
        if bridge:
            try: bridge.shutdown()
            except Exception: pass
        # Dereference all globals
        system_db = db = vision_manager = model_manager = None
        settings = llm_engine = embedding_engine = rag_pipeline = None
        orchestrator = chat_service = bridge = None
        gc.collect()
        print("\n\nAFTER CLEAN", {system_db, db, vision_manager, model_manager, settings,
              llm_engine, embedding_engine, rag_pipeline,
              orchestrator, chat_service, bridge})

    def reload_package(package):
        """Reload all modules in a package recursively."""
        for loader, name, ispkg in pkgutil.walk_packages(package.__path__, package.__name__ + "."):
            if name in sys.modules:
                importlib.reload(sys.modules[name])
                gc.collect()
                submod = sys.modules[name]
                if hasattr(submod, "__path__"):  # recursively reload subpackages
                    reload_package(submod)
                else:
                    importlib.reload(sys.modules[name])
                    gc.collect()
        importlib.reload(package)
        
    def reload_qml():
        engine.clearComponentCache()
        gc.collect()
        if hasattr(root, "reloadMain"):
            print("🔄 Reloading main.qml only")
            root.reloadMain()

    def reload_backend():
        print("🔄 Hot reloading Python backend...")
        clear_backend()
        gc.collect()

        # Reload backend code
        import backend
        reload_package(backend)
        print("\n\nCURENT BACKEND AFTER RELOAD", {system_db, db, vision_manager, model_manager, settings,
              llm_engine, embedding_engine, rag_pipeline,
              orchestrator, chat_service, bridge})

        # Recreate all backend objects
        create_backend()

        # Update QML context to point to new objects
        engine.rootContext().setContextProperty("backend", bridge)

        # Reload QML so it reconnects to new backend
        reload_qml()


    watcher.fileChanged.connect(lambda path: reload_backend() if path.endswith(".py") else reload_qml())
    watcher.directoryChanged.connect(lambda path: None)


# ============================================================
# RUN
# ============================================================
if not engine.rootObjects():
    bridge.shutdown()
    sys.exit(-1)

sys.exit(app.exec())
