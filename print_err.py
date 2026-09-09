from fastapi.testclient import TestClient
from sanket.api import app
import sanket.monitoring as monitoring
import os

os.environ["SANKET_STORAGE_MODE"] = "local"
monitoring.DEFAULT_DB_PATH = "test_err.db"

client = TestClient(app, raise_server_exceptions=True)
try:
    resp = client.post("/api/monitor/demo/seed?scenario=1")
    print(resp.status_code)
except Exception as e:
    import traceback
    traceback.print_exc()
