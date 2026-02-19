
def get_available_tools():
    return [
        {
            "type": "function",
            "function": {
                "name": "search_files",
                "description": "Search local files by name or content.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": "Search query for files"
                        }
                    },
                    "required": ["query"]
                }
            }
        },
        {
            "type": "function",
            "function": {
                "name": "web_search",
                "description": "Search the web for live information.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": "Search query for the web"
                        }
                    }
                }
            }
        }
    ]