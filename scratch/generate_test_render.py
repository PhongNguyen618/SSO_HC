import sys
sys.path.append(r"c:\Users\PC\Desktop\SSO_HC")

from fastapi.testclient import TestClient
from backend.main import app

def generate_render():
    client = TestClient(app)
    response = client.get("/register")
    with open("scratch/rendered_register.html", "w", encoding="utf-8") as f:
        f.write(response.text)
    print("Rendered HTML saved to scratch/rendered_register.html")

if __name__ == "__main__":
    generate_render()
