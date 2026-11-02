"""Run locally to display the operator key. Never include its output in a shared ZIP."""
from agent_store import admin_key, get_store

try:
    from dotenv import load_dotenv
    from agent_store import BASE_DIR
    load_dotenv(BASE_DIR / ".env")
except ImportError:
    pass

if __name__ == "__main__":
    store = get_store()
    print("Timo Agent is ready. Existing products and .env are preserved.")
    print("Knowledge database:", store.path)
    print("Open: http://127.0.0.1:8000/agent")
    print("Manager key (keep private):", admin_key())
