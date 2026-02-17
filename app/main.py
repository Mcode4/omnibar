import sys
import os
import yaml
import importlib
import argparse
import time

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
import sys
import importlib
import pkgutil

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


# Load DevRoot first (holds the Loader)
if DEV_MODE:
    engine.load(QUrl.fromLocalFile(dev_qml_file))
    if not engine.rootObjects():
        sys.exit(-1)
    # Grab root QML object (DevRoot)
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

    if DEV_MODE and hasattr(root, "reloadMain"):
        root.reloadMain()

    print("✅ Backend ready")

# ============================================================
# INITIAL BACKEND
# ============================================================
create_backend()
app.aboutToQuit.connect(lambda: bridge.shutdown())

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
        print("\n\nAFTER CLEAN", {system_db, db, vision_manager, model_manager, settings,
              llm_engine, embedding_engine, rag_pipeline,
              orchestrator, chat_service, bridge})

    def reload_package(package):
        """Reload all modules in a package recursively."""
        for loader, name, ispkg in pkgutil.walk_packages(package.__path__, package.__name__ + "."):
            if name in sys.modules:
                importlib.reload(sys.modules[name])
                submod = sys.modules[name]
                if hasattr(submod, "__path__"):  # recursively reload subpackages
                    reload_package(submod)
        importlib.reload(package)
        
    def reload_qml():
        engine.clearComponentCache()
        if hasattr(root, "reloadMain"):
            print("🔄 Reloading main.qml only")
            root.reloadMain()

    def reload_backend():
        print("🔄 Hot reloading Python backend...")

        if bridge:
            try:
                bridge.shutdown()
            except Exception:
                pass

            # Disconnect signals
            try:
                bridge.systemSignal.disconnect()
            except Exception: pass
            try:
                bridge.aiSignal.disconnect()
            except Exception: pass

        clear_backend()
        import gc
        gc.collect()


        # Reload backend code
        import backend
        reload_package(backend)
        print("\n\nCURENT BACKEND AFTER RELOAD", {system_db, db, vision_manager, model_manager, settings,
              llm_engine, embedding_engine, rag_pipeline,
              orchestrator, chat_service, bridge})
        
        time.sleep(5)

        # Recreate all backend objects
        create_backend()

        # Update QML context to point to new objects
        engine.rootContext().setContextProperty("backend", bridge)
        engine.rootContext().setContextProperty("settings", settings)

        # Reload QML so it reconnects to new backend
        reload_qml()



    watcher.fileChanged.connect(lambda path: reload_backend() if path.endswith(".py") else reload_qml())
    watcher.directoryChanged.connect(lambda path: None)

# ============================================================
# RUN
# ============================================================
sys.exit(app.exec())