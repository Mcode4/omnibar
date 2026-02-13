import os

class ModelManager:
    def __init__(self):
        self.model_dir = os.path.expanduser("~/.local/share/omnimanager/models")

    def ensure_model(self, name, url):
        path = os.path.join(self.model_dir, name)

        if not os.path.exists(path):
            self.download_model(url, path)

    def download_model(self, url, path):
        return