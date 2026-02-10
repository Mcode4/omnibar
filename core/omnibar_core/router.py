from omnibar_core.actions.launch_app import launch_app
from omnibar_core.actions.search_files import search_files
from omnibar_core.actions.discover_apps import find_app
from omnibar_core.models import CommandResult

def route_command(text: str) -> CommandResult:
    text = text.strip().lower()

    if text.startswith("open "):
        query = text.replace("open ", "", 1)
        return find_app(query)
    
    if text.startswith("search "):
        query = text.replace("search ", "", 1)
        return search_files(query)
    
    return CommandResult(
        success=False,
        message="command not recognized"
    )

