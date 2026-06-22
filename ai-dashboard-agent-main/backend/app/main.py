from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1.agent_routes import router as agent_router
from app.api.v1.example_routes import router as example_router
from app.api.v1.widget_routes import router as widget_router


app = FastAPI(
    title="AI Dashboard Agent Backend",
    version="0.2.0",
    description="Backend API for a tenant-safe AI dashboard agent."
)


app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
def health_check():
    return {
        "status": "ok",
        "service": "ai-dashboard-agent-backend",
        "version": "0.2.0"
    }


app.include_router(agent_router, prefix="/api/v1")
app.include_router(widget_router, prefix="/api/v1")
app.include_router(example_router, prefix="/api/v1")
