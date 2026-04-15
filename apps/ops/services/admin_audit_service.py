from __future__ import annotations

from apps.accounts.audit import create_user_log
from apps.accounts.models import UserLogs
from apps.ops.models import AdminAuditLog


def log_admin_action(*, actor=None, action: str, target=None, summary: str, metadata: dict | None = None, request=None):
    target_type = ""
    target_id = ""
    if target is not None:
        target_type = target._meta.label
        target_id = str(getattr(target, "pk", ""))

    audit_entry = AdminAuditLog.objects.create(
        actor=actor if getattr(actor, "is_authenticated", False) else None,
        action=action,
        target_type=target_type,
        target_id=target_id,
        summary=summary,
        metadata_json=metadata or {},
    )
    create_user_log(
        action_type=UserLogs.ActionType.ADMIN_UPDATE,
        description=summary[:500],
        request=request,
        user=actor if getattr(actor, "is_authenticated", False) else None,
        target=target,
        is_success=True,
    )
    return audit_entry
