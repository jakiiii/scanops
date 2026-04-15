from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path

from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from apps.assets.models import Asset, AssetChangeLog, AssetSnapshot
from apps.notifications.models import Notification
from apps.ops.models import AppSetting, Role, SystemHealthSnapshot, UserProfile, WorkerStatusSnapshot
from apps.ops.services import app_settings_service, permission_service
from apps.reports.models import GeneratedReport, ReportTemplate
from apps.scans.models import ScanEventLog, ScanExecution, ScanPortResult, ScanProfile, ScanRequest, ScanResult
from apps.schedules.models import ScanSchedule, ScheduleRunLog
from apps.schedules.services.schedule_service import apply_next_run
from apps.targets.models import Target

User = get_user_model()


@dataclass(frozen=True, slots=True)
class DemoUserSpec:
    full_name: str
    username: str
    email: str
    role_slug: str
    password: str
    is_active: bool = True


class Command(BaseCommand):
    help = "Seed coherent, idempotent demo data for the full ScanOps development environment."

    def add_arguments(self, parser):
        parser.add_argument(
            "--allow-non-debug",
            action="store_true",
            help="Allow running this command when DEBUG is False.",
        )

    def handle(self, *args, **options):
        if not settings.DEBUG and not options["allow_non_debug"]:
            raise CommandError("Refusing to seed demo data with DEBUG=False. Use --allow-non-debug to override.")

        self.summary: dict[str, dict[str, int]] = {}
        now = timezone.now()

        roles = self.seed_roles()
        users, credentials = self.seed_users(roles)
        self.write_credentials_file(credentials)

        targets = self.seed_targets(users)
        profiles = self.seed_scan_profiles(users)
        scan_requests = self.seed_scan_requests(users, targets, profiles)
        executions = self.seed_scan_executions(scan_requests, now=now)
        results = self.seed_scan_results(executions, now=now)
        self.seed_scan_port_results(results)
        self.seed_scan_event_logs(executions, now=now)

        assets = self.seed_assets(users, targets, now=now)
        snapshots = self.seed_asset_snapshots(assets, results, now=now)
        self.seed_asset_change_logs(assets, snapshots, now=now)

        reports = self.seed_reports(users, results, executions, assets, now=now)
        schedules = self.seed_schedules(users, targets, profiles, now=now)
        self.seed_schedule_run_logs(schedules, executions, reports, now=now)
        self.seed_notifications(users, executions, results, schedules, assets, reports, now=now)

        self.seed_app_settings(users)
        self.seed_worker_status(now=now)
        self.seed_system_health(now=now)

        self.print_summary()

    def _track(self, key: str, created: bool):
        bucket = self.summary.setdefault(key, {"created": 0, "updated": 0})
        bucket["created" if created else "updated"] += 1

    def _upsert(self, key: str, model, lookup: dict, defaults: dict):
        obj, created = model.objects.update_or_create(defaults=defaults, **lookup)
        self._track(key, created)
        return obj

    @transaction.atomic
    def seed_roles(self) -> dict[str, Role]:
        roles = permission_service.bootstrap_default_roles()
        role_map = {role.slug: role for role in roles}

        for role in roles:
            group, created = Group.objects.get_or_create(name=role.name)
            self._track("groups", created)
            # Keep a role marker in group metadata via name convention only.
            if group.name != role.name:
                group.name = role.name
                group.save(update_fields=["name"])
                self._track("groups", False)
        return role_map

    @transaction.atomic
    def seed_users(self, roles: dict[str, Role]):
        specs = [
            DemoUserSpec("Super Admin", "superadmin", "superadmin@scanops.local", "super_admin", "ScanOps@Super123"),
            DemoUserSpec("Security Admin", "securityadmin", "securityadmin@scanops.local", "security_admin", "ScanOps@Security123"),
            DemoUserSpec("Analyst One", "analyst1", "analyst1@scanops.local", "analyst", "ScanOps@Analyst123"),
            DemoUserSpec("Analyst Two", "analyst2", "analyst2@scanops.local", "analyst", "ScanOps@Analyst123"),
            DemoUserSpec("Operator One", "operator1", "operator1@scanops.local", "operator", "ScanOps@Operator123"),
            DemoUserSpec("Operator Two", "operator2", "operator2@scanops.local", "operator", "ScanOps@Operator123"),
            DemoUserSpec("Viewer One", "viewer1", "viewer1@scanops.local", "viewer", "ScanOps@Viewer123"),
        ]

        users: dict[str, User] = {}
        credentials: list[dict] = []
        managed_group_names = {role.name for role in roles.values()}
        managed_groups = Group.objects.filter(name__in=managed_group_names)

        for spec in specs:
            first_name, last_name = self._split_name(spec.full_name)
            is_super_admin = spec.role_slug == "super_admin"
            is_security_admin = spec.role_slug == "security_admin"
            is_analyst = spec.role_slug == "analyst"
            is_operator = spec.role_slug == "operator"

            user = self._upsert(
                "users",
                User,
                {"username": spec.username},
                {
                    "email": spec.email,
                    "first_name": first_name,
                    "last_name": last_name,
                    "is_active": spec.is_active,
                    "is_staff": bool(is_super_admin or is_security_admin),
                    "is_superuser": bool(is_super_admin),
                    "is_administrator": bool(is_super_admin or is_security_admin),
                    "is_operator": bool(is_super_admin or is_security_admin or is_analyst or is_operator),
                },
            )

            user.set_password(spec.password)
            user.save(update_fields=["password"])

            role = roles[spec.role_slug]
            profile = self._upsert(
                "user_profiles",
                UserProfile,
                {"user": user},
                {
                    "display_name": spec.full_name,
                    "role": role,
                    "is_approved": True,
                    "is_internal_operator": spec.role_slug != "viewer",
                    "allowed_workspace": self._workspace_for_role(spec.role_slug),
                    "notes": f"Demo seeded user for role {role.name}.",
                    "force_password_reset": False,
                },
            )
            users[spec.username] = user

            user.groups.remove(*managed_groups)
            group = Group.objects.get(name=role.name)
            user.groups.add(group)

            credentials.append(
                {
                    "full_name": spec.full_name,
                    "username": user.username,
                    "email": user.email,
                    "role": role.name,
                    "password": spec.password,
                    "status": "Active" if user.is_active else "Inactive",
                }
            )

        return users, credentials

    def write_credentials_file(self, credentials: list[dict]):
        backup_dir = Path(settings.BASE_DIR) / "backup"
        backup_dir.mkdir(parents=True, exist_ok=True)
        output_file = backup_dir / "user.txt"

        lines = [
            "--------------------------------------------------",
            "Development Demo Users Only — Do Not Use in Production",
            "Generated for local ScanOps demo/testing",
            "--------------------------------------------------",
            "",
        ]
        for item in credentials:
            lines.extend(
                [
                    f"Name: {item['full_name']}",
                    f"Username: {item['username']}",
                    f"Email: {item['email']}",
                    f"Role: {item['role']}",
                    f"Password: {item['password']}",
                    f"Status: {item['status']}",
                    "--------------------------------------------------",
                    "",
                ]
            )

        output_file.write_text("\n".join(lines), encoding="utf-8")

    @transaction.atomic
    def seed_targets(self, users: dict[str, User]) -> dict[str, Target]:
        target_specs = [
            {
                "name": "Core App Server 01",
                "target_type": Target.TargetType.IP,
                "target_value": "10.10.1.5",
                "status": Target.Status.ACTIVE,
                "tags": "production,web,critical",
                "notes": "Primary internal app node.",
                "owner": users["securityadmin"],
                "created_by": users["superadmin"],
            },
            {
                "name": "Core App Server 02",
                "target_type": Target.TargetType.IP,
                "target_value": "10.10.1.10",
                "status": Target.Status.ACTIVE,
                "tags": "production,web,app",
                "notes": "Secondary app node.",
                "owner": users["securityadmin"],
                "created_by": users["superadmin"],
            },
            {
                "name": "DMZ Node",
                "target_type": Target.TargetType.IP,
                "target_value": "10.10.5.20",
                "status": Target.Status.RESTRICTED,
                "tags": "dmz,edge,restricted",
                "notes": "DMZ-facing service node. Restricted by policy.",
                "owner": users["securityadmin"],
                "created_by": users["superadmin"],
            },
            {
                "name": "Database Cluster Gateway",
                "target_type": Target.TargetType.IP,
                "target_value": "172.16.10.5",
                "status": Target.Status.ACTIVE,
                "tags": "database,internal",
                "notes": "Gateway address for database segment.",
                "owner": users["analyst1"],
                "created_by": users["securityadmin"],
            },
            {
                "name": "Internal API",
                "target_type": Target.TargetType.DOMAIN,
                "target_value": "internal-api.local",
                "status": Target.Status.ACTIVE,
                "tags": "api,internal",
                "notes": "Main internal API service.",
                "owner": users["analyst1"],
                "created_by": users["securityadmin"],
            },
            {
                "name": "Intranet Portal",
                "target_type": Target.TargetType.DOMAIN,
                "target_value": "intranet.local",
                "status": Target.Status.ACTIVE,
                "tags": "portal,web,corp",
                "notes": "Corporate intranet frontend.",
                "owner": users["analyst2"],
                "created_by": users["securityadmin"],
            },
            {
                "name": "DB Core",
                "target_type": Target.TargetType.DOMAIN,
                "target_value": "db-core.local",
                "status": Target.Status.ACTIVE,
                "tags": "database,critical",
                "notes": "Primary DB core hostname.",
                "owner": users["operator1"],
                "created_by": users["securityadmin"],
            },
            {
                "name": "File Server",
                "target_type": Target.TargetType.DOMAIN,
                "target_value": "fileserver.local",
                "status": Target.Status.ACTIVE,
                "tags": "storage,smb,internal",
                "notes": "Internal file storage node.",
                "owner": users["operator1"],
                "created_by": users["securityadmin"],
            },
            {
                "name": "Monitoring Service",
                "target_type": Target.TargetType.DOMAIN,
                "target_value": "monitoring.local",
                "status": Target.Status.ACTIVE,
                "tags": "monitoring,ops",
                "notes": "Monitoring and observability stack endpoint.",
                "owner": users["operator2"],
                "created_by": users["securityadmin"],
            },
            {
                "name": "App Gateway",
                "target_type": Target.TargetType.DOMAIN,
                "target_value": "app-gateway.local",
                "status": Target.Status.ACTIVE,
                "tags": "gateway,proxy",
                "notes": "Primary internal application gateway.",
                "owner": users["operator2"],
                "created_by": users["securityadmin"],
            },
            {
                "name": "Corp Segment",
                "target_type": Target.TargetType.CIDR,
                "target_value": "192.168.10.0/24",
                "status": Target.Status.ACTIVE,
                "tags": "network,segment",
                "notes": "Corporate endpoint VLAN segment.",
                "owner": users["analyst2"],
                "created_by": users["superadmin"],
            },
            {
                "name": "IPv6 Ops Node",
                "target_type": Target.TargetType.IPV6,
                "target_value": "fd00::10",
                "status": Target.Status.INACTIVE,
                "tags": "ipv6,lab",
                "notes": "Lab IPv6 node for compatibility validation.",
                "owner": users["viewer1"],
                "created_by": users["superadmin"],
            },
        ]

        targets: dict[str, Target] = {}
        for spec in target_specs:
            target = self._upsert(
                "targets",
                Target,
                {
                    "target_type": spec["target_type"],
                    "target_value": spec["target_value"],
                },
                {
                    "name": spec["name"],
                    "status": spec["status"],
                    "tags": spec["tags"],
                    "notes": spec["notes"],
                    "owner": spec["owner"],
                    "created_by": spec["created_by"],
                },
            )
            targets[spec["target_value"]] = target
        return targets

    @transaction.atomic
    def seed_scan_profiles(self, users: dict[str, User]) -> dict[str, ScanProfile]:
        profile_specs = [
            {
                "name": "Host Discovery",
                "description": "Network host discovery with minimal service probing.",
                "scan_type": ScanProfile.ScanType.HOST_DISCOVERY,
                "port_scope": "",
                "timing_profile": ScanProfile.TimingProfile.BALANCED,
                "flags": dict(host=True, service=False, version=False, os=False, trace=False, dns=True),
                "is_system": True,
            },
            {
                "name": "Quick TCP Scan",
                "description": "Quick internal TCP baseline scan.",
                "scan_type": ScanProfile.ScanType.QUICK_TCP,
                "port_scope": "22,80,443,3389",
                "timing_profile": ScanProfile.TimingProfile.FAST,
                "flags": dict(host=True, service=True, version=False, os=False, trace=False, dns=True),
                "is_system": True,
            },
            {
                "name": "Top 100 Ports",
                "description": "Top 100 common ports with service fingerprints.",
                "scan_type": ScanProfile.ScanType.TOP_100,
                "port_scope": "top-100",
                "timing_profile": ScanProfile.TimingProfile.BALANCED,
                "flags": dict(host=True, service=True, version=True, os=False, trace=False, dns=True),
                "is_system": True,
            },
            {
                "name": "Top 1000 Ports",
                "description": "Top 1000 TCP ports for broader baseline coverage.",
                "scan_type": ScanProfile.ScanType.TOP_1000,
                "port_scope": "top-1000",
                "timing_profile": ScanProfile.TimingProfile.NORMAL,
                "flags": dict(host=True, service=True, version=True, os=False, trace=False, dns=True),
                "is_system": True,
            },
            {
                "name": "Service Detection",
                "description": "Focused service and version detection pass.",
                "scan_type": ScanProfile.ScanType.SERVICE_DETECTION,
                "port_scope": "1-1024",
                "timing_profile": ScanProfile.TimingProfile.NORMAL,
                "flags": dict(host=True, service=True, version=True, os=True, trace=False, dns=True),
                "is_system": True,
            },
            {
                "name": "Safe Basic Scan",
                "description": "Low-impact standard scan template for daily operations.",
                "scan_type": ScanProfile.ScanType.SAFE_BASIC,
                "port_scope": "80,443,8080,8443",
                "timing_profile": ScanProfile.TimingProfile.BALANCED,
                "flags": dict(host=True, service=True, version=False, os=False, trace=False, dns=True),
                "is_system": True,
            },
            {
                "name": "Internal Web Audit",
                "description": "Internal web stack review profile for HTTP/HTTPS services.",
                "scan_type": ScanProfile.ScanType.SERVICE_DETECTION,
                "port_scope": "80,443,8080,8443,9000",
                "timing_profile": ScanProfile.TimingProfile.NORMAL,
                "flags": dict(host=True, service=True, version=True, os=False, trace=True, dns=True),
                "is_system": False,
            },
            {
                "name": "Database Port Review",
                "description": "Database segment scan profile for common DB ports.",
                "scan_type": ScanProfile.ScanType.TOP_100,
                "port_scope": "1433,1521,3306,5432,6379,27017",
                "timing_profile": ScanProfile.TimingProfile.BALANCED,
                "flags": dict(host=True, service=True, version=True, os=False, trace=False, dns=True),
                "is_system": False,
            },
        ]

        profiles: dict[str, ScanProfile] = {}
        for spec in profile_specs:
            flags = spec["flags"]
            profile = self._upsert(
                "scan_profiles",
                ScanProfile,
                {"name": spec["name"]},
                {
                    "description": spec["description"],
                    "scan_type": spec["scan_type"],
                    "port_scope": spec["port_scope"],
                    "enable_host_discovery": flags["host"],
                    "enable_service_detection": flags["service"],
                    "enable_version_detection": flags["version"],
                    "enable_os_detection": flags["os"],
                    "enable_traceroute": flags["trace"],
                    "enable_dns_resolution": flags["dns"],
                    "timing_profile": spec["timing_profile"],
                    "is_system": spec["is_system"],
                    "is_active": True,
                    "created_by": users["securityadmin"],
                },
            )
            profiles[spec["name"]] = profile
        return profiles

    @transaction.atomic
    def seed_scan_requests(self, users: dict[str, User], targets: dict[str, Target], profiles: dict[str, ScanProfile]):
        request_specs = [
            {
                "seed": "SRQ-001",
                "target": "10.10.1.5",
                "profile": "Safe Basic Scan",
                "scan_type": ScanProfile.ScanType.SAFE_BASIC,
                "port_input": "80,443,8080",
                "status": ScanRequest.Status.VALIDATED,
                "validation_summary": "Policy check passed. Approved for immediate execution.",
                "requested_by": "analyst1",
                "timing": ScanProfile.TimingProfile.BALANCED,
            },
            {
                "seed": "SRQ-002",
                "target": "internal-api.local",
                "profile": "Internal Web Audit",
                "scan_type": ScanProfile.ScanType.SERVICE_DETECTION,
                "port_input": "80,443,8443",
                "status": ScanRequest.Status.PENDING,
                "validation_summary": "Pending security admin review due to traceroute option.",
                "requested_by": "analyst2",
                "timing": ScanProfile.TimingProfile.NORMAL,
            },
            {
                "seed": "SRQ-003",
                "target": "db-core.local",
                "profile": "Database Port Review",
                "scan_type": ScanProfile.ScanType.TOP_100,
                "port_input": "3306,5432,6379",
                "status": ScanRequest.Status.DRAFT,
                "validation_summary": "Draft saved for maintenance window.",
                "requested_by": "operator1",
                "timing": ScanProfile.TimingProfile.BALANCED,
            },
            {
                "seed": "SRQ-004",
                "target": "10.10.5.20",
                "profile": "Top 1000 Ports",
                "scan_type": ScanProfile.ScanType.TOP_1000,
                "port_input": "1-1000",
                "status": ScanRequest.Status.REJECTED,
                "validation_summary": "Rejected by policy: target in restricted DMZ range without override.",
                "requested_by": "operator2",
                "timing": ScanProfile.TimingProfile.NORMAL,
            },
            {
                "seed": "SRQ-005",
                "target": "monitoring.local",
                "profile": "Quick TCP Scan",
                "scan_type": ScanProfile.ScanType.QUICK_TCP,
                "port_input": "22,80,443,9100",
                "status": ScanRequest.Status.VALIDATED,
                "validation_summary": "Validated for routine monitoring baseline check.",
                "requested_by": "securityadmin",
                "timing": ScanProfile.TimingProfile.FAST,
            },
            {
                "seed": "SRQ-006",
                "target": "192.168.10.0/24",
                "profile": "Host Discovery",
                "scan_type": ScanProfile.ScanType.HOST_DISCOVERY,
                "port_input": "",
                "status": ScanRequest.Status.PENDING,
                "validation_summary": "Pending approval for broad network host discovery.",
                "requested_by": "superadmin",
                "timing": ScanProfile.TimingProfile.BALANCED,
            },
        ]

        requests: dict[str, ScanRequest] = {}
        for spec in request_specs:
            note_key = f"seed:scan-request:{spec['seed']}"
            request = self._upsert(
                "scan_requests",
                ScanRequest,
                {"notes": note_key},
                {
                    "target": targets[spec["target"]],
                    "profile": profiles[spec["profile"]],
                    "scan_type": spec["scan_type"],
                    "port_input": spec["port_input"],
                    "enable_host_discovery": True,
                    "enable_service_detection": True,
                    "enable_version_detection": True,
                    "enable_os_detection": False,
                    "enable_traceroute": spec["seed"] in {"SRQ-002", "SRQ-006"},
                    "enable_dns_resolution": True,
                    "timing_profile": spec["timing"],
                    "status": spec["status"],
                    "validation_summary": spec["validation_summary"],
                    "requested_by": users[spec["requested_by"]],
                },
            )
            requests[spec["seed"]] = request
        return requests

    @transaction.atomic
    def seed_scan_executions(self, requests: dict[str, ScanRequest], *, now):
        execution_specs = [
            {
                "execution_id": "DEMO-EXE-1001",
                "request": "SRQ-001",
                "status": ScanExecution.Status.COMPLETED,
                "queue_status": ScanExecution.QueueStatus.DONE,
                "worker": "worker-alpha",
                "progress": 100,
                "stage": "Completed",
                "message": "Scan finished successfully.",
                "started_delta": timezone.timedelta(hours=6),
                "duration_seconds": 412,
                "priority": 2,
            },
            {
                "execution_id": "DEMO-EXE-1002",
                "request": "SRQ-002",
                "status": ScanExecution.Status.RUNNING,
                "queue_status": ScanExecution.QueueStatus.PROCESSING,
                "worker": "worker-bravo",
                "progress": 63,
                "stage": "Service Detection",
                "message": "Service probes in progress.",
                "started_delta": timezone.timedelta(minutes=35),
                "duration_seconds": 1260,
                "priority": 3,
            },
            {
                "execution_id": "DEMO-EXE-1003",
                "request": "SRQ-003",
                "status": ScanExecution.Status.QUEUED,
                "queue_status": ScanExecution.QueueStatus.WAITING,
                "worker": "worker-charlie",
                "progress": 0,
                "stage": "Queued",
                "message": "Awaiting worker assignment.",
                "started_delta": None,
                "duration_seconds": 0,
                "priority": 4,
            },
            {
                "execution_id": "DEMO-EXE-1004",
                "request": "SRQ-004",
                "status": ScanExecution.Status.FAILED,
                "queue_status": ScanExecution.QueueStatus.ERROR,
                "worker": "worker-bravo",
                "progress": 21,
                "stage": "Host Discovery",
                "message": "Scan aborted due to policy/network error.",
                "started_delta": timezone.timedelta(hours=2, minutes=10),
                "duration_seconds": 233,
                "priority": 1,
            },
            {
                "execution_id": "DEMO-EXE-1005",
                "request": "SRQ-005",
                "status": ScanExecution.Status.CANCELLED,
                "queue_status": ScanExecution.QueueStatus.ERROR,
                "worker": "worker-alpha",
                "progress": 15,
                "stage": "Cancelled",
                "message": "Execution manually cancelled by admin.",
                "started_delta": timezone.timedelta(hours=1, minutes=20),
                "duration_seconds": 89,
                "priority": 3,
            },
        ]

        executions: dict[str, ScanExecution] = {}
        for spec in execution_specs:
            started_at = now - spec["started_delta"] if spec["started_delta"] else None
            completed_at = None
            if spec["status"] in {ScanExecution.Status.COMPLETED, ScanExecution.Status.FAILED, ScanExecution.Status.CANCELLED} and started_at:
                completed_at = started_at + timezone.timedelta(seconds=spec["duration_seconds"])

            execution = self._upsert(
                "scan_executions",
                ScanExecution,
                {"execution_id": spec["execution_id"]},
                {
                    "scan_request": requests[spec["request"]],
                    "status": spec["status"],
                    "queue_status": spec["queue_status"],
                    "started_at": started_at,
                    "completed_at": completed_at,
                    "duration_seconds": spec["duration_seconds"],
                    "worker_name": spec["worker"],
                    "progress_percent": spec["progress"],
                    "current_stage": spec["stage"],
                    "status_message": spec["message"],
                    "is_archived": False,
                    "priority": spec["priority"],
                },
            )
            executions[spec["execution_id"]] = execution
        return executions

    @transaction.atomic
    def seed_scan_results(self, executions: dict[str, ScanExecution], *, now):
        result_specs = [
            {
                "execution_id": "DEMO-EXE-1001",
                "host_status": ScanResult.HostStatus.UP,
                "open_ports": 5,
                "closed_ports": 120,
                "filtered_ports": 18,
                "services": 5,
                "os_guess": "Ubuntu Linux 22.04 LTS",
                "raw_output_text": "Nmap scan report for 10.10.1.5\nHost is up (0.005s latency).\nPORT     STATE SERVICE VERSION\n22/tcp   open  ssh     OpenSSH 8.9p1\n80/tcp   open  http    nginx 1.24.0\n443/tcp  open  https   nginx 1.24.0\n3306/tcp open  mysql   MySQL 8.0.34\n8080/tcp open  http    Internal API Gateway",
                "parsed_output_json": {
                    "host": "10.10.1.5",
                    "status": "up",
                    "ports": [22, 80, 443, 3306, 8080],
                    "services": ["ssh", "http", "https", "mysql", "http"],
                },
                "traceroute_data_json": [{"hop": 1, "ip": "10.10.1.1"}, {"hop": 2, "ip": "10.10.1.5"}],
                "script_output_json": {"http-title": "ScanOps Internal API", "ssh-hostkey": "rsa-sha2-512"},
            },
            {
                "execution_id": "DEMO-EXE-1002",
                "host_status": ScanResult.HostStatus.UP,
                "open_ports": 4,
                "closed_ports": 97,
                "filtered_ports": 12,
                "services": 4,
                "os_guess": "Debian GNU/Linux 12",
                "raw_output_text": "Nmap scan report for internal-api.local\nHost is up.\nPORT     STATE SERVICE VERSION\n80/tcp   open  http    nginx 1.22\n443/tcp  open  https   nginx 1.22\n8443/tcp open  ssl/http Java Spring Boot\n9000/tcp open  http    Metrics Endpoint",
                "parsed_output_json": {
                    "host": "internal-api.local",
                    "status": "up",
                    "ports": [80, 443, 8443, 9000],
                    "services": ["http", "https", "ssl/http", "http"],
                },
                "traceroute_data_json": [{"hop": 1, "ip": "10.10.5.1"}, {"hop": 2, "ip": "10.10.5.10"}],
                "script_output_json": {"ssl-cert": "CN=internal-api.local", "http-security-headers": "partial"},
            },
            {
                "execution_id": "DEMO-EXE-1004",
                "host_status": ScanResult.HostStatus.PARTIAL,
                "open_ports": 2,
                "closed_ports": 18,
                "filtered_ports": 230,
                "services": 2,
                "os_guess": "Unknown (firewalled)",
                "raw_output_text": "Nmap scan report for 10.10.5.20\nHost seems down or heavily filtered.\nPORT     STATE    SERVICE\n443/tcp  open     https\n8443/tcp filtered https-alt",
                "parsed_output_json": {
                    "host": "10.10.5.20",
                    "status": "partial",
                    "ports": [443, 8443],
                    "services": ["https", "https-alt"],
                    "notes": ["heavy filtering", "policy restriction"],
                },
                "traceroute_data_json": [{"hop": 1, "ip": "10.10.5.1"}, {"hop": 2, "ip": "10.10.5.20"}],
                "script_output_json": {"policy-check": "restricted target"},
            },
            {
                "execution_id": "DEMO-EXE-1005",
                "host_status": ScanResult.HostStatus.UNKNOWN,
                "open_ports": 1,
                "closed_ports": 6,
                "filtered_ports": 44,
                "services": 1,
                "os_guess": "N/A",
                "raw_output_text": "Execution cancelled before full completion.\nPartial data retained for audit.",
                "parsed_output_json": {"status": "cancelled", "partial": True, "ports": [9100]},
                "traceroute_data_json": [],
                "script_output_json": {"cancel_reason": "manual_admin_stop"},
            },
        ]

        results: dict[str, ScanResult] = {}
        for spec in result_specs:
            execution = executions[spec["execution_id"]]
            target_snapshot = execution.scan_request.target.target_value
            result = self._upsert(
                "scan_results",
                ScanResult,
                {"execution": execution},
                {
                    "target_snapshot": target_snapshot,
                    "host_status": spec["host_status"],
                    "total_open_ports": spec["open_ports"],
                    "total_closed_ports": spec["closed_ports"],
                    "total_filtered_ports": spec["filtered_ports"],
                    "total_services_detected": spec["services"],
                    "os_guess": spec["os_guess"],
                    "raw_output_text": spec["raw_output_text"],
                    "raw_output_xml": f"<nmaprun><host><address addr='{target_snapshot}'/></host></nmaprun>",
                    "parsed_output_json": spec["parsed_output_json"],
                    "traceroute_data_json": spec["traceroute_data_json"],
                    "script_output_json": spec["script_output_json"],
                    "result_summary": {
                        "seed_ref": f"result:{spec['execution_id']}",
                        "risk_hint": "high" if spec["open_ports"] >= 5 else "medium",
                    },
                    "generated_at": now - timezone.timedelta(minutes=45),
                },
            )
            results[spec["execution_id"]] = result
        return results

    @transaction.atomic
    def seed_scan_port_results(self, results: dict[str, ScanResult]):
        port_specs = {
            "DEMO-EXE-1001": [
                (22, "tcp", "open", "ssh", "OpenSSH 8.9p1", ScanPortResult.RiskLevel.MEDIUM),
                (80, "tcp", "open", "http", "nginx 1.24.0", ScanPortResult.RiskLevel.LOW),
                (443, "tcp", "open", "https", "nginx TLS", ScanPortResult.RiskLevel.LOW),
                (3306, "tcp", "open", "mysql", "MySQL 8.0.34", ScanPortResult.RiskLevel.HIGH),
                (8080, "tcp", "open", "http-proxy", "Internal app service", ScanPortResult.RiskLevel.MEDIUM),
                (53, "udp", "open", "domain", "Internal DNS", ScanPortResult.RiskLevel.LOW),
            ],
            "DEMO-EXE-1002": [
                (80, "tcp", "open", "http", "nginx 1.22", ScanPortResult.RiskLevel.LOW),
                (443, "tcp", "open", "https", "nginx TLS", ScanPortResult.RiskLevel.LOW),
                (8443, "tcp", "open", "https-alt", "Admin console", ScanPortResult.RiskLevel.HIGH),
                (9000, "tcp", "open", "http", "Metrics endpoint", ScanPortResult.RiskLevel.MEDIUM),
            ],
            "DEMO-EXE-1004": [
                (443, "tcp", "open", "https", "Edge HTTPS", ScanPortResult.RiskLevel.MEDIUM),
                (8443, "tcp", "filtered", "https-alt", "Filtered admin endpoint", ScanPortResult.RiskLevel.HIGH),
            ],
            "DEMO-EXE-1005": [
                (9100, "tcp", "open", "jetdirect", "Node exporter", ScanPortResult.RiskLevel.INFO),
            ],
        }

        for execution_id, entries in port_specs.items():
            result = results.get(execution_id)
            if result is None:
                continue
            for port, protocol, state, service, version, risk in entries:
                self._upsert(
                    "scan_port_results",
                    ScanPortResult,
                    {"result": result, "port": port, "protocol": protocol},
                    {
                        "state": state,
                        "service_name": service,
                        "service_version": version,
                        "risk_level": risk,
                        "extra_data_json": {"seed_ref": f"port:{execution_id}:{port}/{protocol}"},
                    },
                )

    @transaction.atomic
    def seed_scan_event_logs(self, executions: dict[str, ScanExecution], *, now):
        event_specs = {
            "DEMO-EXE-1001": [
                ("queued", "Execution queued by scheduler."),
                ("started", "Worker accepted execution."),
                ("host_discovery_complete", "Host discovery completed."),
                ("service_detection_complete", "Service detection completed."),
                ("parsing_complete", "Result parsing completed."),
                ("completed", "Execution completed successfully."),
            ],
            "DEMO-EXE-1002": [
                ("queued", "Execution queued by analyst."),
                ("started", "Worker started execution."),
                ("host_discovery_complete", "Host discovery completed."),
                ("service_detection_complete", "Service probes in progress."),
            ],
            "DEMO-EXE-1003": [
                ("queued", "Execution queued and awaiting assignment."),
            ],
            "DEMO-EXE-1004": [
                ("queued", "Execution queued."),
                ("started", "Execution started on worker."),
                ("failed", "Execution failed due to policy restriction."),
            ],
            "DEMO-EXE-1005": [
                ("queued", "Execution queued."),
                ("started", "Execution started."),
                ("cancelled", "Execution manually cancelled by administrator."),
            ],
        }

        for execution_id, events in event_specs.items():
            execution = executions[execution_id]
            for index, (event_type, message) in enumerate(events, start=1):
                lookup = {"execution": execution, "event_type": event_type, "message": message}
                existing = ScanEventLog.objects.filter(**lookup).order_by("id").first()
                if existing:
                    existing.metadata_json = {"seed_ref": f"log:{execution_id}:{index}"}
                    existing.save(update_fields=["metadata_json"])
                    self._track("scan_event_logs", False)
                else:
                    ScanEventLog.objects.create(
                        execution=execution,
                        event_type=event_type,
                        message=message,
                        metadata_json={"seed_ref": f"log:{execution_id}:{index}"},
                        created_at=now - timezone.timedelta(minutes=20 - index),
                    )
                    self._track("scan_event_logs", True)

    @transaction.atomic
    def seed_assets(self, users: dict[str, User], targets: dict[str, Target], *, now):
        asset_specs = [
            {
                "name": "web-01.internal",
                "target": "10.10.1.5",
                "hostname": "web-01.internal",
                "ip": "10.10.1.5",
                "os": "Ubuntu Linux 22.04",
                "risk_score": Decimal("62.50"),
                "risk_level": Asset.RiskLevel.MEDIUM,
                "owner_name": "WebOps Team",
                "status": Asset.Status.MONITORING,
                "open_ports": 5,
            },
            {
                "name": "db-01.internal",
                "target": "db-core.local",
                "hostname": "db-01.internal",
                "ip": "172.16.10.25",
                "os": "Debian GNU/Linux 12",
                "risk_score": Decimal("81.20"),
                "risk_level": Asset.RiskLevel.HIGH,
                "owner_name": "Data Platform",
                "status": Asset.Status.ACTIVE,
                "open_ports": 3,
            },
            {
                "name": "fileserver-01.internal",
                "target": "fileserver.local",
                "hostname": "fileserver-01.internal",
                "ip": "172.16.11.30",
                "os": "Windows Server 2019",
                "risk_score": Decimal("72.40"),
                "risk_level": Asset.RiskLevel.MEDIUM,
                "owner_name": "IT Operations",
                "status": Asset.Status.ACTIVE,
                "open_ports": 4,
            },
            {
                "name": "gateway-01.internal",
                "target": "app-gateway.local",
                "hostname": "gateway-01.internal",
                "ip": "10.10.5.20",
                "os": "Alpine Linux",
                "risk_score": Decimal("88.10"),
                "risk_level": Asset.RiskLevel.HIGH,
                "owner_name": "Network Security",
                "status": Asset.Status.MONITORING,
                "open_ports": 2,
            },
            {
                "name": "monitor-01.internal",
                "target": "monitoring.local",
                "hostname": "monitor-01.internal",
                "ip": "10.10.20.9",
                "os": "Ubuntu Linux 20.04",
                "risk_score": Decimal("41.80"),
                "risk_level": Asset.RiskLevel.LOW,
                "owner_name": "Observability Team",
                "status": Asset.Status.MONITORING,
                "open_ports": 3,
            },
            {
                "name": "backup-01.internal",
                "target": "192.168.10.0/24",
                "hostname": "backup-01.internal",
                "ip": "192.168.10.42",
                "os": "Rocky Linux 9",
                "risk_score": Decimal("56.70"),
                "risk_level": Asset.RiskLevel.MEDIUM,
                "owner_name": "Backup Team",
                "status": Asset.Status.ACTIVE,
                "open_ports": 2,
            },
        ]

        assets: dict[str, Asset] = {}
        for spec in asset_specs:
            canonical_identifier = f"seed-asset-{spec['name']}"
            target = targets[spec["target"]]
            asset = self._upsert(
                "assets",
                Asset,
                {"canonical_identifier": canonical_identifier},
                {
                    "name": spec["name"],
                    "target": target,
                    "hostname": spec["hostname"],
                    "ip_address": spec["ip"],
                    "operating_system": spec["os"],
                    "risk_score": spec["risk_score"],
                    "risk_level": spec["risk_level"],
                    "owner_name": spec["owner_name"],
                    "notes": f"Seeded demo asset for {spec['owner_name']}.",
                    "last_seen_at": now - timezone.timedelta(minutes=12),
                    "last_scanned_at": now - timezone.timedelta(hours=2),
                    "status": spec["status"],
                    "current_open_ports_count": spec["open_ports"],
                },
            )
            assets[spec["name"]] = asset
        return assets

    @transaction.atomic
    def seed_asset_snapshots(self, assets: dict[str, Asset], results: dict[str, ScanResult], *, now):
        snapshot_specs = [
            ("web-01-a", "web-01.internal", "DEMO-EXE-1001", "Ubuntu Linux 22.04", [22, 80, 443, 3306, 8080]),
            ("web-01-b", "web-01.internal", "DEMO-EXE-1002", "Ubuntu Linux 22.04", [22, 80, 443, 8080, 8443]),
            ("db-01-a", "db-01.internal", "DEMO-EXE-1004", "Debian GNU/Linux 12", [3306, 5432, 6379]),
            ("db-01-b", "db-01.internal", "DEMO-EXE-1005", "Debian GNU/Linux 12", [5432, 6379]),
            ("fileserver-01", "fileserver-01.internal", "DEMO-EXE-1001", "Windows Server 2019", [445, 139, 3389, 5985]),
            ("gateway-01", "gateway-01.internal", "DEMO-EXE-1004", "Alpine Linux", [443, 8443]),
            ("monitor-01", "monitor-01.internal", "DEMO-EXE-1002", "Ubuntu Linux 20.04", [22, 9090, 9100]),
            ("backup-01", "backup-01.internal", "DEMO-EXE-1005", "Rocky Linux 9", [22, 873]),
        ]

        snapshots: dict[str, AssetSnapshot] = {}
        for code, asset_name, execution_id, os_name, open_ports in snapshot_specs:
            asset = assets[asset_name]
            result = results[execution_id]
            snapshot = self._upsert(
                "asset_snapshots",
                AssetSnapshot,
                {"asset": asset, "source_result": result},
                {
                    "hostname": asset.hostname,
                    "ip_address": asset.ip_address,
                    "operating_system": os_name,
                    "open_ports_json": open_ports,
                    "services_json": [{"port": p, "service": "unknown"} for p in open_ports],
                    "raw_summary_json": {"seed_ref": f"asset_snapshot:{code}", "open_ports_count": len(open_ports)},
                    "created_at": now - timezone.timedelta(minutes=30),
                },
            )
            snapshots[code] = snapshot
        return snapshots

    @transaction.atomic
    def seed_asset_change_logs(self, assets: dict[str, Asset], snapshots: dict[str, AssetSnapshot], *, now):
        changes = [
            {
                "asset": "web-01.internal",
                "change_type": AssetChangeLog.ChangeType.PORTS_ADDED,
                "summary": "New port opened: 8443/tcp detected on web-01.internal.",
                "previous": "web-01-a",
                "current": "web-01-b",
                "diff": {"added_ports": [8443], "removed_ports": []},
            },
            {
                "asset": "db-01.internal",
                "change_type": AssetChangeLog.ChangeType.SERVICE_CHANGED,
                "summary": "Database service version changed on db-01.internal (MySQL hidden, PostgreSQL retained).",
                "previous": "db-01-a",
                "current": "db-01-b",
                "diff": {"service_changes": [{"port": 3306, "change": "removed"}, {"port": 5432, "change": "updated"}]},
            },
            {
                "asset": "gateway-01.internal",
                "change_type": AssetChangeLog.ChangeType.OS_CHANGED,
                "summary": "OS fingerprint changed on gateway-01.internal after patch cycle.",
                "previous": "gateway-01",
                "current": "gateway-01",
                "diff": {"from": "Alpine Linux 3.18", "to": "Alpine Linux 3.19"},
            },
            {
                "asset": "monitor-01.internal",
                "change_type": AssetChangeLog.ChangeType.PORTS_REMOVED,
                "summary": "Port 3000/tcp service removed from monitor-01.internal.",
                "previous": "monitor-01",
                "current": "monitor-01",
                "diff": {"removed_ports": [3000]},
            },
        ]

        for item in changes:
            asset = assets[item["asset"]]
            self._upsert(
                "asset_change_logs",
                AssetChangeLog,
                {"asset": asset, "change_type": item["change_type"], "summary": item["summary"]},
                {
                    "previous_snapshot": snapshots[item["previous"]],
                    "current_snapshot": snapshots[item["current"]],
                    "diff_json": item["diff"],
                    "created_at": now - timezone.timedelta(minutes=10),
                },
            )

    @transaction.atomic
    def seed_reports(
        self,
        users: dict[str, User],
        results: dict[str, ScanResult],
        executions: dict[str, ScanExecution],
        assets: dict[str, Asset],
        *,
        now,
    ):
        template_specs = [
            ("executive-summary-template", "Executive Summary Template", GeneratedReport.ReportType.EXECUTIVE_SUMMARY),
            ("technical-report-template", "Technical Report Template", GeneratedReport.ReportType.TECHNICAL_REPORT),
            ("comparison-report-template", "Comparison Report Template", GeneratedReport.ReportType.COMPARISON_REPORT),
            ("per-host-template", "Per Host Template", GeneratedReport.ReportType.PER_HOST_REPORT),
        ]

        templates: dict[str, ReportTemplate] = {}
        for slug, name, report_type in template_specs:
            template = self._upsert(
                "report_templates",
                ReportTemplate,
                {"slug": slug},
                {
                    "name": name,
                    "description": f"Seeded template for {report_type}.",
                    "report_type": report_type,
                    "is_active": True,
                    "is_system": True,
                },
            )
            templates[report_type] = template

        report_specs = [
            {
                "title": "Executive Summary — Internal API Baseline",
                "report_type": GeneratedReport.ReportType.EXECUTIVE_SUMMARY,
                "format": GeneratedReport.Format.HTML,
                "status": GeneratedReport.Status.GENERATED,
                "summary": "Executive overview of baseline findings for internal API and gateway assets.",
                "source_result": results["DEMO-EXE-1001"],
                "source_execution": executions["DEMO-EXE-1001"],
                "generated_by": users["analyst1"],
                "asset": assets["web-01.internal"],
            },
            {
                "title": "Technical Report — Service Detection Pass",
                "report_type": GeneratedReport.ReportType.TECHNICAL_REPORT,
                "format": GeneratedReport.Format.PDF,
                "status": GeneratedReport.Status.GENERATED,
                "summary": "Detailed technical findings from internal web audit scan execution.",
                "source_result": results["DEMO-EXE-1002"],
                "source_execution": executions["DEMO-EXE-1002"],
                "generated_by": users["analyst2"],
                "asset": assets["monitor-01.internal"],
            },
            {
                "title": "Comparison Report — API Baseline Drift",
                "report_type": GeneratedReport.ReportType.COMPARISON_REPORT,
                "format": GeneratedReport.Format.HTML,
                "status": GeneratedReport.Status.GENERATED,
                "summary": "Comparison of baseline versus current API surface to detect drift.",
                "source_result": None,
                "source_execution": None,
                "comparison_left_result": results["DEMO-EXE-1001"],
                "comparison_right_result": results["DEMO-EXE-1002"],
                "generated_by": users["securityadmin"],
                "asset": assets["web-01.internal"],
            },
            {
                "title": "Per Host Report — DB Segment Validation",
                "report_type": GeneratedReport.ReportType.PER_HOST_REPORT,
                "format": GeneratedReport.Format.JSON,
                "status": GeneratedReport.Status.GENERATED,
                "summary": "Host-level database segment validation report.",
                "source_result": results["DEMO-EXE-1004"],
                "source_execution": executions["DEMO-EXE-1004"],
                "generated_by": users["operator1"],
                "asset": assets["db-01.internal"],
            },
        ]

        reports: dict[str, GeneratedReport] = {}
        for spec in report_specs:
            report = self._upsert(
                "reports",
                GeneratedReport,
                {"title": spec["title"]},
                {
                    "report_type": spec["report_type"],
                    "report_template": templates[spec["report_type"]],
                    "source_result": spec.get("source_result"),
                    "source_execution": spec.get("source_execution"),
                    "comparison_left_result": spec.get("comparison_left_result"),
                    "comparison_right_result": spec.get("comparison_right_result"),
                    "asset": spec["asset"],
                    "generated_by": spec["generated_by"],
                    "format": spec["format"],
                    "status": spec["status"],
                    "summary": spec["summary"],
                    "report_payload_json": {
                        "seed_ref": f"report:{spec['title']}",
                        "generated_at": now.isoformat(),
                        "type": spec["report_type"],
                    },
                    "rendered_html": f"<h1>{spec['title']}</h1><p>{spec['summary']}</p>",
                    "generated_file_path": f"/tmp/scanops/reports/{spec['title'].lower().replace(' ', '-')}.out",
                },
            )
            reports[spec["title"]] = report
        return reports

    @transaction.atomic
    def seed_schedules(self, users: dict[str, User], targets: dict[str, Target], profiles: dict[str, ScanProfile], *, now):
        schedule_specs = [
            {
                "name": "Daily Internal Audit",
                "target": "internal-api.local",
                "profile": "Internal Web Audit",
                "schedule_type": ScanSchedule.ScheduleType.DAILY,
                "recurrence_rule": "",
                "start_at": now - timezone.timedelta(days=1, hours=1),
                "notification_enabled": True,
                "created_by": users["securityadmin"],
            },
            {
                "name": "Weekly Web Server Review",
                "target": "10.10.1.10",
                "profile": "Top 100 Ports",
                "schedule_type": ScanSchedule.ScheduleType.WEEKLY,
                "recurrence_rule": "",
                "start_at": now - timezone.timedelta(days=7),
                "notification_enabled": True,
                "created_by": users["analyst1"],
            },
            {
                "name": "One-time Database Validation",
                "target": "db-core.local",
                "profile": "Database Port Review",
                "schedule_type": ScanSchedule.ScheduleType.ONE_TIME,
                "recurrence_rule": "",
                "start_at": now + timezone.timedelta(hours=6),
                "notification_enabled": True,
                "created_by": users["operator1"],
            },
            {
                "name": "Monthly Infrastructure Sweep",
                "target": "192.168.10.0/24",
                "profile": "Host Discovery",
                "schedule_type": ScanSchedule.ScheduleType.MONTHLY,
                "recurrence_rule": "",
                "start_at": now - timezone.timedelta(days=30),
                "notification_enabled": False,
                "created_by": users["superadmin"],
            },
        ]

        schedules: dict[str, ScanSchedule] = {}
        for spec in schedule_specs:
            profile = profiles[spec["profile"]]
            schedule = self._upsert(
                "schedules",
                ScanSchedule,
                {"name": spec["name"]},
                {
                    "target": targets[spec["target"]],
                    "profile": profile,
                    "scan_type": profile.scan_type,
                    "port_input": profile.port_scope,
                    "enable_host_discovery": profile.enable_host_discovery,
                    "enable_service_detection": profile.enable_service_detection,
                    "enable_version_detection": profile.enable_version_detection,
                    "enable_os_detection": profile.enable_os_detection,
                    "enable_traceroute": profile.enable_traceroute,
                    "enable_dns_resolution": profile.enable_dns_resolution,
                    "timing_profile": profile.timing_profile,
                    "schedule_type": spec["schedule_type"],
                    "recurrence_rule": spec["recurrence_rule"],
                    "start_at": spec["start_at"],
                    "end_at": None,
                    "is_enabled": True,
                    "notification_enabled": spec["notification_enabled"],
                    "created_by": spec["created_by"],
                },
            )
            apply_next_run(schedule)
            schedules[spec["name"]] = schedule
        return schedules

    @transaction.atomic
    def seed_schedule_run_logs(
        self,
        schedules: dict[str, ScanSchedule],
        executions: dict[str, ScanExecution],
        reports: dict[str, GeneratedReport],
        *,
        now,
    ):
        log_specs = [
            {
                "schedule": "Daily Internal Audit",
                "message": "Seeded run: execution queued as DEMO-EXE-1001.",
                "status": ScheduleRunLog.Status.COMPLETED,
                "execution": "DEMO-EXE-1001",
                "report": "Executive Summary — Internal API Baseline",
                "run_delta": timezone.timedelta(hours=4),
            },
            {
                "schedule": "Weekly Web Server Review",
                "message": "Seeded run: execution queued as DEMO-EXE-1002.",
                "status": ScheduleRunLog.Status.TRIGGERED,
                "execution": "DEMO-EXE-1002",
                "report": None,
                "run_delta": timezone.timedelta(hours=2, minutes=10),
            },
            {
                "schedule": "One-time Database Validation",
                "message": "Seeded run: awaiting maintenance window.",
                "status": ScheduleRunLog.Status.PENDING,
                "execution": None,
                "report": None,
                "run_delta": timezone.timedelta(minutes=30),
            },
            {
                "schedule": "Monthly Infrastructure Sweep",
                "message": "Seeded run: schedule skipped due to maintenance freeze.",
                "status": ScheduleRunLog.Status.SKIPPED,
                "execution": None,
                "report": None,
                "run_delta": timezone.timedelta(days=1, hours=3),
            },
            {
                "schedule": "Weekly Web Server Review",
                "message": "Seeded run: execution failed on worker-bravo.",
                "status": ScheduleRunLog.Status.FAILED,
                "execution": "DEMO-EXE-1004",
                "report": "Technical Report — Service Detection Pass",
                "run_delta": timezone.timedelta(days=2, hours=1),
            },
        ]

        for spec in log_specs:
            schedule = schedules[spec["schedule"]]
            execution = executions.get(spec["execution"]) if spec["execution"] else None
            report = reports.get(spec["report"]) if spec["report"] else None
            run_at = now - spec["run_delta"]

            self._upsert(
                "schedule_run_logs",
                ScheduleRunLog,
                {"schedule": schedule, "message": spec["message"]},
                {
                    "execution": execution,
                    "run_at": run_at,
                    "status": spec["status"],
                    "generated_report": report,
                },
            )

    @transaction.atomic
    def seed_notifications(
        self,
        users: dict[str, User],
        executions: dict[str, ScanExecution],
        results: dict[str, ScanResult],
        schedules: dict[str, ScanSchedule],
        assets: dict[str, Asset],
        reports: dict[str, GeneratedReport],
        *,
        now,
    ):
        specs = [
            {
                "recipient": "analyst1",
                "title": "Scan completed: DEMO-EXE-1001",
                "message": "Execution DEMO-EXE-1001 completed with 5 open ports detected.",
                "notification_type": Notification.NotificationType.SCAN_COMPLETED,
                "severity": Notification.Severity.SUCCESS,
                "is_read": False,
                "execution": "DEMO-EXE-1001",
                "result": "DEMO-EXE-1001",
                "schedule": "Daily Internal Audit",
                "asset": "web-01.internal",
                "action_url": "/scans/results/",
            },
            {
                "recipient": "securityadmin",
                "title": "Scan failed: DEMO-EXE-1004",
                "message": "Execution DEMO-EXE-1004 failed due to restricted target policy.",
                "notification_type": Notification.NotificationType.SCAN_FAILED,
                "severity": Notification.Severity.ERROR,
                "is_read": False,
                "execution": "DEMO-EXE-1004",
                "result": "DEMO-EXE-1004",
                "schedule": "Weekly Web Server Review",
                "asset": "gateway-01.internal",
                "action_url": "/scans/running/",
            },
            {
                "recipient": "analyst2",
                "title": "Report generated: Technical Report",
                "message": "Technical report for service detection pass is ready.",
                "notification_type": Notification.NotificationType.REPORT_GENERATED,
                "severity": Notification.Severity.INFO,
                "is_read": True,
                "execution": "DEMO-EXE-1002",
                "result": "DEMO-EXE-1002",
                "schedule": None,
                "asset": "monitor-01.internal",
                "action_url": "/reports/",
            },
            {
                "recipient": "operator1",
                "title": "Schedule triggered: Weekly Web Server Review",
                "message": "Scheduled scan workflow has been triggered.",
                "notification_type": Notification.NotificationType.SCHEDULE_TRIGGERED,
                "severity": Notification.Severity.INFO,
                "is_read": False,
                "execution": "DEMO-EXE-1002",
                "result": None,
                "schedule": "Weekly Web Server Review",
                "asset": None,
                "action_url": "/schedules/",
            },
            {
                "recipient": "operator2",
                "title": "Asset changed: web-01.internal",
                "message": "New exposed port detected on web-01.internal.",
                "notification_type": Notification.NotificationType.ASSET_CHANGED,
                "severity": Notification.Severity.WARNING,
                "is_read": False,
                "execution": None,
                "result": None,
                "schedule": None,
                "asset": "web-01.internal",
                "action_url": "/assets/changes/",
            },
            {
                "recipient": "viewer1",
                "title": "System alert: Queue backlog warning",
                "message": "Queue backlog exceeded warning threshold on worker-bravo.",
                "notification_type": Notification.NotificationType.SYSTEM_ALERT,
                "severity": Notification.Severity.WARNING,
                "is_read": False,
                "execution": None,
                "result": None,
                "schedule": None,
                "asset": None,
                "action_url": "/ops/health/system/",
            },
        ]

        for spec in specs:
            notification = self._upsert(
                "notifications",
                Notification,
                {
                    "recipient": users[spec["recipient"]],
                    "title": spec["title"],
                    "notification_type": spec["notification_type"],
                },
                {
                    "message": spec["message"],
                    "severity": spec["severity"],
                    "is_read": spec["is_read"],
                    "related_execution": executions.get(spec["execution"]) if spec["execution"] else None,
                    "related_result": results.get(spec["result"]) if spec["result"] else None,
                    "related_schedule": schedules.get(spec["schedule"]) if spec["schedule"] else None,
                    "related_asset": assets.get(spec["asset"]) if spec["asset"] else None,
                    "action_url": spec["action_url"],
                    "metadata_json": {"seed_ref": f"notification:{spec['title']}"},
                    "read_at": now - timezone.timedelta(minutes=5) if spec["is_read"] else None,
                },
            )

            # Keep object touched for realism
            if notification.is_read and notification.read_at is None:
                notification.read_at = now - timezone.timedelta(minutes=5)
                notification.save(update_fields=["read_at"])

    @transaction.atomic
    def seed_app_settings(self, users: dict[str, User]):
        actor = users["superadmin"]
        for category in (
            AppSetting.Category.GENERAL,
            AppSetting.Category.SCAN_POLICY,
            AppSetting.Category.ALLOWED_TARGETS,
            AppSetting.Category.NOTIFICATIONS,
            AppSetting.Category.EXPORTS,
            AppSetting.Category.UI,
        ):
            app_settings_service.reset_category_to_defaults(category, user=actor)
            self._track("app_settings_categories", False)

        app_settings_service.update_category_values(
            AppSetting.Category.GENERAL,
            {
                "app_brand_name": "ScanOps",
                "default_landing_page": "dashboard",
                "time_zone": "UTC",
                "language": "en-us",
                "scan_retention_days": 120,
                "audit_retention_days": 365,
                "compact_sidebar": False,
                "show_help_tips": True,
            },
            user=actor,
        )
        app_settings_service.update_category_values(
            AppSetting.Category.SCAN_POLICY,
            {
                "allowed_scan_types": ["host_discovery", "quick_tcp", "top_100", "top_1000", "service_detection", "safe_basic"],
                "blocked_scan_types": [],
                "max_ports_per_scan": 2048,
                "scan_timeout_seconds": 1200,
                "max_concurrency": 25,
                "safe_default_options": True,
                "aggressive_requires_approval": True,
            },
            user=actor,
        )
        app_settings_service.update_category_values(
            AppSetting.Category.ALLOWED_TARGETS,
            {
                "whitelist_ranges": ["10.0.0.0/8", "172.16.0.0/12", "192.168.0.0/16"],
                "blocked_ranges": ["0.0.0.0/0"],
                "restrict_public_targets": True,
                "strict_target_validation": True,
                "approval_required_new_targets": True,
            },
            user=actor,
        )
        app_settings_service.update_category_values(
            AppSetting.Category.NOTIFICATIONS,
            {
                "in_app_enabled": True,
                "email_enabled": True,
                "severity_preferences": ["warning", "error"],
                "daily_digest_enabled": True,
                "digest_hour_utc": 7,
            },
            user=actor,
        )
        app_settings_service.update_category_values(
            AppSetting.Category.EXPORTS,
            {
                "default_report_format": "html",
                "branded_template": "enterprise_standard",
                "pdf_header_text": "ScanOps Internal Security Report",
                "pdf_footer_text": "Authorized Internal Use Only",
                "export_retention_days": 45,
                "file_naming_pattern": "{type}-{target}-{date}",
            },
            user=actor,
        )
        app_settings_service.update_category_values(
            AppSetting.Category.UI,
            {
                "default_theme": "dark",
                "compact_mode": False,
                "data_density": "comfortable",
                "table_page_size": 20,
                "dashboard_card_style": "standard",
            },
            user=actor,
        )
        self._track("app_settings_categories", False)

    @transaction.atomic
    def seed_worker_status(self, *, now):
        specs = [
            {
                "worker_name": "worker-alpha",
                "status": WorkerStatusSnapshot.Status.ONLINE,
                "active_jobs_count": 3,
                "queued_jobs_count": 2,
                "failed_jobs_count": 0,
                "heartbeat_delta": timezone.timedelta(seconds=35),
            },
            {
                "worker_name": "worker-bravo",
                "status": WorkerStatusSnapshot.Status.DEGRADED,
                "active_jobs_count": 1,
                "queued_jobs_count": 6,
                "failed_jobs_count": 2,
                "heartbeat_delta": timezone.timedelta(minutes=8),
            },
            {
                "worker_name": "worker-charlie",
                "status": WorkerStatusSnapshot.Status.OFFLINE,
                "active_jobs_count": 0,
                "queued_jobs_count": 0,
                "failed_jobs_count": 4,
                "heartbeat_delta": timezone.timedelta(minutes=48),
            },
        ]

        for spec in specs:
            latest = (
                WorkerStatusSnapshot.objects.filter(worker_name=spec["worker_name"])
                .order_by("-created_at")
                .first()
            )
            defaults = {
                "status": spec["status"],
                "active_jobs_count": spec["active_jobs_count"],
                "queued_jobs_count": spec["queued_jobs_count"],
                "failed_jobs_count": spec["failed_jobs_count"],
                "heartbeat_at": now - spec["heartbeat_delta"],
                "metadata_json": {"seed_ref": f"worker:{spec['worker_name']}"},
            }
            if latest:
                for field, value in defaults.items():
                    setattr(latest, field, value)
                latest.save(update_fields=list(defaults.keys()) + ["created_at"])
                self._track("worker_status_snapshots", False)
            else:
                WorkerStatusSnapshot.objects.create(worker_name=spec["worker_name"], **defaults)
                self._track("worker_status_snapshots", True)

    @transaction.atomic
    def seed_system_health(self, *, now):
        specs = [
            (
                SystemHealthSnapshot.ServiceName.DJANGO_APP,
                SystemHealthSnapshot.Status.HEALTHY,
                "Demo seed: Django app process healthy.",
                {"response_ms": 22},
            ),
            (
                SystemHealthSnapshot.ServiceName.DATABASE,
                SystemHealthSnapshot.Status.HEALTHY,
                "Demo seed: Database connectivity healthy.",
                {"latency_ms": 12},
            ),
            (
                SystemHealthSnapshot.ServiceName.NMAP_BINARY,
                SystemHealthSnapshot.Status.HEALTHY,
                "Demo seed: Nmap binary available in PATH.",
                {"binary": "nmap"},
            ),
            (
                SystemHealthSnapshot.ServiceName.QUEUE_SERVICE,
                SystemHealthSnapshot.Status.WARNING,
                "Demo seed: Queue backlog elevated on one worker.",
                {"queued_jobs": 8},
            ),
            (
                SystemHealthSnapshot.ServiceName.SCHEDULER,
                SystemHealthSnapshot.Status.HEALTHY,
                "Demo seed: Scheduler active with no overdue critical jobs.",
                {"enabled_schedules": 4},
            ),
            (
                SystemHealthSnapshot.ServiceName.STORAGE,
                SystemHealthSnapshot.Status.HEALTHY,
                "Demo seed: Storage paths writable.",
                {"media_writable": True, "static_writable": True},
            ),
        ]

        for service_name, status, summary, metadata in specs:
            snapshot = (
                SystemHealthSnapshot.objects.filter(
                    service_name=service_name,
                    summary__startswith="Demo seed:",
                )
                .order_by("-checked_at", "-id")
                .first()
            )
            if snapshot:
                snapshot.status = status
                snapshot.summary = summary
                snapshot.metadata_json = metadata
                snapshot.checked_at = now
                snapshot.save(update_fields=["status", "summary", "metadata_json", "checked_at"])
                self._track("system_health_snapshots", False)
            else:
                SystemHealthSnapshot.objects.create(
                    service_name=service_name,
                    status=status,
                    summary=summary,
                    metadata_json=metadata,
                    checked_at=now,
                )
                self._track("system_health_snapshots", True)

    def print_summary(self):
        self.stdout.write(self.style.SUCCESS("Demo seeding complete."))
        for key in sorted(self.summary.keys()):
            created = self.summary[key]["created"]
            updated = self.summary[key]["updated"]
            self.stdout.write(f" - {key}: created={created}, updated={updated}")
        self.stdout.write("Credentials file: backup/user.txt")

    @staticmethod
    def _split_name(full_name: str) -> tuple[str, str]:
        parts = [part for part in (full_name or "").split(" ") if part]
        if not parts:
            return "", ""
        if len(parts) == 1:
            return parts[0], ""
        return parts[0], " ".join(parts[1:])

    @staticmethod
    def _workspace_for_role(role_slug: str) -> str:
        mapping = {
            "super_admin": "Global Security Operations",
            "security_admin": "Security Governance",
            "analyst": "Threat Analysis",
            "operator": "Network Operations",
            "viewer": "Audit & Oversight",
        }
        return mapping.get(role_slug, "General")
