from PySide6.QtCore import QObject
from backend.settings import Settings
from backend.databases.system_db import SystemDatabase
from backend.databases.user_db import UserDatabase
from backend.ai.model_manager import ModelManager
from backend.ai.rag_pipeline import RAGPipeline

class AppServices(QObject):
    def __init__(
        self, 
        current_tasks,
        settings: Settings,
        system_db: SystemDatabase,
        user_db: UserDatabase,
        model_manager: ModelManager,
        rag_pipeline: RAGPipeline
    ):
        self.current_tasks = current_tasks
        self.settings = settings
        self.system_db = system_db
        self.user_db = user_db
        self.model_manager = model_manager
        self.rag_pipeline = rag_pipeline


# Backend Bridge old imports:
# current_tasks, settings, system_db, user_db, model_manager, rag_pipeline