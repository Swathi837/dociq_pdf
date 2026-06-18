from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.routers import auth, documents, chat, alerts, dashboard, workspace, billing

app = FastAPI(title="DocIQ API", version="0.3.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router,      prefix="/auth",      tags=["auth"])
app.include_router(documents.router, prefix="/documents", tags=["documents"])
app.include_router(chat.router,      prefix="/chat",      tags=["chat"])
app.include_router(alerts.router,    prefix="/alerts",    tags=["alerts"])
app.include_router(dashboard.router, prefix="/dashboard", tags=["dashboard"])
app.include_router(workspace.router, prefix="/workspace", tags=["workspace"])
app.include_router(billing.router,   prefix="/billing",   tags=["billing"])


@app.get("/health")
async def health():
    return {"status": "ok", "version": "0.3.0"}