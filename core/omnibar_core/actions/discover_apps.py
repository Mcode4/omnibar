import os
# from configparser import ConfigParser
from xdg import DesktopEntry
from difflib import get_close_matches
from omnibar_core.models import CommandResult

DESKTOP_DIRS = [
    "/usr/share/applications",                             # normal system apps
    os.path.expanduser("~/.local/share/applications"),     # user apps
    "/var/lib/snapd/desktop/applications",                # snap apps
    os.path.expanduser("~/.local/share/flatpak/exports/share/applications")  # flatpak apps
]


_app_cache = None

def load_apps():
    global _app_cache
    if _app_cache is not None:
        return _app_cache
    
    apps = {}
    for dir_path in DESKTOP_DIRS:
        if not os.path.exists(dir_path):
            continue

        for file in os.listdir(dir_path):
            if file.endswith(".desktop"):
                # desktop_file = os.path.join(dir_path, file)
                # config = ConfigParser()
                try:
                    # config.read(desktop_file)
                    # name = config.get("Desktop Entry", "Name", fallback=None)
                    # exec_cmd = config.get("Desktop Entry", "Exec", fallback=None)
                    # if name and exec_cmd:
                    #     apps[name.lower()] = exec_cmd.split()[0]
                    entry = DesktopEntry.DesktopEntry(os.path.join(dir_path, file))
                    name = entry.getName()
                    exec_cmd = entry.getExec()
                    # no_display = entry.getNoDisplay()
                    if not name or not exec_cmd:
                        continue

                    exec_cmd = exec_cmd.split()[0].replace("%u", ""). replace("%f", "").strip()
                    apps[name.lower().replace("_", " ")] = exec_cmd
                except Exception:
                    continue

    _app_cache = apps
    return apps
    
def find_app(query: str) -> CommandResult:
    apps = load_apps()
    query_lower = query.lower()
    matches = { 
        name: cmd 
        for name, cmd in apps.items() 
        if query_lower in name or all(q in name for q in query_lower.split())
    }

    print(f'\nAPPS: {apps} \n\n QUERY:{query_lower} \n\n MATCHES:{matches}\n\n')

    if not matches:
        close_names = get_close_matches(query_lower, apps.keys(), cutoff=0.5)
        matches = {name: apps[name] for name in close_names}
        print(f'\n\nNO MATCH, CLOSE NAMES CHECK: {close_names} \nNEW MATCHES: {matches}')

    if matches:
        return CommandResult(
            success=True,
            message=f"Found {len(matches)} app(s)",
            data={"apps": matches}
        )
    else:
        return CommandResult(
            success=False,
            message=f"No apps found matching query"
        )