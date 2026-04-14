"""
Identity Fusion Service — cross-system account identity resolution.

Groups accounts by:
  - UID (Linux uid / Windows SID): 100% confidence
  - Exact username: 90% confidence
  - Email pattern: 80% confidence
  - Manual: 100% confidence
"""

import logging
from collections import defaultdict
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy.orm import Session

from backend import models

logger = logging.getLogger("identity_fusion")


def _guess_display_name(username: str) -> str:
    """Extract a human-readable display name from a username."""
    # Strip common suffixes: _cn, _w, _admin, _dev, _test
    name = username.lower()
    for suffix in ("_cn", "_w", "_admin", "_dev", "_test", "_prod"):
        if name.endswith(suffix):
            return username[:-len(suffix) - 1]
    return username


def _guess_email(username: str, hostname: Optional[str] = None) -> Optional[str]:
    """Infer email from username pattern."""
    if "@" in username:
        return username
    if hostname and ("ldap" in hostname or "ad" in hostname or "corp" in hostname):
        return f"{username}@company.com"
    return None


def fuse_identities(db: Session) -> dict:
    """
    Auto-match accounts across assets to build human identities.
    Returns summary dict.
    """
    # ── Step 1: gather latest snapshot per asset per username ────────────────
    # We need one snapshot per (asset, username) pair, prefer the latest scan
    assets = {a.id: a for a in db.query(models.Asset).all()}
    latest_job_ids = {a.id: a.last_scan_job_id for a in assets.values() if a.last_scan_job_id}

    if not latest_job_ids:
        return {"identities": 0, "links": 0, "matched_by": {}}

    # Get all snapshots from latest jobs
    all_snaps = db.query(models.AccountSnapshot).filter(
        models.AccountSnapshot.job_id.in_(latest_job_ids.values()),
        models.AccountSnapshot.deleted_at.is_(None),
    ).all()

    # De-duplicate: keep latest snapshot per (asset_id, username)
    snap_map: dict[tuple, models.AccountSnapshot] = {}
    for s in all_snaps:
        key = (s.asset_id, s.username)
        if key not in snap_map or s.snapshot_time > snap_map[key].snapshot_time:
            snap_map[key] = s

    snapshots = list(snap_map.values())
    logger.info(f"Identity fusion: {len(snapshots)} unique account snapshots across {len(assets)} assets")

    # ── Step 2: build groups ─────────────────────────────────────────────────
    # uid_map[uid_sid] = [snapshots]
    uid_map: dict[str, list[models.AccountSnapshot]] = defaultdict(list)
    # username_map[username] = [snapshots]
    username_map: dict[str, list[models.AccountSnapshot]] = defaultdict(list)

    for snap in snapshots:
        if snap.uid_sid:
            uid_map[snap.uid_sid].append(snap)
        username_map[snap.username.lower()].append(snap)

    # ── Step 3: create/update identities ──────────────────────────────────────
    now = datetime.now(timezone.utc)
    created = 0
    updated = 0
    matched_by = {"uid": 0, "username": 0}

    existing = {i.id: i for i in db.query(models.HumanIdentity).all()}
    existing_links = db.query(models.IdentityAccount).all()
    # snapshot_id → identity_id
    snap_to_identity: dict[int, int] = {la.snapshot_id: la.identity_id for la in existing_links}

    def _get_or_create(display_name: str, source: str, confidence: int, snap: models.AccountSnapshot) -> models.HumanIdentity:
        """Get existing or create new identity."""
        # Try to find by display_name matching an existing identity
        for ident in existing.values():
            if ident.display_name == display_name and ident.source == source:
                return ident
        # Create new
        ident = models.HumanIdentity(
            display_name=display_name,
            email=_guess_email(display_name, assets.get(snap.asset_id).hostname if snap.asset_id in assets else None),
            confidence=confidence,
            source=source,
        )
        db.add(ident)
        db.flush()
        existing[ident.id] = ident
        return ident

    def _ensure_link(ident: models.HumanIdentity, snap: models.AccountSnapshot,
                     match_type: str, confidence: int) -> bool:
        """Link snapshot to identity if not already linked. Returns True if new link."""
        if snap.id in snap_to_identity:
            return False  # already linked
        link = models.IdentityAccount(
            identity_id=ident.id,
            snapshot_id=snap.id,
            asset_id=snap.asset_id,
            match_type=match_type,
            match_confidence=confidence,
        )
        db.add(link)
        snap_to_identity[snap.id] = ident.id
        return True

    # UID matches: highest confidence
    for uid, snaps in uid_map.items():
        if len(snaps) < 2:
            continue
        # All share the same uid → same person
        base_snap = max(snaps, key=lambda s: s.snapshot_time)
        display_name = _guess_display_name(base_snap.username)
        ident = _get_or_create(display_name, "auto", 100, base_snap)
        ident.confidence = max(ident.confidence, 100)
        for snap in snaps:
            if _ensure_link(ident, snap, "uid", 100):
                updated += 1
        matched_by["uid"] += 1

    # Username matches: exact match across 2+ assets
    for uname_lower, snaps in username_map.items():
        # Skip if already all in a UID group (already handled)
        already_grouped = set()
        for snap in snaps:
            if snap.uid_sid and len(uid_map.get(snap.uid_sid, [])) >= 2:
                already_grouped.add(snap.id)
        remaining = [s for s in snaps if s.id not in already_grouped]
        if len(remaining) < 2:
            continue
        base_snap = max(remaining, key=lambda s: s.snapshot_time)
        display_name = _guess_display_name(base_snap.username)
        ident = _get_or_create(display_name, "auto", 90, base_snap)
        ident.confidence = max(ident.confidence, 90)
        for snap in remaining:
            if _ensure_link(ident, snap, "username", 90):
                updated += 1
        matched_by["username"] += 1

    # ── Step 4: update account_count on all identities ───────────────────────
    for ident in existing.values():
        links = [l for l in existing_links + list(snap_to_identity.keys())
                 if (isinstance(l, int) and snap_to_identity.get(l) == ident.id)
                 or (hasattr(l, 'identity_id') and l.identity_id == ident.id)]
        # Count from snap_to_identity
        count = sum(1 for sid, iid in snap_to_identity.items() if iid == ident.id)
        ident.account_count = count
        ident.updated_at = now

    db.commit()
    logger.info(f"Identity fusion complete: {len(existing)} identities, {updated} links added, {matched_by}")
    return {
        "identities": len(existing),
        "links": updated,
        "matched_by": matched_by,
    }


def get_identity_list(db: Session, search: Optional[str] = None,
                      limit: int = 50, offset: int = 0) -> tuple[list[dict], int]:
    """
    Return a list of identity summaries with computed stats.
    """
    query = db.query(models.HumanIdentity)

    if search:
        query = query.filter(
            (models.HumanIdentity.display_name.ilike(f"%{search}%"))
            | (models.HumanIdentity.email.ilike(f"%{search}%"))
        )

    total = query.count()
    identities = query.order_by(models.HumanIdentity.confidence.desc()).offset(offset).limit(limit).all()

    result = []
    for ident in identities:
        links = db.query(models.IdentityAccount).filter(
            models.IdentityAccount.identity_id == ident.id
        ).all()
        if not links:
            continue

        snap_ids = [l.snapshot_id for l in links]
        asset_ids = list({l.asset_id for l in links})

        snaps = db.query(models.AccountSnapshot).filter(
            models.AccountSnapshot.id.in_(snap_ids)
        ).all()
        snap_by_id = {s.id: s for s in snaps}

        assets = db.query(models.Asset).filter(models.Asset.id.in_(asset_ids)).all()
        assets_map = {a.id: a for a in assets}

        profiles = db.query(models.AssetRiskProfile).filter(
            models.AssetRiskProfile.asset_id.in_(asset_ids)
        ).all()
        risk_map = {p.asset_id: p.risk_score for p in profiles}

        admin_count = sum(1 for s in snaps if s.is_admin)
        latest_login = max((s.last_login for s in snaps if s.last_login), default=None)
        max_risk = max((risk_map.get(l.asset_id, 0) for l in links), default=0)

        account_items = []
        for l in links:
            snap = snap_by_id.get(l.snapshot_id)
            asset = assets_map.get(l.asset_id)
            account_items.append({
                "id": l.id,
                "snapshot_id": l.snapshot_id,
                "asset_id": l.asset_id,
                "asset_code": asset.asset_code if asset else "Unknown",
                "ip": asset.ip if asset else "?",
                "hostname": asset.hostname if asset else None,
                "username": snap.username if snap else "?",
                "uid_sid": snap.uid_sid if snap else "?",
                "is_admin": snap.is_admin if snap else False,
                "account_status": snap.account_status if snap else None,
                "last_login": snap.last_login if snap else None,
                "match_type": l.match_type,
                "match_confidence": l.match_confidence,
            })

        result.append({
            "id": ident.id,
            "display_name": ident.display_name,
            "email": ident.email,
            "confidence": ident.confidence,
            "source": ident.source,
            "account_count": len(snaps),
            "admin_count": admin_count,
            "asset_count": len(asset_ids),
            "max_risk_score": max_risk,
            "latest_login": latest_login,
            "accounts": account_items,
        })

    return result, total
