from __future__ import annotations

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.db import transaction

from apps.assets.models import Asset
from apps.reports.models import GeneratedReport
from apps.scans.models import ScanRequest
from apps.schedules.models import ScanSchedule
from apps.targets.models import Target


class Command(BaseCommand):
    help = "Backfill missing ownership fields across operational models."

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Preview ownership fixes without writing changes.",
        )
        parser.add_argument(
            "--fallback-username",
            default="",
            help="Prefer this username when assigning unresolved orphan records.",
        )

    def handle(self, *args, **options):
        dry_run = bool(options["dry_run"])
        fallback_username = (options.get("fallback_username") or "").strip()

        fallback_user = self._pick_fallback_user(preferred_username=fallback_username)
        User = get_user_model()
        if fallback_user:
            self.stdout.write(
                self.style.NOTICE(f"Using fallback user: {fallback_user.username} (id={fallback_user.pk})")
            )
        elif User.objects.exists():
            self.stdout.write(
                self.style.WARNING("No superadmin/securityadmin fallback user found; unresolved rows may remain.")
            )
        else:
            self.stdout.write(self.style.WARNING("No users exist; ownership backfill cannot assign fallback owners."))

        summary = {
            "targets_updated": 0,
            "scan_requests_updated": 0,
            "schedules_updated": 0,
            "reports_updated": 0,
            "assets_updated": 0,
            "unresolved": 0,
        }

        with transaction.atomic():
            summary["targets_updated"], unresolved = self._backfill_targets(fallback_user, dry_run=dry_run)
            summary["unresolved"] += unresolved

            summary["scan_requests_updated"], unresolved = self._backfill_scan_requests(
                fallback_user,
                dry_run=dry_run,
            )
            summary["unresolved"] += unresolved

            summary["schedules_updated"], unresolved = self._backfill_schedules(fallback_user, dry_run=dry_run)
            summary["unresolved"] += unresolved

            summary["reports_updated"], unresolved = self._backfill_reports(fallback_user, dry_run=dry_run)
            summary["unresolved"] += unresolved

            summary["assets_updated"], unresolved = self._backfill_assets(fallback_user, dry_run=dry_run)
            summary["unresolved"] += unresolved

            if dry_run:
                transaction.set_rollback(True)

        mode_label = "DRY RUN" if dry_run else "APPLIED"
        self.stdout.write(self.style.SUCCESS(f"[{mode_label}] Ownership backfill summary:"))
        for key, value in summary.items():
            self.stdout.write(f"  - {key}: {value}")

    @staticmethod
    def _pick_fallback_user(*, preferred_username: str = ""):
        User = get_user_model()
        if preferred_username:
            preferred = User.objects.filter(username=preferred_username).first()
            if preferred:
                return preferred

        superuser = User.objects.filter(is_superuser=True).order_by("id").first()
        if superuser:
            return superuser

        from apps.ops.services import permission_service

        for slug in (permission_service.SUPER_ADMIN, permission_service.SECURITY_ADMIN):
            user = (
                User.objects.select_related("profile__role")
                .filter(profile__role__slug=slug, is_active=True)
                .order_by("id")
                .first()
            )
            if user:
                return user

        return User.objects.filter(is_active=True).order_by("id").first()

    @staticmethod
    def _save_if_needed(instance, changed_fields: list[str], *, dry_run: bool) -> bool:
        if not changed_fields:
            return False
        if not dry_run:
            if "updated_at" in {field.name for field in instance._meta.fields} and "updated_at" not in changed_fields:
                changed_fields.append("updated_at")
            instance.save(update_fields=changed_fields)
        return True

    def _backfill_targets(self, fallback_user, *, dry_run: bool) -> tuple[int, int]:
        updated = 0
        unresolved = 0
        queryset = Target.objects.select_related("owner", "created_by").all()
        for target in queryset:
            changed_fields: list[str] = []
            owner = target.owner
            creator = target.created_by

            if owner is None:
                owner = creator or fallback_user
                if owner is not None:
                    target.owner = owner
                    changed_fields.append("owner")
            if creator is None:
                creator = owner or fallback_user
                if creator is not None:
                    target.created_by = creator
                    changed_fields.append("created_by")

            if target.owner_id is None or target.created_by_id is None:
                unresolved += 1

            if self._save_if_needed(target, changed_fields, dry_run=dry_run):
                updated += 1
        return updated, unresolved

    def _backfill_scan_requests(self, fallback_user, *, dry_run: bool) -> tuple[int, int]:
        updated = 0
        unresolved = 0
        queryset = ScanRequest.objects.select_related("target__owner", "target__created_by").filter(requested_by__isnull=True)
        for request in queryset:
            requested_by = request.target.owner or request.target.created_by or fallback_user
            if requested_by is None:
                unresolved += 1
                continue
            request.requested_by = requested_by
            if self._save_if_needed(request, ["requested_by"], dry_run=dry_run):
                updated += 1
        return updated, unresolved

    def _backfill_schedules(self, fallback_user, *, dry_run: bool) -> tuple[int, int]:
        updated = 0
        unresolved = 0
        queryset = ScanSchedule.objects.select_related("target__owner", "target__created_by").filter(created_by__isnull=True)
        for schedule in queryset:
            created_by = schedule.target.owner or schedule.target.created_by or fallback_user
            if created_by is None:
                unresolved += 1
                continue
            schedule.created_by = created_by
            if self._save_if_needed(schedule, ["created_by"], dry_run=dry_run):
                updated += 1
        return updated, unresolved

    def _backfill_reports(self, fallback_user, *, dry_run: bool) -> tuple[int, int]:
        updated = 0
        unresolved = 0
        queryset = GeneratedReport.objects.select_related(
            "source_execution__scan_request__requested_by",
            "source_result__execution__scan_request__requested_by",
            "comparison_left_result__execution__scan_request__requested_by",
            "comparison_right_result__execution__scan_request__requested_by",
            "asset__owner",
            "asset__target__owner",
            "asset__target__created_by",
        ).filter(generated_by__isnull=True)

        for report in queryset:
            generated_by = (
                getattr(getattr(report.source_execution, "scan_request", None), "requested_by", None)
                or getattr(getattr(getattr(report.source_result, "execution", None), "scan_request", None), "requested_by", None)
                or getattr(getattr(getattr(report.comparison_left_result, "execution", None), "scan_request", None), "requested_by", None)
                or getattr(getattr(getattr(report.comparison_right_result, "execution", None), "scan_request", None), "requested_by", None)
                or getattr(report.asset, "owner", None)
                or getattr(getattr(report.asset, "target", None), "owner", None)
                or getattr(getattr(report.asset, "target", None), "created_by", None)
                or fallback_user
            )
            if generated_by is None:
                unresolved += 1
                continue
            report.generated_by = generated_by
            if self._save_if_needed(report, ["generated_by"], dry_run=dry_run):
                updated += 1
        return updated, unresolved

    def _backfill_assets(self, fallback_user, *, dry_run: bool) -> tuple[int, int]:
        updated = 0
        unresolved = 0
        queryset = Asset.objects.select_related("target__owner", "target__created_by").prefetch_related("snapshots")

        for asset in queryset:
            changed_fields: list[str] = []
            owner = asset.owner

            if owner is None:
                latest_snapshot = asset.snapshots.order_by("-created_at").first()
                snapshot_owner = None
                if latest_snapshot and latest_snapshot.source_result:
                    snapshot_owner = getattr(
                        getattr(latest_snapshot.source_result.execution, "scan_request", None),
                        "requested_by",
                        None,
                    )

                owner = asset.target.owner if asset.target_id and asset.target and asset.target.owner_id else None
                if owner is None and asset.target_id and asset.target and asset.target.created_by_id:
                    owner = asset.target.created_by
                if owner is None and snapshot_owner is not None:
                    owner = snapshot_owner
                if owner is None:
                    owner = fallback_user

                if owner is not None:
                    asset.owner = owner
                    changed_fields.append("owner")
                else:
                    unresolved += 1

            if asset.owner and not asset.owner_name:
                asset.owner_name = asset.owner.username
                changed_fields.append("owner_name")

            if self._save_if_needed(asset, changed_fields, dry_run=dry_run):
                updated += 1

        return updated, unresolved
