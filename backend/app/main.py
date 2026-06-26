from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.routers import admin_collect, chat, feedback, museums, narrate, recognize

app = FastAPI(title="Museum Guide API", version="0.1.0")

# 静态文件（博物馆图片等）
app.mount("/static", StaticFiles(directory="app/static"), name="static")

app.include_router(museums.router)
app.include_router(recognize.router)
app.include_router(narrate.router)
app.include_router(chat.router)
app.include_router(feedback.router)
app.include_router(admin_collect.router)


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.get("/admin")
async def admin_page():
    """采集管理后台单页（原生 HTML+JS，零构建）。"""
    return FileResponse("app/static/admin/index.html")

