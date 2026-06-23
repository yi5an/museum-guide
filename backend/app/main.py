from fastapi import FastAPI

from app.routers import museums

app = FastAPI(title="Museum Guide API", version="0.1.0")

app.include_router(museums.router)


@app.get("/health")
async def health():
    return {"status": "ok"}
