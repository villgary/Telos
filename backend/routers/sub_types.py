from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from typing import Optional, List

from backend.database import get_db
from backend import models, schemas, auth

router = APIRouter(prefix="/api/v1/sub-types", tags=["子类型管理"])


def _sub_type_response(st: models.SubTypeDef) -> schemas.SubTypeDefResponse:
    return schemas.SubTypeDefResponse(
        id=st.id,
        slug=st.slug,
        name=st.name,
        description=st.description,
        sub_type_kind=st.sub_type_kind,
        icon=st.icon,
        color=st.color,
        sort_order=st.sort_order,
        created_at=st.created_at,
    )


@router.get("", response_model=List[schemas.SubTypeDefResponse])
async def list_sub_types(
    kind: Optional[str] = Query(None, description="Filter by sub_type_kind (network, iot, database, os)"),
    db: Session = Depends(get_db),
    user: models.User = Depends(auth.get_current_user),
):
    """List all sub-type definitions, optionally filtered by kind."""
    query = db.query(models.SubTypeDef)
    if kind:
        query = query.filter(models.SubTypeDef.sub_type_kind == kind)
    sub_types = query.order_by(models.SubTypeDef.sub_type_kind, models.SubTypeDef.sort_order, models.SubTypeDef.name).all()
    return [_sub_type_response(st) for st in sub_types]


@router.post("", response_model=schemas.SubTypeDefResponse, status_code=status.HTTP_201_CREATED)
async def create_sub_type(
    st_in: schemas.SubTypeDefCreate,
    db: Session = Depends(get_db),
    user: models.User = Depends(auth.require_role(models.UserRole.admin)),
):
    """Create a new sub-type definition (admin only)."""
    existing = db.query(models.SubTypeDef).filter(
        models.SubTypeDef.slug == st_in.slug
    ).first()
    if existing:
        raise HTTPException(status_code=400, detail=f"子类型 slug '{st_in.slug}' 已存在")

    if st_in.sub_type_kind not in ('network', 'iot', 'database', 'os'):
        raise HTTPException(status_code=400, detail="sub_type_kind 必须是 network, iot, database, 或 os 之一")

    st = models.SubTypeDef(
        slug=st_in.slug,
        name=st_in.name,
        description=st_in.description,
        sub_type_kind=st_in.sub_type_kind,
        icon=st_in.icon,
        color=st_in.color,
        sort_order=st_in.sort_order,
    )
    db.add(st)
    db.commit()
    db.refresh(st)
    return _sub_type_response(st)


@router.put("/{sub_type_id}", response_model=schemas.SubTypeDefResponse)
async def update_sub_type(
    sub_type_id: int,
    update_in: schemas.SubTypeDefUpdate,
    db: Session = Depends(get_db),
    user: models.User = Depends(auth.require_role(models.UserRole.admin)),
):
    """Update sub-type metadata. slug and kind cannot be changed."""
    st = db.query(models.SubTypeDef).filter(
        models.SubTypeDef.id == sub_type_id
    ).first()
    if not st:
        raise HTTPException(status_code=404, detail="子类型不存在")

    if update_in.name is not None:
        st.name = update_in.name
    if update_in.description is not None:
        st.description = update_in.description
    if update_in.icon is not None:
        st.icon = update_in.icon
    if update_in.color is not None:
        st.color = update_in.color
    if update_in.sort_order is not None:
        st.sort_order = update_in.sort_order

    db.commit()
    db.refresh(st)
    return _sub_type_response(st)


@router.delete("/{sub_type_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_sub_type(
    sub_type_id: int,
    db: Session = Depends(get_db),
    user: models.User = Depends(auth.require_role(models.UserRole.admin)),
):
    """Delete a sub-type definition."""
    st = db.query(models.SubTypeDef).filter(
        models.SubTypeDef.id == sub_type_id
    ).first()
    if not st:
        raise HTTPException(status_code=404, detail="子类型不存在")

    db.delete(st)
    db.commit()
