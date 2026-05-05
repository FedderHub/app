import os
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
from app.db import engine
from app import models
from app.routers import auth, jobs

# Create all tables on startup
models.Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="FederHub Integrated API",
    description="Merged Alpha/Beta/Gamma API for auth, jobs, orchestration, and metrics",
    version="3.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Routers ───────────────────────────────────────────────────────────────────
app.include_router(auth.router)
app.include_router(jobs.router)


# ── Downloads ─────────────────────────────────────────────────────────────────
@app.get("/download/client/{os_type}")
def download_client_app(os_type: str):
    """Serves the actual compiled Electron Client executable for Mac or Windows."""
    
    # Path to the downloads folder we created
    DOWNLOAD_DIR = os.path.join(os.path.dirname(__file__), "../downloads")

    if os_type.lower() == "mac":
        file_name = "FederHub-Edge-Client.dmg"
        media_type = "application/x-apple-diskimage"
    elif os_type.lower() == "windows":
        file_name = "FederHub-Edge-Client.exe"
        media_type = "application/x-msdownload"
    else:
        raise HTTPException(status_code=400, detail="Invalid OS. Choose 'mac' or 'windows'.")

    file_path = os.path.join(DOWNLOAD_DIR, file_name)

    # Check if the ML Engineer has placed the built file in the folder yet
    if not os.path.exists(file_path):
        raise HTTPException(
            status_code=404, 
            detail=f"{file_name} is not available on the server. Please compile the Electron app and place it in backend/downloads."
        )
    
    return FileResponse(
        path=file_path, 
        filename=file_name, 
        media_type=media_type
    )

# ── Health & root ─────────────────────────────────────────────────────────────
@app.get("/")
def root():
    return {"message": "FederHub Integrated API v3 is running"}


@app.get("/health")
def health():
    return {"status": "ok"}