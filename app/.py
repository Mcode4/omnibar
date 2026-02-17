import sys
import os
import yaml
import importlib
import argparse
import gc
import pkgutil

from PySide6.QtWidgets import QApplication
from PySide6.QtQml import QQmlApplicationEngine
from PySide6.QtCore import QFileSystemWatcher, QUrl, QTimer

import backend  # keep a reference to the package for reloading

# ============================================================
# ARG PARSER
# ============================================================
parser = argparse.ArgumentParser()
parser.add_argument("--dev", "--d", "--dev-mode", action="store_true")
args = parser.parse_args()
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
from backend.system.device_manager import DeviceManager

device_setting = config.get("system", {}).get("device", "auto")
forced = None if device_setting == "auto" else device_setting
device_manager = DeviceManager(forced_device=forced)
device = device_manager.get_device()

# ============================================================
# APP + ENGINE INIT
# ============================================================
app = QApplication(sys.argv)
engine = QQmlApplicationEngine()

qml_file = os.path.join(os.path.dirname(__file__), "ui", "main.qml")
dev_qml_file = os.path.join(os.path.dirname(__file__), "ui", "DevRoot.qml")

current_tasks = {"ai": 0, "system": 0}

# Global backend references
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

# Load QML shell
load_target = dev_qml_file if DEV_MODE else qml_file
engine.load(QUrl.fromLocalFile(load_target))
if not engine.rootObjects():
    sys.exit(-1)
root = engine.rootObjects()[0]

# ============================================================
# PURGE BACKEND MODULES
# Removes all cached backend.* modules from sys.modules so
# the next import fetches fresh bytecode from disk.
# ============================================================
def purge_backend_modules():
    to_delete = [key for key in sys.modules if key == "backend" or key.startswith("backend.")]
    for key in to_delete:
        del sys.modules[key]
    gc.collect()
    print(f"🗑️  Purged {len(to_delete)} backend modules from sys.modules")

# ============================================================
# BACKEND CREATION
# Always imports fresh after purge_backend_modules().
# ============================================================
def create_backend():
    global system_db, db, vision_manager, model_manager, settings
    global llm_engine, embedding_engine, rag_pipeline
    global orchestrator, chat_service, bridge

    print("🚀 Creating backend...")

    # --- Fresh imports (works because sys.modules was purged) ---
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
    from backend.ai.vision_manager import VisionManager

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

    bridge = BackendBridge(current_tasks, settings, chat_service)

    engine.rootContext().setContextProperty("backend", bridge)
    engine.rootContext().setContextProperty("settings", settings)

    if DEV_MODE and hasattr(root, "reloadMain"):
        root.reloadMain()

    print("✅ Backend ready")

# ============================================================
# SHUTDOWN HELPER
# ============================================================
def teardown_backend():
    global system_db, db, vision_manager, model_manager, settings
    global llm_engine, embedding_engine, rag_pipeline
    global orchestrator, chat_service, bridge

    if bridge is not None:
        try:
            bridge.shutdown()
        except Exception as e:
            print(f"⚠️  Bridge shutdown error: {e}")

    system_db = db = vision_manager = model_manager = None
    settings = llm_engine = embedding_engine = rag_pipeline = None
    orchestrator = chat_service = bridge = None
    gc.collect()
    print("✅ Backend torn down")

# ============================================================
# INITIAL BACKEND
# ============================================================
create_backend()
app.aboutToQuit.connect(teardown_backend)

# ============================================================
# DEV MODE: FILE WATCHER + DEBOUNCED RELOAD
# ============================================================
if DEV_MODE:
    # Debounce timer — prevents multiple rapid saves from
    # triggering several reloads in quick succession.
    _reload_timer = QTimer()
    _reload_timer.setSingleShot(True)
    _reload_timer.setInterval(2500)  # ms — tune to taste

    _pending_py = False
    _pending_qml = False

    def _do_reload():
        global _pending_py, _pending_qml
        py  = _pending_py
        qml = _pending_qml
        _pending_py = _pending_qml = False

        if py:
            print("🔄 Hot reloading Python backend...")
            teardown_backend()
            purge_backend_modules()
            create_backend()
            # After a Python reload always also refresh QML bindings
            engine.clearComponentCache()
            if hasattr(root, "reloadMain"):
                root.reloadMain()

        elif qml:
            print("🔄 Reloading QML only...")
            engine.clearComponentCache()
            if hasattr(root, "reloadMain"):
                print("Reloading Main QML")
                root.reloadMain()

    _reload_timer.timeout.connect(_do_reload)

    def _on_file_changed(path: str):
        global _pending_py, _pending_qml

        # Re-add the path: many editors (vim, VS Code) write files by
        # deleting and recreating them, which removes them from the watcher.
        if path not in watcher.files():
            watcher.addPath(path)

        if path.endswith(".py"):
            _pending_py = True
        elif path.endswith(".qml") and not path.endswith("DevRoot.qml"):
            _pending_qml = True

        _reload_timer.start()  # restart the timer on every change

    # Build initial watch list
    base_dir = os.path.dirname(os.path.abspath(__file__))
    files_to_watch = []
    for root_dir, _, files in os.walk(base_dir):
        for f in files:
            if f.endswith((".py", ".qml")) and f != "DevRoot.qml":
                files_to_watch.append(os.path.join(root_dir, f))

    watcher = QFileSystemWatcher()
    watcher.addPaths(files_to_watch)
    watcher.fileChanged.connect(_on_file_changed)

# ============================================================
# RUN
# ============================================================
sys.exit(app.exec())