import subprocess
from omnibar_core.models import CommandResult

def launch_app(app_name: str) -> CommandResult:
    try:
        subprocess.Popen([app_name])
        return CommandResult(
            success=True,
            message=f"Launched {app_name}"
        )
    except FileNotFoundError:
        return CommandResult(
            success=False,
            message=f'Application "{app_name}" not found'
        )
    except Exception as e:
        return CommandResult(
            success=False,
            message=str(e)
        )