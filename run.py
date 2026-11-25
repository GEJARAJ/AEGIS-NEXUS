"""One-command launcher for AEGIS NEXUS — Civic Sentinel Government Command Portal."""

import uvicorn


if __name__ == "__main__":
    print("==================================================================")
    print("  AEGIS NEXUS | Civic Sentinel (Powered by NEXA ENGINE)")
    print("  Simulation-Based Government Infrastructure Intelligence Portal")
    print("  Open: http://127.0.0.1:8000")
    print("==================================================================")
    uvicorn.run("backend.app.main:app", host="127.0.0.1", port=8000, reload=False)
