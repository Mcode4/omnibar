import os
from omnibar_core.models import CommandResult

def search_files(query: str, search_path: str=os.path.expanduser("~")) -> CommandResult:
    matches = []
    query_lower = query.lower()

    for root, dirs, files in os.walk(search_path):
        for f in files:
            if query_lower in f.lower():
                matches.append(os.path.join(root, f))

    if matches:
        return CommandResult(
            success=True,
            message=f"Found {len(matches)} file(s)",
            data={"files": matches[:10]} # Limit to first 10 for now
        )
    else:
        return CommandResult(
            success=False,
            message="No files found matching query"
        )