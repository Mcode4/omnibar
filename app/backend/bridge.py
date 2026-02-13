from PySide6.QtCore import QObject, Slot, Signal, QThread
from app.backend.router.command_router import CommandRouter
import os
import json

class SearchWorker(QObject):
    finished = Signal(str)
    started = Signal()

    def __init__(self):
        super().__init__()
        self.router = CommandRouter()

    @Slot(str)
    def process(self, text):
        self.started.emit()
        # print('Process Started')
        result = self.router.route(text)
        self.finished.emit(json.dumps(result))
        # print(f'Process Finished\n\n RESULTS: {result}')

# class FileSearchWorker(QThread):
#     resultsReady = Signal(list)

#     def __init__(self, query: str, search_path: str = None):
#         super().__init__()
#         self.query = query
#         self.search_path = search_path or os.path.expanduser("~")
    
#     def run(self):
#         matches = []
#         query_lower = self.query.lower()

#         for root, dirs, files in os.walk(self.search_path):
#             for f in files:
#                 if query_lower == f.lower():
#                     matches.append(os.path.join(root, f))
        
#         if not matches:
#             matches = ["No files found matching query"]

#         self.resultsReady.emit(json.dumps(matches))


class BackendBridge(QObject):
    searchResults = Signal(str)
    searchCommandStarted = Signal()
    searchSignal = Signal(str)

    def __init__(self):
        super().__init__()
        self.search_thread = QThread()
        self.search_worker = SearchWorker()

        self.search_worker.moveToThread(self.search_thread)

        # connect signals
        self.searchSignal.connect(self.search_worker.process)
        self.search_worker.finished.connect(self.searchResults)
        self.search_worker.started.connect(self.searchCommandStarted)

        self.search_thread.start()

    @Slot(str)
    def processSearchCommand(self, text):
        text = text.strip()
        print(f"Command received from UI: {text}")
        self.searchSignal.emit(text)
        

