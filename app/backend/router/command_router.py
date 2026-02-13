from backend.search_files import search_files
from backend.discover_apps import find_app

class CommandRouter:
    def __init__(self):
        self.commands = {
            "echo": self.echo,
            "help": self.help_command,
            "files": self.search,
            "apps": self.open_app,
        }
    
    def route(self, text: str) -> dict:
        if not text.strip():
            return ""
        
        parts = text.split(" ", 1)
        command = parts[0]
        argument = parts[1] if len(parts) > 1 else ""

        if command in self.commands:
            return self.commands[command](argument)
        
        return {
            "type": "error",
            "success": False,
            "message": f"Unkown command: {command}"
        }
        
    def echo(self, arg: str) -> dict:
        return {
            "type": "text",
            "success": True,
            "message": arg
        }
    
    def help_command(self, arg: str) -> str:
        return "Available commands: " + ", ".join(self.commands.keys())
    
    def search(self, arg: str) -> str:
        results = search_files(arg)
        return {
            "type": "files",
            "success": results["success"],
            "message": results["message"],
            "data": results.get("data", {})
        }
    
    def open_app(self, arg: str) -> str:
        results = find_app(arg)
        return {
            "type": "apps",
            "success": results["success"],
            "message": results["message"],
            "data": results.get("data", {})
        }

    
