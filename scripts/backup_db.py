#!/usr/bin/env python3
from __future__ import annotations

import argparse
import datetime as dt
import os
import re
import shutil
import sqlite3
import subprocess
import sys
import tempfile
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_BACKUP_DIR = PROJECT_ROOT / "dbbackup"
MONTH_ABBR = ("jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec")


def bootstrap_django():
    sys.path.insert(0, str(PROJECT_ROOT))
    from core.env import configure_environment

    configure_environment()

    import django

    django.setup()

    from django.conf import settings

    return settings


def slugify(value: str) -> str:
    lowered = re.sub(r"[^a-zA-Z0-9]+", "_", value.strip().lower()).strip("_")
    return lowered or "incidentmatrix"


def detect_database_label(engine: str, database_name: str) -> str:
    if "sqlite" in engine:
        stem = Path(database_name or "").stem
        if stem in {"", "db"}:
            label = slugify(PROJECT_ROOT.name)
        else:
            label = slugify(stem)
    elif database_name:
        label = slugify(Path(str(database_name)).name)
    else:
        label = slugify(PROJECT_ROOT.name)
    if label.startswith("db_") and len(label) > 3:
        return label[3:]
    return label


def build_output_path(backup_dir: Path, database_label: str, extension: str) -> Path:
    now = dt.datetime.now()
    filename = f"db_{database_label}_{now.year}_{MONTH_ABBR[now.month - 1]}_{now.day:02d}{extension}"
    target = backup_dir / filename
    if not target.exists():
        return target
    return backup_dir / f"db_{database_label}_{now.year}_{MONTH_ABBR[now.month - 1]}_{now.day:02d}_{now.strftime('%H%M%S')}{extension}"


def ensure_backup_dir(path: Path) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    return path


def run_command(command: list[str], env: dict[str, str], output_path: Path) -> None:
    with output_path.open("wb") as handle:
        subprocess.run(command, stdout=handle, stderr=subprocess.PIPE, check=True, env=env, cwd=PROJECT_ROOT)


def dump_postgresql(database: dict[str, str], output_path: Path) -> None:
    pg_dump = shutil.which("pg_dump")
    if not pg_dump:
        raise RuntimeError("pg_dump is required for PostgreSQL backups but was not found in PATH.")

    env = os.environ.copy()
    if database.get("PASSWORD"):
        env["PGPASSWORD"] = str(database["PASSWORD"])

    command = [pg_dump, "--format=plain", "--no-owner", "--no-privileges"]
    if database.get("HOST"):
        command.extend(["--host", str(database["HOST"])])
    if database.get("PORT"):
        command.extend(["--port", str(database["PORT"])])
    if database.get("USER"):
        command.extend(["--username", str(database["USER"])])
    command.append(str(database["NAME"]))

    run_command(command, env, output_path)


def dump_mysql(database: dict[str, str], output_path: Path) -> None:
    mysqldump = shutil.which("mysqldump") or shutil.which("mariadb-dump")
    if not mysqldump:
        raise RuntimeError("mysqldump or mariadb-dump is required for MySQL backups but was not found in PATH.")

    env = os.environ.copy()
    if database.get("PASSWORD"):
        env["MYSQL_PWD"] = str(database["PASSWORD"])

    command = [mysqldump, "--single-transaction", "--quick", "--routines", "--triggers", "--events", "--skip-lock-tables"]
    if database.get("HOST"):
        command.extend(["--host", str(database["HOST"])])
    if database.get("PORT"):
        command.extend(["--port", str(database["PORT"])])
    if database.get("USER"):
        command.extend(["--user", str(database["USER"])])
    command.append(str(database["NAME"]))

    run_command(command, env, output_path)


def dump_sqlite(database_path: str, output_path: Path) -> None:
    source_path = Path(database_path)
    if not source_path.exists():
        raise RuntimeError(f"SQLite database was not found at {source_path}")

    with tempfile.NamedTemporaryFile(prefix="incidentmatrix_sqlite_", suffix=".sqlite3", delete=False) as tmp_file:
        temp_backup_path = Path(tmp_file.name)

    try:
        with sqlite3.connect(f"file:{source_path}?mode=ro", uri=True) as source_conn:
            with sqlite3.connect(temp_backup_path) as backup_conn:
                source_conn.backup(backup_conn)

        with sqlite3.connect(temp_backup_path) as snapshot_conn, output_path.open("w", encoding="utf-8") as handle:
            for statement in snapshot_conn.iterdump():
                handle.write(f"{statement}\n")
    finally:
        temp_backup_path.unlink(missing_ok=True)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Create a database backup for IncidentMatrix.")
    parser.add_argument(
        "--backup-dir",
        default=str(DEFAULT_BACKUP_DIR),
        help="Directory where backup files will be written.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    settings = bootstrap_django()
    database = settings.DATABASES["default"]
    engine = database.get("ENGINE", "")
    database_label = detect_database_label(engine, str(database.get("NAME", "")))
    backup_dir = ensure_backup_dir(Path(args.backup_dir).resolve())
    final_path = build_output_path(backup_dir, database_label, ".sql")

    with tempfile.NamedTemporaryFile(prefix="incidentmatrix_backup_", suffix=".sql", dir=backup_dir, delete=False) as tmp_file:
        temp_output_path = Path(tmp_file.name)

    try:
        if "postgresql" in engine:
            dump_postgresql(database, temp_output_path)
        elif "mysql" in engine:
            dump_mysql(database, temp_output_path)
        elif "sqlite" in engine:
            dump_sqlite(str(database["NAME"]), temp_output_path)
        else:
            raise RuntimeError(f"Unsupported database engine: {engine}")

        temp_output_path.replace(final_path)
        os.chmod(final_path, 0o644)
    except Exception:
        temp_output_path.unlink(missing_ok=True)
        raise

    print(f"Backup completed successfully.")
    print(f"Database engine: {engine}")
    print(f"Backup file: {final_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
