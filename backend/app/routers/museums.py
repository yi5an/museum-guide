from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import Exhibit, Floor, Museum, Narration, Route
from app.schemas import (
    ExhibitListResponse,
    ExhibitOut,
    FloorOut,
    LocateRequest,
    LocateResponse,
    MuseumDetailResponse,
    MuseumListItem,
    MuseumListResponse,
    RouteOut,
)
from app.services.geo import point_in_fence

router = APIRouter(prefix="/api/museums", tags=["museums"])


@router.get("", response_model=MuseumListResponse)
async def museum_list(db: Session = Depends(get_db)):
    """所有支持的博物馆列表。"""
    museums = db.scalars(select(Museum).order_by(Museum.id)).all()
    items = []
    for m in museums:
        count = db.scalar(
            select(func.count(Exhibit.id)).where(
                Exhibit.museum_id == m.id, Exhibit.status == "active"
            )
        )
        items.append(MuseumListItem(
            id=m.id, name=m.name, city=m.city,
            description=m.description, exhibit_count=count or 0,
            cover_image_url=m.cover_image_url,
        ))
    return MuseumListResponse(total=len(items), museums=items)


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
        cover_image_url=museum.cover_image_url,
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


@router.get("/{museum_id}/exhibits", response_model=ExhibitListResponse)
async def exhibit_list(
    museum_id: int,
    floor_id: int | None = None,
    limit: int = 200,
    db: Session = Depends(get_db),
):
    """按楼层获取展品列表。floor_id 不传则返回该馆全部。"""
    stmt = select(Exhibit).where(
        Exhibit.museum_id == museum_id,
        Exhibit.status.in_(["active", "moved"]),
    )
    if floor_id is not None:
        stmt = stmt.where(Exhibit.floor_id == floor_id)
    stmt = stmt.order_by(Exhibit.category, Exhibit.name).limit(limit)

    exhibits_out = []
    for e in db.scalars(stmt):
        # 是否有讲解
        has_n = db.scalar(
            select(func.count(Narration.id)).where(Narration.exhibit_id == e.id)
        )
        exhibits_out.append(ExhibitOut(
            id=e.id,
            name=e.name,
            category=e.category,
            dynasty=e.dynasty,
            floor_id=e.floor_id,
            plan_x=e.plan_x,
            plan_y=e.plan_y,
            has_narration=(has_n or 0) > 0,
        ))

    return ExhibitListResponse(
        floor_id=floor_id,
        total=len(exhibits_out),
        exhibits=exhibits_out,
    )
