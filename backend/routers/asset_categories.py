from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List

from backend.database import get_db
from backend import models, schemas, auth

router = APIRouter(prefix="/api/v1/asset-categories", tags=["资产品类管理"])


# System slugs that have i18n entries — custom user slugs must NOT get name_i18n_key
_SYSTEM_I18N_SLUGS = {
    "server", "database", "network", "iot",
    "os", "linux", "ubuntu-desktop", "linux-server",
    "windows", "windows-desktop", "windows-server",
}


def _cat_response(cat: models.AssetCategoryDef) -> schemas.AssetCategoryDefResponse:
    return schemas.AssetCategoryDefResponse(
        id=cat.id,
        slug=cat.slug,
        name=cat.name,
        name_i18n_key=f"category.{cat.slug}" if cat.slug in _SYSTEM_I18N_SLUGS else None,
        description=cat.description,
        icon=cat.icon,
        sub_type_kind=cat.sub_type_kind,
        parent_id=cat.parent_id,
    )


def _cat_tree_response(cat: models.AssetCategoryDef, children_map: dict) -> schemas.AssetCategoryTreeResponse:
    return schemas.AssetCategoryTreeResponse(
        id=cat.id,
        slug=cat.slug,
        name=cat.name,
        name_i18n_key=f"category.{cat.slug}" if cat.slug in _SYSTEM_I18N_SLUGS else None,
        sub_type_kind=cat.sub_type_kind,
        children=[_cat_tree_response(child, children_map) for child in children_map.get(cat.id, [])],
    )


@router.get("", response_model=list[schemas.AssetCategoryDefResponse])
async def list_categories(
    db: Session = Depends(get_db),
    user: models.User = Depends(auth.get_current_user),
):
    """List all asset category definitions (flat)."""
    cats = db.query(models.AssetCategoryDef).order_by(models.AssetCategoryDef.id).all()
    return [_cat_response(c) for c in cats]


@router.get("/tree", response_model=list[schemas.AssetCategoryTreeResponse])
async def list_categories_tree(
    db: Session = Depends(get_db),
    user: models.User = Depends(auth.get_current_user),
):
    """List all asset categories as a nested tree."""
    cats = db.query(models.AssetCategoryDef).order_by(models.AssetCategoryDef.id).all()
    # Build children map: parent_id -> [children]
    children_map: dict = {}
    for cat in cats:
        children_map.setdefault(cat.parent_id or 0, []).append(cat)
    # Roots are those with parent_id=None (keyed as 0)
    roots = children_map.get(0, [])
    return [_cat_tree_response(root, children_map) for root in roots]


@router.post("", response_model=schemas.AssetCategoryDefResponse, status_code=status.HTTP_201_CREATED)
async def create_category(
    cat_in: schemas.AssetCategoryDefCreate,
    db: Session = Depends(get_db),
    user: models.User = Depends(auth.require_role(models.UserRole.admin)),
):
    """Create a new asset category (admin only). Slug can be any identifier."""
    existing = db.query(models.AssetCategoryDef).filter(
        models.AssetCategoryDef.slug == cat_in.slug
    ).first()
    if existing:
        raise HTTPException(status_code=400, detail=f"品类 slug '{cat_in.slug}' 已存在")

    if cat_in.parent_id:
        parent = db.query(models.AssetCategoryDef).filter(
            models.AssetCategoryDef.id == cat_in.parent_id
        ).first()
        if not parent:
            raise HTTPException(status_code=400, detail="父品类不存在")

    cat = models.AssetCategoryDef(
        slug=cat_in.slug,
        name=cat_in.name,
        description=cat_in.description,
        icon=cat_in.icon,
        sub_type_kind=cat_in.sub_type_kind,
        parent_id=cat_in.parent_id,
    )
    db.add(cat)
    db.commit()
    db.refresh(cat)
    return _cat_response(cat)


@router.put("/{cat_id}", response_model=schemas.AssetCategoryDefResponse)
async def update_category(
    cat_id: int,
    update_in: schemas.AssetCategoryDefUpdate,
    db: Session = Depends(get_db),
    user: models.User = Depends(auth.require_role(models.UserRole.admin)),
):
    """Update category metadata. slug cannot be changed."""
    cat = db.query(models.AssetCategoryDef).filter(
        models.AssetCategoryDef.id == cat_id
    ).first()
    if not cat:
        raise HTTPException(status_code=404, detail="品类不存在")

    if update_in.name is not None:
        cat.name = update_in.name
    if update_in.description is not None:
        cat.description = update_in.description
    if update_in.icon is not None:
        cat.icon = update_in.icon
    if update_in.sub_type_kind is not None:
        cat.sub_type_kind = update_in.sub_type_kind
    if update_in.parent_id is not None:
        if update_in.parent_id == cat_id:
            raise HTTPException(status_code=400, detail="不能将自己设为父品类")
        parent = db.query(models.AssetCategoryDef).filter(
            models.AssetCategoryDef.id == update_in.parent_id
        ).first()
        if not parent:
            raise HTTPException(status_code=400, detail="父品类不存在")
        cat.parent_id = update_in.parent_id

    db.commit()
    db.refresh(cat)
    return _cat_response(cat)


@router.delete("/{cat_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_category(
    cat_id: int,
    db: Session = Depends(get_db),
    user: models.User = Depends(auth.require_role(models.UserRole.admin)),
):
    """Delete a category. Fails if any asset is linked to it."""
    cat = db.query(models.AssetCategoryDef).filter(
        models.AssetCategoryDef.id == cat_id
    ).first()
    if not cat:
        raise HTTPException(status_code=404, detail="品类不存在")

    # Check if any assets reference this category
    if cat.assets:
        raise HTTPException(
            status_code=400,
            detail=f"仍有 {len(cat.assets)} 个资产使用此品类，无法删除",
        )

    db.delete(cat)
    db.commit()
