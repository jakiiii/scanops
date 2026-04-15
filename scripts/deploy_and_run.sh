#!/usr/bin/env bash
set -Eeuo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

MANAGE_PY="${PROJECT_ROOT}/manage.py"
VENV_DIR="${PROJECT_ROOT}/.venv"
REQ_FILE="${PROJECT_ROOT}/requirements.txt"
ENV_FILE="${PROJECT_ROOT}/.env"
ENV_EXAMPLE="${PROJECT_ROOT}/.env.example"

MODE="local"
HOST="${SCANOPS_HOST:-0.0.0.0}"
PORT="${SCANOPS_PORT:-8008}"

SKIP_INSTALL=0
SKIP_MIGRATE=0
SKIP_COLLECTSTATIC=0
SKIP_CHECK=0
SEED_DEMO=0
NO_RUN=0
NO_BUILD=0
SHOW_LOGS=0

PYTHON_BIN=""
PIP_BIN=""
COMPOSE_CMD=()

log() {
  printf '[ScanOps] %s\n' "$*"
}

warn() {
  printf '[ScanOps][WARN] %s\n' "$*" >&2
}

die() {
  printf '[ScanOps][ERROR] %s\n' "$*" >&2
  exit 1
}

usage() {
  cat <<EOF
Usage: scripts/deploy_and_run.sh [options]

Modes:
  --mode local|docker     Run locally (Django runserver) or via Docker Compose

Core options:
  --host <host>           Bind host for local runserver (default: ${HOST})
  --port <port>           Bind port / healthcheck port (default: ${PORT})
  --skip-install          Skip pip install -r requirements.txt (local mode)
  --skip-migrate          Skip python manage.py migrate
  --skip-collectstatic    Skip python manage.py collectstatic --noinput
  --skip-check            Skip python manage.py check
  --seed-demo             Run python manage.py seed_demo_environment if command exists
  --no-run                Prepare only; do not start runserver / docker compose up

Docker mode:
  --no-build              Skip docker compose build
  --logs                  Follow docker compose logs after startup

Misc:
  -h, --help              Show this help
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --mode)
      [[ $# -ge 2 ]] || die "--mode requires a value"
      MODE="$2"
      shift 2
      ;;
    --host)
      [[ $# -ge 2 ]] || die "--host requires a value"
      HOST="$2"
      shift 2
      ;;
    --port)
      [[ $# -ge 2 ]] || die "--port requires a value"
      PORT="$2"
      shift 2
      ;;
    --skip-install)
      SKIP_INSTALL=1
      shift
      ;;
    --skip-migrate)
      SKIP_MIGRATE=1
      shift
      ;;
    --skip-collectstatic)
      SKIP_COLLECTSTATIC=1
      shift
      ;;
    --skip-check)
      SKIP_CHECK=1
      shift
      ;;
    --seed-demo)
      SEED_DEMO=1
      shift
      ;;
    --no-run)
      NO_RUN=1
      shift
      ;;
    --no-build)
      NO_BUILD=1
      shift
      ;;
    --logs)
      SHOW_LOGS=1
      shift
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      die "Unknown option: $1"
      ;;
  esac
done

[[ "${MODE}" == "local" || "${MODE}" == "docker" ]] || die "--mode must be 'local' or 'docker'"
[[ -f "${MANAGE_PY}" ]] || die "manage.py not found at ${MANAGE_PY}"
[[ -f "${REQ_FILE}" ]] || die "requirements.txt not found at ${REQ_FILE}"

cd "${PROJECT_ROOT}"

if [[ ! -f "${ENV_FILE}" && -f "${ENV_EXAMPLE}" ]]; then
  cp "${ENV_EXAMPLE}" "${ENV_FILE}"
  log "Created .env from .env.example"
fi

mkdir -p "${PROJECT_ROOT}/app_logs" "${PROJECT_ROOT}/static_root/static" "${PROJECT_ROOT}/media_root/media"

activate_venv_if_present() {
  if [[ -d "${VENV_DIR}" && -f "${VENV_DIR}/bin/activate" ]]; then
    # shellcheck disable=SC1090
    source "${VENV_DIR}/bin/activate"
    log "Activated virtualenv: ${VENV_DIR}"
  else
    warn "Virtualenv not found at ${VENV_DIR}; using system Python"
  fi
}

set_python_tools() {
  if command -v python >/dev/null 2>&1; then
    PYTHON_BIN="$(command -v python)"
  elif command -v python3 >/dev/null 2>&1; then
    PYTHON_BIN="$(command -v python3)"
  else
    die "Python is not installed"
  fi

  if command -v pip >/dev/null 2>&1; then
    PIP_BIN="$(command -v pip)"
  else
    PIP_BIN="${PYTHON_BIN} -m pip"
  fi
}

run_manage() {
  "${PYTHON_BIN}" "${MANAGE_PY}" "$@"
}

prepare_local() {
  activate_venv_if_present
  set_python_tools

  if [[ "${SKIP_INSTALL}" -eq 0 ]]; then
    log "Installing dependencies"
    # shellcheck disable=SC2086
    ${PIP_BIN} install -r "${REQ_FILE}"
  fi

  if [[ "${SKIP_MIGRATE}" -eq 0 ]]; then
    log "Running migrations"
    run_manage migrate --noinput
  fi

  if [[ "${SKIP_COLLECTSTATIC}" -eq 0 ]]; then
    log "Collecting static files"
    run_manage collectstatic --noinput --ignore "admin/js/*"
  fi

  if [[ "${SKIP_CHECK}" -eq 0 ]]; then
    log "Running Django system checks"
    run_manage check
  fi

  if [[ "${SEED_DEMO}" -eq 1 ]]; then
    if run_manage help seed_demo_environment >/dev/null 2>&1; then
      log "Seeding demo environment"
      run_manage seed_demo_environment
    else
      warn "seed_demo_environment command not found; skipping demo seed"
    fi
  fi

  if [[ "${NO_RUN}" -eq 1 ]]; then
    log "Preparation complete (--no-run enabled)"
    return
  fi

  log "Starting ScanOps on http://${HOST}:${PORT}"
  exec "${PYTHON_BIN}" "${MANAGE_PY}" runserver "${HOST}:${PORT}"
}

set_compose_cmd() {
  if docker compose version >/dev/null 2>&1; then
    COMPOSE_CMD=(docker compose)
  elif command -v docker-compose >/dev/null 2>&1; then
    COMPOSE_CMD=(docker-compose)
  else
    die "Docker Compose is required for --mode docker"
  fi
}

wait_for_http() {
  local url="$1"
  local attempts="$2"
  local sleep_for="$3"

  if ! command -v curl >/dev/null 2>&1; then
    warn "curl not available; skipping HTTP verification for ${url}"
    return 0
  fi

  for _ in $(seq 1 "${attempts}"); do
    if curl -fsS "${url}" >/dev/null 2>&1; then
      return 0
    fi
    sleep "${sleep_for}"
  done
  return 1
}

prepare_docker() {
  command -v docker >/dev/null 2>&1 || die "Docker is not installed"
  docker info >/dev/null 2>&1 || die "Docker daemon is not reachable"
  set_compose_cmd

  if [[ "${NO_BUILD}" -eq 0 ]]; then
    log "Building Docker image"
    "${COMPOSE_CMD[@]}" build
  fi

  if [[ "${NO_RUN}" -eq 1 ]]; then
    log "Docker build complete (--no-run enabled)"
    return
  fi

  log "Starting Docker services"
  "${COMPOSE_CMD[@]}" up -d

  local login_url="http://127.0.0.1:${PORT}/login/"
  if wait_for_http "${login_url}" 90 1; then
    log "Application is reachable at ${login_url}"
  else
    "${COMPOSE_CMD[@]}" logs --tail=200 scanops-web || true
    die "App did not become ready on ${login_url}"
  fi

  "${COMPOSE_CMD[@]}" ps

  if [[ "${SHOW_LOGS}" -eq 1 ]]; then
    "${COMPOSE_CMD[@]}" logs -f --tail=200 scanops-web
  fi
}

if [[ "${MODE}" == "local" ]]; then
  prepare_local
else
  prepare_docker
fi
