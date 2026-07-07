import os

def list_files():
    print("Files in workspace:")
    for f in os.listdir("."):
        if f.endswith(".db") or "sso" in f.lower() or "db" in f.lower():
            size = os.path.getsize(f) if os.path.isfile(f) else "DIR"
            print(f"  {f} | Size: {size}")

if __name__ == "__main__":
    list_files()
