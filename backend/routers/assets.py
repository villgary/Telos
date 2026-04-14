from fastapi import APIRouter, Depends, HTTPException, status, BackgroundTasks, Request, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from sqlalchemy import or_
from datetime import datetime
from typing import Optional, List
import csv
import io

from backend.database import get_db
from backend import models, schemas, auth, encryption
from backend.models import AssetCategory, OSType, DBType, NetworkVendor, IoTType
from backend.services import ssh_scanner, win_scanner
from backend import schemas as S

router = APIRouter(prefix="/api/v1/assets", tags=["资产管理"])


def _log_action(db, user_id, action, target_type, target_id, detail=None, ip="unknown"):
    log = models.AuditLog(
        user_id=user_id,
        action=action,
        target_type=target_type,
        target_id=target_id,
        detail=detail,
        ip_address=ip,
    )
    db.add(log)


def _descendant_slugs(db: Session, parent_id: int) -> List[str]:
    """Recursively get all descendant slugs for a category."""
    cats = db.query(models.AssetCategoryDef).filter(
        models.AssetCategoryDef.parent_id == parent_id
    ).all()
    slugs = [c.slug for c in cats]
    for cat in cats:
        slugs.extend(_descendant_slugs(db, cat.id))
    return slugs


def _descendant_ids(db: Session, parent_id: int) -> List[int]:
    """Recursively get all descendant IDs for a category."""
    cats = db.query(models.AssetCategoryDef).filter(
        models.AssetCategoryDef.parent_id == parent_id
    ).all()
    ids = [c.id for c in cats]
    for cat in cats:
        ids.extend(_descendant_ids(db, cat.id))
    return ids


@router.get("", response_model=list[schemas.AssetResponse])
async def list_assets(
    q: str = Query(None, description="按 IP 或主机名搜索"),
    asset_category: str = Query(None),
    status_filter: str = Query(None, alias="status"),
    group_id: int = Query(None, description="按资产分组筛选"),
    category_id: int = Query(None, description="按资产品类筛选（含所有子品类）"),
    db: Session = Depends(get_db),
    user: models.User = Depends(auth.get_current_user),
):
    """
    List assets with optional search and filter.
    - q: search by IP or hostname (case-insensitive)
    - asset_category: filter by top-level category (server/database/network)
    - category_id: filter by exact category AND all its descendants (multi-level)
    - status: filter by online/offline/auth_failed/untested
    - group_id: filter by asset group
    """
    query = db.query(models.Asset)

    if q:
        q_lower = f"%{q.lower()}%"
        query = query.filter(
            or_(
                models.Asset.ip.ilike(q_lower),
                models.Asset.hostname.ilike(q_lower),
            )
        )
    if category_id is not None:
        cat = db.query(models.AssetCategoryDef).filter(
            models.AssetCategoryDef.id == category_id
        ).first()
        if cat:
            all_slugs = [cat.slug] + _descendant_slugs(db, cat.id)
            all_ids = [cat.id] + _descendant_ids(db, cat.id)
            query = query.filter(
                or_(
                    models.Asset.category_slug.in_(all_slugs),
                    models.Asset.asset_category_def_id.in_(all_ids),
                )
            )
        else:
            # Invalid category_id → no match
            query = query.filter(models.Asset.id < 0)
    elif asset_category:
        query = query.filter(models.Asset.asset_category == asset_category)
    if status_filter:
        query = query.filter(models.Asset.status == status_filter)
    if group_id is not None:
        query = query.filter(models.Asset.group_id == group_id)

    return query.order_by(models.Asset.created_at.desc()).all()


@router.get("/export.csv")
async def export_assets_csv(
    q: str = Query(None),
    asset_category: str = Query(None),
    category_id: int = Query(None, description="按资产品类ID筛选（含子品类）"),
    db: Session = Depends(get_db),
    user: models.User = Depends(auth.get_current_user),
):
    """Export assets as CSV."""
    query = db.query(models.Asset)
    if q:
        q_lower = f"%{q.lower()}%"
        query = query.filter(
            or_(
                models.Asset.ip.ilike(q_lower),
                models.Asset.hostname.ilike(q_lower),
            )
        )
    if category_id is not None:
        cat = db.query(models.AssetCategoryDef).filter(
            models.AssetCategoryDef.id == category_id
        ).first()
        if cat:
            all_slugs = [cat.slug] + _descendant_slugs(db, cat.id)
            all_ids = [cat.id] + _descendant_ids(db, cat.id)
            query = query.filter(
                or_(
                    models.Asset.category_slug.in_(all_slugs),
                    models.Asset.asset_category_def_id.in_(all_ids),
                )
            )
        else:
            query = query.filter(models.Asset.id < 0)
    elif asset_category:
        query = query.filter(models.Asset.asset_category == asset_category)

    assets = query.order_by(models.Asset.created_at.desc()).all()

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow([
        "IP", "主机名", "类别", "子类型", "端口", "状态",
        "最后扫描", "创建时间",
    ])
    for a in assets:
        sub_type = (a.db_type.value if a.db_type else
                    a.network_type.value if a.network_type else
                    a.os_type.value if a.os_type else "")
        writer.writerow([
            a.ip,
            a.hostname or "",
            a.asset_category.value,
            sub_type,
            a.port,
            a.status.value,
            a.last_scan_at.isoformat() if a.last_scan_at else "",
            a.created_at.isoformat(),
        ])

    output.seek(0)
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=assets.csv"},
    )


@router.post("/bulk-delete", status_code=status.HTTP_204_NO_CONTENT)
async def bulk_delete_assets(
    asset_ids: list[int],
    request: Request,
    db: Session = Depends(get_db),
    user: models.User = Depends(auth.require_role(models.UserRole.admin)),
):
    """
    Delete multiple assets in one operation (admin only).
    """
    if not asset_ids:
        raise HTTPException(status_code=400, detail="未指定要删除的资产")

    assets = db.query(models.Asset).filter(models.Asset.id.in_(asset_ids)).all()
    if len(assets) != len(asset_ids):
        found_ids = {a.id for a in assets}
        missing = [id for id in asset_ids if id not in found_ids]
        raise HTTPException(status_code=404, detail=f"资产不存在: {missing}")

    for asset in assets:
        _log_action(db, user.id, "asset.delete", "asset", asset.id,
                    {"ip": asset.ip, "bulk": True}, ip=auth.get_client_ip(request))
        # Cascade delete related records
        db.query(models.AccountSnapshot).filter(models.AccountSnapshot.asset_id == asset.id).delete()
        db.query(models.ScanJob).filter(models.ScanJob.asset_id == asset.id).delete()
        db.query(models.ScanSchedule).filter(models.ScanSchedule.asset_id == asset.id).delete()
        db.query(models.AssetRiskProfile).filter(models.AssetRiskProfile.asset_id == asset.id).delete()
        db.query(models.Alert).filter(models.Alert.asset_id == asset.id).delete()
        db.query(models.IdentityAccount).filter(models.IdentityAccount.asset_id == asset.id).delete()
        db.delete(asset)

    db.commit()


@router.post("", response_model=schemas.AssetResponse, status_code=status.HTTP_201_CREATED)
async def create_asset(
    asset_in: schemas.AssetCreate,
    request: Request,
    db: Session = Depends(get_db),
    user: models.User = Depends(auth.require_role(models.UserRole.operator, models.UserRole.admin)),
):
    ip = asset_in.ip
    port = asset_in.port or 22
    existing = db.query(models.Asset).filter(
        models.Asset.ip == ip,
        models.Asset.port == port,
    ).first()
    if existing:
        raise HTTPException(status_code=400, detail=f"资产 {ip}:{port} 已存在")

    # Generate asset_code: ASM-00001, ASM-00002, ...
    max_id = db.query(models.Asset.id).order_by(models.Asset.id.desc()).first()
    next_num = (max_id[0] + 1) if max_id else 1
    asset_code = f"ASM-{next_num:05d}"

    cred = db.query(models.Credential).filter(models.Credential.id == asset_in.credential_id).first()
    if not cred:
        raise HTTPException(status_code=400, detail="凭据不存在")

    # Resolve category: derive asset_category enum and sub-type from category_slug
    # Map sub_type_kind → (asset_category enum, sub_type_field)
    _SUBKIND_MAP = {
        "os":        (AssetCategory.server,   "os_type"),
        "database":  (AssetCategory.database, "db_type"),
        "network":   (AssetCategory.network,  "network_type"),
        "iot":       (AssetCategory.iot,     "iot_type"),
    }
    _SUBKIND_TO_ENUM = {"os": OSType, "database": DBType, "network": NetworkVendor, "iot": IoTType}

    final_cat_def_id = asset_in.asset_category_def_id
    final_cat_slug = asset_in.category_slug
    final_asset_category = asset_in.asset_category
    final_os_type = asset_in.os_type
    final_db_type = asset_in.db_type
    final_network_type = asset_in.network_type
    final_iot_type = asset_in.iot_type

    # Look up category by slug if provided
    cat_def = None
    if final_cat_slug:
        cat_def = db.query(models.AssetCategoryDef).filter(
            models.AssetCategoryDef.slug == final_cat_slug
        ).first()
        if not cat_def:
            raise HTTPException(status_code=400, detail=f"资产品类 '{final_cat_slug}' 不存在")
        final_cat_def_id = cat_def.id

    # If category def found, derive asset_category enum from its sub_type_kind
    # (ignore form's asset_category default — category_slug is the source of truth)
    if cat_def:
        # Determine which sub_type_kind to use: own value, or inherited from parent
        if cat_def.sub_type_kind and cat_def.sub_type_kind != "none":
            effective_kind = cat_def.sub_type_kind
        elif cat_def.parent_id:
            parent = db.query(models.AssetCategoryDef).filter(
                models.AssetCategoryDef.id == cat_def.parent_id
            ).first()
            effective_kind = (parent.sub_type_kind or "none") if parent else "none"
        else:
            effective_kind = cat_def.sub_type_kind or "none"

        mapped = _SUBKIND_MAP.get(effective_kind)
        if mapped:
            final_asset_category, _ = mapped
        elif final_asset_category is None:
            # No asset_category from form and sub_type_kind='none': derive from slug/parent
            _slug_lower = (final_cat_slug or "").lower()
            _parent_slug = (parent.slug.lower() if parent else "") if cat_def and cat_def.parent_id else ""
            if _parent_slug == "database":
                final_asset_category = AssetCategory.database
                for _db_member in DBType:
                    if _db_member.value == _slug_lower:
                        final_db_type = _db_member
                        break
            elif _parent_slug == "network":
                final_asset_category = AssetCategory.network
            elif _parent_slug == "iot":
                final_asset_category = AssetCategory.iot
            elif "linux" in _slug_lower or "ubuntu" in _slug_lower or _parent_slug == "linux":
                final_asset_category = AssetCategory.server
                final_os_type = OSType.linux
            elif "windows" in _slug_lower or _parent_slug == "windows":
                final_asset_category = AssetCategory.server
                final_os_type = OSType.windows
            else:
                final_asset_category = AssetCategory.server

        # Derive OS type from category slug (handles sub_type_kind='none' categories)
        # Substring matching covers: ubuntu-desktop, linux-server, windows-desktop, windows-server, etc.
        _slug_lower = (final_cat_slug or "").lower()
        if "linux" in _slug_lower or "ubuntu" in _slug_lower:
            final_os_type = OSType.linux
        elif "windows" in _slug_lower:
            final_os_type = OSType.windows
        elif effective_kind == "os":
            sub_enum_cls = _SUBKIND_TO_ENUM.get(effective_kind)
            if sub_enum_cls:
                for member in sub_enum_cls:
                    if member.value == final_cat_slug:
                        final_os_type = OSType(member.value)
                        break

    # Default ports
    if not port or port == 0:
        defaults = {
            "mysql": 3306, "postgresql": 5432, "redis": 6379,
            "mongodb": 27017, "mssql": 1433,
            "linux": 22, "windows": 445,
        }
        key = (final_db_type.value if final_db_type else
               final_os_type.value if final_os_type else None)
        port = defaults.get(key, 22) if key else 22

    asset = models.Asset(
        asset_code=asset_code,
        ip=asset_in.ip,
        hostname=asset_in.hostname,
        asset_category=final_asset_category,
        asset_category_def_id=final_cat_def_id,
        category_slug=final_cat_slug,
        os_type=final_os_type,
        db_type=final_db_type,
        network_type=final_network_type,
        iot_type=final_iot_type,
        port=port,
        credential_id=asset_in.credential_id,
        created_by=user.id,
    )
    db.add(asset)
    db.commit()
    db.refresh(asset)

    _log_action(db, user.id, "asset.create", "asset", asset.id,
                {"ip": asset.ip}, ip=auth.get_client_ip(request))
    db.commit()
    return asset


@router.get("/{asset_id}", response_model=schemas.AssetResponse)
async def get_asset(
    asset_id: int,
    db: Session = Depends(get_db),
    user: models.User = Depends(auth.get_current_user),
):
    asset = db.query(models.Asset).filter(models.Asset.id == asset_id).first()
    if not asset:
        raise HTTPException(status_code=404, detail="资产不存在")
    return asset


@router.get("/{asset_id}/hierarchy", response_model=schemas.HierarchyNode)
async def get_asset_hierarchy(
    asset_id: int,
    db: Session = Depends(get_db),
    user: models.User = Depends(auth.get_current_user),
):
    """Return the full hierarchy tree for an asset (children recursively) with account stats."""
    root = db.query(models.Asset).filter(models.Asset.id == asset_id).first()
    if not root:
        raise HTTPException(status_code=404, detail="资产不存在")

    # Pre-fetch all child relationships for the entire subtree
    all_child_rels = db.query(models.AssetRelationship, models.Asset).join(
        models.Asset, models.Asset.id == models.AssetRelationship.child_id
    ).filter(
        models.AssetRelationship.parent_id == asset_id
    ).all()

    # BFS: fetch all descendants and build child_map
    child_map: dict[int, list[tuple]] = {}
    for rel, child_asset in all_child_rels:
        child_map.setdefault(rel.parent_id, []).append((rel, child_asset))
    queue = [r.child_id for r, _ in all_child_rels]
    fetched_assets: dict[int, models.Asset] = {asset_id: root}
    fetched_assets.update({a.id: a for _, a in all_child_rels})

    while queue:
        next_batch = list(queue)
        queue.clear()
        rels_and_assets = db.query(models.AssetRelationship, models.Asset).join(
            models.Asset, models.Asset.id == models.AssetRelationship.child_id
        ).filter(
            models.AssetRelationship.parent_id.in_(next_batch)
        ).all()
        for rel, child_asset in rels_and_assets:
            child_map.setdefault(rel.parent_id, []).append((rel, child_asset))
            if child_asset.id not in fetched_assets:
                fetched_assets[child_asset.id] = child_asset
                queue.append(child_asset.id)

    # Pre-fetch snapshot stats for ALL assets in the tree (single query)
    all_asset_ids = list(fetched_assets.keys())
    latest_job_ids = {
        a.id: a.last_scan_job_id
        for a in fetched_assets.values()
        if a.last_scan_job_id
    }
    if latest_job_ids:
        snaps = db.query(models.AccountSnapshot).filter(
            models.AccountSnapshot.job_id.in_(latest_job_ids.values())
        ).all()
    else:
        snaps = []

    # Build per-asset snapshot stats
    snap_stats: dict[int, dict] = {aid: {"count": 0, "admin": 0, "recent": []} for aid in all_asset_ids}
    for snap in snaps:
        aid = snap.asset_id
        if aid not in snap_stats:
            continue
        snap_stats[aid]["count"] += 1
        if snap.is_admin:
            snap_stats[aid]["admin"] += 1
        if len(snap_stats[aid]["recent"]) < 10:
            snap_stats[aid]["recent"].append(schemas.AccountSummaryItem(
                id=snap.id,
                username=snap.username,
                is_admin=snap.is_admin,
                account_status=snap.account_status,
                last_login=snap.last_login,
            ))

    def build_node(aid: int, rel_type: Optional[str]) -> schemas.HierarchyNode:
        asset_obj = fetched_assets.get(aid)
        stats = snap_stats.get(aid, {"count": 0, "admin": 0, "recent": []})
        asset_summary = schemas.AssetSummary(
            id=asset_obj.id,
            asset_code=asset_obj.asset_code,
            ip=asset_obj.ip,
            hostname=asset_obj.hostname,
            asset_category=asset_obj.asset_category,
            account_count=stats["count"],
            admin_count=stats["admin"],
            latest_accounts=stats["recent"],
        )
        children = [
            build_node(child_asset.id, rel.relation_type.value)
            for rel, child_asset in child_map.get(aid, [])
        ]
        return schemas.HierarchyNode(
            asset=asset_summary,
            relation_type=rel_type,
            children=children,
        )

    return build_node(asset_id, None)


@router.put("/{asset_id}", response_model=schemas.AssetResponse)
async def update_asset(
    asset_id: int,
    asset_in: schemas.AssetUpdate,
    db: Session = Depends(get_db),
    user: models.User = Depends(auth.require_role(models.UserRole.operator, models.UserRole.admin)),
):
    asset = db.query(models.Asset).filter(models.Asset.id == asset_id).first()
    if not asset:
        raise HTTPException(status_code=404, detail="资产不存在")

    if asset_in.ip is not None:
        # unique 约束是 (ip, port)，所以两样都要查
        port_to_check = asset_in.port if asset_in.port is not None else asset.port
        existing = db.query(models.Asset).filter(
            models.Asset.ip == asset_in.ip,
            models.Asset.port == port_to_check,
            models.Asset.id != asset_id,
        ).first()
        if existing:
            raise HTTPException(status_code=400, detail=f"IP {asset_in.ip}:{port_to_check} 已被其他资产使用")
        asset.ip = asset_in.ip
    if asset_in.hostname is not None:
        asset.hostname = asset_in.hostname
    if asset_in.asset_category is not None:
        asset.asset_category = asset_in.asset_category
    if asset_in.asset_category_def_id is not None:
        cat_def = db.query(models.AssetCategoryDef).filter(
            models.AssetCategoryDef.id == asset_in.asset_category_def_id
        ).first()
        if not cat_def:
            raise HTTPException(status_code=400, detail="指定的资产品类不存在")
        asset.asset_category_def_id = asset_in.asset_category_def_id
    if asset_in.category_slug is not None:
        cat_def = db.query(models.AssetCategoryDef).filter(
            models.AssetCategoryDef.slug == asset_in.category_slug
        ).first()
        if not cat_def:
            raise HTTPException(status_code=400, detail=f"资产品类 '{asset_in.category_slug}' 不存在")
        asset.asset_category_def_id = cat_def.id
    if asset_in.group_id is not None:
        asset.group_id = asset_in.group_id
    if asset_in.os_type is not None:
        asset.os_type = asset_in.os_type
    if asset_in.db_type is not None:
        asset.db_type = asset_in.db_type
    if asset_in.network_type is not None:
        asset.network_type = asset_in.network_type
    if asset_in.iot_type is not None:
        asset.iot_type = asset_in.iot_type
    if asset_in.port is not None:
        asset.port = asset_in.port
    if asset_in.credential_id is not None:
        cred = db.query(models.Credential).filter(models.Credential.id == asset_in.credential_id).first()
        if not cred:
            raise HTTPException(status_code=400, detail="凭据不存在")
        asset.credential_id = asset_in.credential_id

    db.commit()
    db.refresh(asset)
    return asset


@router.delete("/{asset_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_asset(
    asset_id: int,
    request: Request,
    db: Session = Depends(get_db),
    user: models.User = Depends(auth.require_role(models.UserRole.operator, models.UserRole.admin)),
):
    asset = db.query(models.Asset).filter(models.Asset.id == asset_id).first()
    if not asset:
        raise HTTPException(status_code=404, detail="资产不存在")
    _log_action(db, user.id, "asset.delete", "asset", asset.id,
                {"ip": asset.ip}, ip=auth.get_client_ip(request))

    # Manually cascade delete related records to avoid FK constraint issues
    db.query(models.AccountSnapshot).filter(models.AccountSnapshot.asset_id == asset_id).delete()
    db.query(models.ScanJob).filter(models.ScanJob.asset_id == asset_id).delete()
    db.query(models.ScanSchedule).filter(models.ScanSchedule.asset_id == asset_id).delete()
    db.query(models.AssetRiskProfile).filter(models.AssetRiskProfile.asset_id == asset_id).delete()
    db.query(models.Alert).filter(models.Alert.asset_id == asset_id).delete()
    db.query(models.IdentityAccount).filter(models.IdentityAccount.asset_id == asset_id).delete()
    db.query(models.AssetRelationship).filter(
        (models.AssetRelationship.parent_id == asset_id) |
        (models.AssetRelationship.child_id == asset_id)
    ).delete()

    db.delete(asset)
    db.commit()


@router.post("/{asset_id}/test", response_model=dict)
async def test_connection(
    asset_id: int,
    db: Session = Depends(get_db),
    user: models.User = Depends(auth.require_role(models.UserRole.operator, models.UserRole.admin)),
):
    """Test connectivity for a server or database asset."""
    asset = db.query(models.Asset).filter(models.Asset.id == asset_id).first()
    if not asset:
        raise HTTPException(status_code=404, detail="资产不存在")

    cred = asset.credential

    # Decrypt credential
    if cred.auth_type == models.AuthType.password:
        password = encryption.decrypt(cred.password_enc) if cred.password_enc else None
        private_key = None
        passphrase = None
    else:
        password = None
        private_key = encryption.decrypt(cred.private_key_enc) if cred.private_key_enc else None
        passphrase = encryption.decrypt(cred.passphrase_enc) if cred.passphrase_enc else None

    if asset.asset_category == AssetCategory.database:
        from backend.services import db_scanner
        db_type_val = asset.db_type.value if asset.db_type else "mysql"
        result, _ = db_scanner.scan_asset(
            ip=asset.ip, port=asset.port or 0,
            username=cred.username, password=password,
            db_type=db_type_val, timeout=15,
        )
    elif asset.asset_category == AssetCategory.network:
        from backend.services import net_scanner
        result, _ = net_scanner.scan_asset(
            ip=asset.ip, port=asset.port,
            username=cred.username, password=password,
            private_key=private_key, passphrase=passphrase, timeout=15,
        )
    elif asset.os_type == models.OSType.linux:
        result, _ = ssh_scanner.scan_asset(
            ip=asset.ip, port=asset.port,
            username=cred.username, password=password,
            private_key=private_key, passphrase=passphrase, timeout=15,
        )
    else:
        result, _ = win_scanner.scan_asset(
            ip=asset.ip, port=asset.port,
            username=cred.username, password=password, timeout=15,
        )

    # Update asset status
    asset.status = models.AssetStatus(result.status)
    db.commit()

    return {
        "success": result.success,
        "status": result.status,
        "error": result.error,
    }
