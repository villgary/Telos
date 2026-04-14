from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError

from backend.database import get_db
from backend import models, schemas, auth

router = APIRouter(prefix="/api/v1/asset-relationships", tags=["资产关系"])


def _cycle_check(db: Session, parent_id: int, child_id: int) -> bool:
    """Return True if adding parent→child would create a cycle."""
    # BFS from child upward; if we reach parent, it's a cycle
    visited: set[int] = set()
    queue = [child_id]
    while queue:
        current = queue.pop(0)
        if current == parent_id:
            return True
        if current in visited:
            continue
        visited.add(current)
        # Walk up
        rels = db.query(models.AssetRelationship).filter(
            models.AssetRelationship.child_id == current
        ).all()
        for rel in rels:
            if rel.parent_id not in visited:
                queue.append(rel.parent_id)
    return False


@router.get("", response_model=list[schemas.AssetRelationshipResponse])
async def list_relationships(
    asset_id: int = None,
    db: Session = Depends(get_db),
    user: models.User = Depends(auth.get_current_user),
):
    """List all asset relationships, optionally filtered by asset_id."""
    query = db.query(models.AssetRelationship)
    if asset_id:
        query = query.filter(
            (models.AssetRelationship.parent_id == asset_id) |
            (models.AssetRelationship.child_id == asset_id)
        )
    return query.all()


@router.post("", response_model=schemas.AssetRelationshipResponse,
             status_code=status.HTTP_201_CREATED)
async def create_relationship(
    rel_in: schemas.AssetRelationshipCreate,
    db: Session = Depends(get_db),
    user: models.User = Depends(auth.require_role(models.UserRole.operator, models.UserRole.admin)),
):
    """Create an asset relationship (parent → child)."""
    if rel_in.parent_id == rel_in.child_id:
        raise HTTPException(status_code=400, detail="资产不能与自身建立关系")

    parent = db.query(models.Asset).filter(models.Asset.id == rel_in.parent_id).first()
    child = db.query(models.Asset).filter(models.Asset.id == rel_in.child_id).first()
    if not parent:
        raise HTTPException(status_code=404, detail=f"父资产 {rel_in.parent_id} 不存在")
    if not child:
        raise HTTPException(status_code=404, detail=f"子资产 {rel_in.child_id} 不存在")

    # Cycle detection
    if _cycle_check(db, rel_in.parent_id, rel_in.child_id):
        raise HTTPException(status_code=400, detail="该关系会形成循环引用，已拒绝")

    rel = models.AssetRelationship(
        parent_id=rel_in.parent_id,
        child_id=rel_in.child_id,
        relation_type=rel_in.relation_type,
        description=rel_in.description,
        created_by=user.id,
    )
    db.add(rel)
    try:
        db.commit()
        db.refresh(rel)
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=400, detail="该关系已存在")
    return rel


@router.put("/{rel_id}", response_model=schemas.AssetRelationshipResponse)
async def update_relationship(
    rel_id: int,
    rel_in: schemas.AssetRelationshipUpdate,
    db: Session = Depends(get_db),
    user: models.User = Depends(auth.require_role(models.UserRole.operator, models.UserRole.admin)),
):
    """Update a relationship's type or description."""
    rel = db.query(models.AssetRelationship).filter(
        models.AssetRelationship.id == rel_id
    ).first()
    if not rel:
        raise HTTPException(status_code=404, detail="关系不存在")

    if rel_in.relation_type is not None:
        rel.relation_type = rel_in.relation_type
    if rel_in.description is not None:
        rel.description = rel_in.description

    db.commit()
    db.refresh(rel)
    return rel


@router.delete("/{rel_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_relationship(
    rel_id: int,
    db: Session = Depends(get_db),
    user: models.User = Depends(auth.require_role(models.UserRole.operator, models.UserRole.admin)),
):
    """Delete a relationship."""
    rel = db.query(models.AssetRelationship).filter(
        models.AssetRelationship.id == rel_id
    ).first()
    if not rel:
        raise HTTPException(status_code=404, detail="关系不存在")
    db.delete(rel)
    db.commit()
