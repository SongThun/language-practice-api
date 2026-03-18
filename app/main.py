from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.routers import practice, tags, words

app = FastAPI(
    title="Language Practice API",
    description="Multi-language vocabulary and writing practice platform with AI-powered evaluation",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(words.router, prefix="/api/words", tags=["words"])
app.include_router(tags.router, prefix="/api/tags", tags=["tags"])
app.include_router(practice.router, prefix="/api/practice", tags=["practice"])


@app.get("/health")
async def health_check() -> dict[str, str]:
    return {"status": "ok"}
