"""
Diff engine: compare two sets of account snapshots.
"""

from typing import List, Dict, Tuple
from backend import models, schemas
from backend.models import DiffType, RiskLevel


def compute_diff(
    snapshots_a: List[models.AccountSnapshot],
    snapshots_b: List[models.AccountSnapshot],
) -> Tuple[List[schemas.DiffItem], Dict[str, int]]:
    """
    Compare snapshot set A (base) vs B (compare).

    Returns:
        (List[DiffItem], summary_dict)
    """
    items: List[schemas.DiffItem] = []
    summary: Dict[str, int] = {
        "added": 0,
        "removed": 0,
        "escalated": 0,
        "deactivated": 0,
        "modified": 0,
    }

    # Index by uid_sid for O(1) lookup
    snap_a_map: Dict[str, models.AccountSnapshot] = {s.uid_sid: s for s in snapshots_a}
    snap_b_map: Dict[str, models.AccountSnapshot] = {s.uid_sid: s for s in snapshots_b}

    all_uids = set(snap_a_map.keys()) | set(snap_b_map.keys())

    for uid_sid in all_uids:
        in_a = uid_sid in snap_a_map
        in_b = uid_sid in snap_b_map
        snap_a = snap_a_map.get(uid_sid)
        snap_b = snap_b_map.get(uid_sid)

        if in_a and not in_b:
            # Disappeared
            diff_type = DiffType.removed
            risk = RiskLevel.warning
            summary["removed"] += 1
            diff_item = schemas.DiffItem(
                diff_type=diff_type,
                risk_level=risk,
                username=snap_a.username,
                uid_sid=uid_sid,
                field_changes={"status": ("present", "absent")},
            )

        elif not in_a and in_b:
            # New account
            diff_type = DiffType.added
            risk = RiskLevel.critical
            summary["added"] += 1
            diff_item = schemas.DiffItem(
                diff_type=diff_type,
                risk_level=risk,
                username=snap_b.username,
                uid_sid=uid_sid,
                field_changes={"is_admin": (None, snap_b.is_admin)},
            )

        else:
            # Both exist — check for changes
            changes = {}
            diff_type = None
            risk = None
            if snap_a.is_admin != snap_b.is_admin:
                if not snap_a.is_admin and snap_b.is_admin:
                    diff_type = DiffType.escalated
                    risk = RiskLevel.critical
                    summary["escalated"] += 1
                elif snap_a.is_admin and not snap_b.is_admin:
                    diff_type = DiffType.deactivated
                    risk = RiskLevel.info
                    summary["deactivated"] += 1
                else:
                    diff_type = DiffType.modified
                    risk = RiskLevel.warning
                    summary["modified"] += 1
                changes["is_admin"] = (snap_a.is_admin, snap_b.is_admin)

            if snap_a.account_status != snap_b.account_status:
                changes["account_status"] = (snap_a.account_status, snap_b.account_status)

            if snap_a.shell != snap_b.shell:
                changes["shell"] = (snap_a.shell, snap_b.shell)

            if changes:
                # Handle case where only account_status/shell changed (not is_admin)
                if diff_type is None:
                    diff_type = DiffType.modified
                    risk = RiskLevel.warning
                    summary["modified"] += 1
                # Recompute risk for escalated if not already set
                diff_item = schemas.DiffItem(
                    diff_type=diff_type,
                    risk_level=risk,
                    username=snap_b.username,
                    uid_sid=uid_sid,
                    field_changes=changes,
                )
            else:
                # No meaningful changes
                continue

        items.append(diff_item)

    return items, summary
