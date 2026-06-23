from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import Exhibit, Floor, Museum, Route
from app.schemas import (
    FloorOut,
    LocateRequest,
    LocateResponse,
    MuseumDetailResponse,
    RouteOut,
)
from app.services.geo import point_in_fence

router = APIRouter(prefix="/api/museums", tags=["museums"])


@router.post("/locate", response_model=LocateResponse)
async def locate(req: LocateRequest, db: Session = Depends(get_db)):
    """根据 GPS 判定是否在某博物馆的 geo_fence 内。"""
    for museum in db.scalars(select(Museum)):
        fence = [(p[0], p[1]) for p in (museum.geo_fence or [])]
        # 注意：point_in_fence(x=经度, y=纬度)
        if point_in_fence(req.lng, req.lat, fence):
            return LocateResponse(museum_id=museum.id, name=museum.name, is_inside=True)
    return LocateResponse(museum_id=None, name=None, is_inside=False)


@router.get("/{museum_id}", response_model=MuseumDetailResponse)
async def museum_detail(museum_id: int, db: Session = Depends(get_db)):
    museum = db.get(Museum, museum_id)
    if not museum:
        raise HTTPException(status_code=404, detail="Museum not found")

    floors = db.scalars(
        select(Floor).where(Floor.museum_id == museum_id).order_by(Floor.sort_order)
    ).all()
    routes = db.scalars(select(Route).where(Route.museum_id == museum_id)).all()
    active_count = db.scalar(
        select(func.count(Exhibit.id)).where(
            Exhibit.museum_id == museum_id, Exhibit.status == "active"
        )
    )

    return MuseumDetailResponse(
        id=museum.id,
        name=museum.name,
        name_i18n=museum.name_i18n or {},
        city=museum.city,
        country=museum.country,
        description=museum.description,
        floors=[
            FloorOut(
                id=f.id,
                level=f.level,
                name=f.name,
                floor_plan_url=f.floor_plan_url,
                sort_order=f.sort_order,
            )
            for f in floors
        ],
        routes=[
            RouteOut(
                id=r.id,
                title=r.title,
                theme=r.theme,
                duration_min=r.duration_min,
                exhibit_order=r.exhibit_order or [],
            )
            for r in routes
        ],
        exhibit_count=active_count or 0,
    )
