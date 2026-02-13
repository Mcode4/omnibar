import os

def search_files(query: str, max_results: int = 50, search_path: str=os.path.expanduser("~")):
    matches = []
    query_lower = query.lower()

    for root, dirs, files in os.walk(search_path):
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