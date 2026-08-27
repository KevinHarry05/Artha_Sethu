"""
Plain dev launcher.

CORS and the auth router are now attached directly inside api/main.py
(both were originally bolted on here at runtime, back when api/main.py
was being kept untouched under an earlier, narrower instruction -- that
constraint no longer applies, so they were folded into main.py properly
instead of staying as a separate patch layer here). This file is now just
a convenience entry point.

Run:
    pip install -r requirements.txt
    pip install python-multipart   # see requirements.txt note in AUTH.md
    python3 -m db.init_db
    python3 -m db.init_auth_db
    python3 -m db.ingest_raw_data /path/to/MAKEATHON_Internal
    python3 run_server.py
    # backend now serves http://localhost:8000 with CORS open for
    # http://localhost:3000 (FronteEnd's dev server) and the auth routes
    # live at /auth/signup, /auth/login

Override the allowed frontend origin(s) with FRONTEND_ORIGINS (comma-
separated) if FronteEnd runs on a different port/host, e.g.:
    FRONTEND_ORIGINS=http://localhost:3001 python3 run_server.py
"""

import os

import uvicorn

from api.main import app

if __name__ == "__main__":
    port = int(os.environ.get("PORT", "8000"))
    print(f"ARTHA SETU backend -> http://localhost:{port}")
    uvicorn.run(app, host="0.0.0.0", port=port)
