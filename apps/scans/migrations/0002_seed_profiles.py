from django.db import migrations


def seed_scan_profiles(apps, schema_editor):
    ScanProfile = apps.get_model("scans", "ScanProfile")
    defaults = [
        {
            "name": "Safe Basic",
            "description": "Default low-risk baseline for authorized assets.",
            "scan_type": "safe_basic",
            "port_scope": "top_100",
            "enable_host_discovery": True,
            "enable_service_detection": True,
            "enable_version_detection": False,
            "enable_os_detection": False,
            "enable_traceroute": False,
            "enable_dns_resolution": True,
            "timing_profile": "normal",
            "is_system": True,
            "is_active": True,
        },
        {
            "name": "Service Detection",
            "description": "Host and service validation with version detection.",
            "scan_type": "service_detection",
            "port_scope": "top_1000",
            "enable_host_discovery": True,
            "enable_service_detection": True,
            "enable_version_detection": True,
            "enable_os_detection": False,
            "enable_traceroute": False,
            "enable_dns_resolution": True,
            "timing_profile": "balanced",
            "is_system": True,
            "is_active": True,
        },
    ]

    for item in defaults:
        ScanProfile.objects.update_or_create(
            name=item["name"],
            defaults=item,
        )


def remove_seed_scan_profiles(apps, schema_editor):
    ScanProfile = apps.get_model("scans", "ScanProfile")
    ScanProfile.objects.filter(name__in=["Safe Basic", "Service Detection"], is_system=True).delete()


class Migration(migrations.Migration):
    dependencies = [
        ("scans", "0001_initial"),
    ]

    operations = [
        migrations.RunPython(seed_scan_profiles, remove_seed_scan_profiles),
    ]
