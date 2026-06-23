from fastapi import FastAPI

from app.routers import museums, recognize

app = FastAPI(title="Museum Guide API", version="0.1.0")

app.include_router(museums.router)
app.include_router(recognize.router)


@app.get("/health")
async def health():
    return {"status": "ok"}
