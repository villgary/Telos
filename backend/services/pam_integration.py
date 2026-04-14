"""
PAM Integration Service — sync accounts and build comparison view.
"""

import logging
from collections import defaultdict
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy.orm import Session

from backend import models
from backend.services.pam_providers import get_provider, PAMAccount

logger = logging.getLogger("pam_integration")


def sync_integration(db: Session, integration_id: int) -> dict:
    """
    Sync one PAM integration: fetch accounts from provider,
    match to AccountScan assets, save results.
    Returns summary dict.
    """
    integration = db.query(models.PAMIntegration).filter(
        models.PAMIntegration.id == integration_id
    ).first()
    if not integration:
        return {"error": "Integration not found"}

    # Clear old synced accounts
    db.query(models.PAMSyncedAccount).filter(
        models.PAMSyncedAccount.integration_id == integration_id
    ).delete()

    try:
        provider = get_provider(integration.provider)
        pam_accounts = provider.fetch_accounts(integration.config or {})
    except Exception as e:
        integration.status = "error"
        integration.last_error = str(e)[:500]
        db.commit()
        logger.warning(f"PAM sync failed for integration {integration_id}: {e}")
        return {"error": str(e), "accounts_fetched": 0}

    # Build asset → snapshot lookup (by username)
    all_assets = {a.id: a for a in db.query(models.Asset).all()}
    job_ids = {a.last_scan_job_id for a in all_assets.values() if a.last_scan_job_id}

    if job_ids:
        all_snaps = db.query(models.AccountSnapshot).filter(
            models.AccountSnapshot.job_id.in_(job_ids),
            models.AccountSnapshot.deleted_at.is_(None),
        ).all()
    else:
        all_snaps = []

    # username_lower → list of (asset_id, snapshot_id, is_admin)
    snap_lookup: dict[str, list[tuple]] = defaultdict(list)
    for snap in all_snaps:
        snap_lookup[snap.username.lower()].append((snap.asset_id, snap.id, snap.is_admin))

    matched = 0
    unmatched_pam = 0

    for pam_acc in pam_accounts:
        # Try to match by username
        candidates = snap_lookup.get(pam_acc.account_name.lower(), [])
        best_match: Optional[tuple] = None
        if candidates:
            # Prefer privileged match
            privileged = [c for c in candidates if c[2]]
            best_match = (privileged or candidates)[0]

        asset_id = best_match[0] if best_match else None
        snapshot_id = best_match[1] if best_match else None
        is_admin = best_match[2] if best_match else False
        confidence = 100 if best_match else 0

        if best_match:
            matched += 1
        else:
            unmatched_pam += 1

        synced = models.PAMSyncedAccount(
            integration_id=integration_id,
            asset_id=asset_id,
            account_name=pam_acc.account_name,
            account_type=pam_acc.account_type,
            pam_status=pam_acc.pam_status,
            last_used=pam_acc.last_used,
            matched_snapshot_id=snapshot_id,
            match_confidence=confidence,
        )
        db.add(synced)

    integration.status = "active"
    integration.last_sync_at = datetime.now(timezone.utc)
    integration.last_error = None
    db.commit()

    logger.info(f"PAM sync complete: integration={integration_id}, matched={matched}, unmatched_pam={unmatched_pam}")
    return {
        "accounts_fetched": len(pam_accounts),
        "matched": matched,
        "unmatched_pam": unmatched_pam,
    }


def get_comparison(db: Session, integration_id: Optional[int] = None) -> list[dict]:
    """
    Build unified comparison view between PAM accounts and AccountScan.
    """
    query = db.query(models.PAMIntegration)
    if integration_id:
        query = query.filter(models.PAMIntegration.id == integration_id)

    integrations = query.all()
    results = []

    for integ in integrations:
        synced_accounts = db.query(models.PAMSyncedAccount).filter(
            models.PAMSyncedAccount.integration_id == integ.id
        ).all()

        # snapshot_id → (username, is_admin)
        snap_map: dict[int, tuple] = {}
        snap_ids = [s.matched_snapshot_id for s in synced_accounts if s.matched_snapshot_id]
        if snap_ids:
            snaps = db.query(models.AccountSnapshot).filter(
                models.AccountSnapshot.id.in_(snap_ids)
            ).all()
            snap_map = {s.id: (s.username, s.is_admin) for s in snaps}

        for acc in synced_accounts:
            snap_info = snap_map.get(acc.matched_snapshot_id)
            is_admin = snap_info[1] if snap_info else False

            # Determine comparison result
            if acc.asset_id and is_admin and acc.account_type != "privileged":
                result = "privileged_gap"
                result_label = "权限不匹配"
            elif acc.asset_id and is_admin:
                result = "compliant"
                result_label = "合规"
            elif acc.asset_id:
                result = "compliant"
                result_label = "合规"
            else:
                result = "unmanaged"
                result_label = "PAM有记录，AccountScan未发现"

            asset = db.query(models.Asset).get(acc.asset_id) if acc.asset_id else None

            results.append({
                "integration_name": integ.name,
                "integration_id": integ.id,
                "account_name": acc.account_name,
                "account_type": acc.account_type,
                "pam_status": acc.pam_status,
                "last_used": acc.last_used,
                "asset_code": asset.asset_code if asset else None,
                "asset_ip": asset.ip if asset else None,
                "is_admin": is_admin,
                "result": result,
                "result_label": result_label,
            })

    return results
