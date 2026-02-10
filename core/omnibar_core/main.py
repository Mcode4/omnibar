import sys
from omnibar_core.router import route_command

def main():
    if len(sys.argv) < 2:
        print("Usage: omnibar \"open firefox\"")
        return
    
    command = " ".join(sys.argv[1:])
    result = route_command(command)

    print(f"[{"Ok" if result.success else "ERR"}] {result.message}")

if __name__ == "__main__":
    main()