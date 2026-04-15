import os
from pathlib import Path

from dotenv import load_dotenv


PROJECT_ROOT = Path(__file__).resolve().parent.parent
DOTENV_FILE = PROJECT_ROOT / ".env"
DOTENV_LOCAL_FILE = PROJECT_ROOT / ".env.local"
TRUE_VALUES = {"1", "true", "yes", "on"}


def _env_flag(name, default=False):
    value = os.environ.get(name)
    if value is None:
        return default
    return value.strip().lower() in TRUE_VALUES


def configure_environment():
    explicit_environment = (os.environ.get("JTRO_ENVIRONMENT") or "").strip().lower()
    load_dotenv_in_production = _env_flag("JTRO_LOAD_DOTENV_IN_PRODUCTION", default=False)
    should_load_dotenv = explicit_environment != "production" or load_dotenv_in_production
    skip_local_dotenv = _env_flag("JTRO_SKIP_DOTENV_LOCAL", default=False)

    if should_load_dotenv:
        # Prefer developer-local overrides first so the tracked .env can stay sanitized.
        if DOTENV_LOCAL_FILE.exists() and not skip_local_dotenv:
            load_dotenv(DOTENV_LOCAL_FILE)
        if DOTENV_FILE.exists():
            load_dotenv(DOTENV_FILE)

    environment = (os.environ.get("JTRO_ENVIRONMENT") or "dev").strip().lower()
    settings_module = "core.settings.production" if environment == "production" else "core.settings.dev"
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", settings_module)
    return settings_module
