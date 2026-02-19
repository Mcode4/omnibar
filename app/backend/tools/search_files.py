import os
from backend.settings import Settings

def search_files(query: str, settings: Settings):
    search_settings = settings.get_settings()["tool_settings"]["search_files"]
    max_results = search_settings.get("max_results", 50)
    search_path = search_settings.get("search_path", os.path.expanduser("~"))
    can_search_sub_directories = search_settings.get(
        "can_search_sub_directories", True
    )
    matches = []
    query_lower = query.lower()

    for root, dirs, files in os.walk(search_path):
        if can_search_sub_directories and dirs:
            dirs[:] = []
        for f in files:
            if query_lower in f.lower():
                matches.append(os.path.join(root, f))

                if len(matches) >= max_results:
                    return {
                        "success": True,
                        "message": f"Showing first {max_results} file(s)",
                        "data": matches
                    }



    if matches:
        return {
            "success": True,
            "message": f"Found {len(matches)} file(s)",
            "data": matches
        }
    else:
        return {
            "success": False,
            "message": "No files found matching query"
        }