#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PYTHON_BIN="${PROJECT_ROOT}/.venv/bin/python"
SYSTEMD_USER_DIR="${XDG_CONFIG_HOME:-$HOME/.config}/systemd/user"
SERVICE_TEMPLATE="${PROJECT_ROOT}/deploy/systemd/incidentmatrix-db-backup.service.template"
TIMER_TEMPLATE="${PROJECT_ROOT}/deploy/systemd/incidentmatrix-db-backup.timer"
SERVICE_DEST="${SYSTEMD_USER_DIR}/incidentmatrix-db-backup.service"
TIMER_DEST="${SYSTEMD_USER_DIR}/incidentmatrix-db-backup.timer"
DRY_RUN=0

if [[ "${1:-}" == "--dry-run" ]]; then
  DRY_RUN=1
fi

if [[ ! -x "${PYTHON_BIN}" ]]; then
  echo "Expected Python interpreter not found: ${PYTHON_BIN}" >&2
  exit 1
fi

render_service() {
  sed \
    -e "s|__PROJECT_ROOT__|${PROJECT_ROOT}|g" \
    -e "s|__PYTHON_BIN__|${PYTHON_BIN}|g" \
    "${SERVICE_TEMPLATE}"
}

if [[ "${DRY_RUN}" -eq 1 ]]; then
  echo "--- incidentmatrix-db-backup.service ---"
  render_service
  echo
  echo "--- incidentmatrix-db-backup.timer ---"
  cat "${TIMER_TEMPLATE}"
  exit 0
fi

mkdir -p "${SYSTEMD_USER_DIR}"
render_service > "${SERVICE_DEST}"
cp "${TIMER_TEMPLATE}" "${TIMER_DEST}"

systemctl --user daemon-reload
systemctl --user enable --now incidentmatrix-db-backup.timer
systemctl --user status incidentmatrix-db-backup.timer --no-pager || true
