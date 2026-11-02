"""Run offline tests against isolated synthetic data, never the operator's DBs."""
import os
from pathlib import Path
import tempfile
import unittest

def main():
    with tempfile.TemporaryDirectory(prefix="timo-tests-") as folder:
        root = Path(folder)
        os.environ.update(TIMO_CATALOG_DB=str(root / "products.db"),
                          TIMO_AGENT_DB=str(root / "agent.db"),
                          TIMO_GRAPH_DB=str(root / "graph.db"),
                          TIMO_STT_PROVIDER="groq", TIMO_CHAT_PROVIDER="n8n",
                          LANGSMITH_TRACING="false", LANGCHAIN_TRACING_V2="false")
        from setup_demo import main as setup_demo
        setup_demo()
        suite = unittest.defaultTestLoader.discover("tests", pattern="test_*.py")
        result = unittest.TextTestRunner(verbosity=2).run(suite)
        return 0 if result.wasSuccessful() else 1

if __name__ == "__main__":
    raise SystemExit(main())
