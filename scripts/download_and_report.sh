#!/usr/bin/env bash
# Download all artifacts from a GitHub Actions run, build the final report,
# and optionally sync results to Google Drive via rclone.
#
# Required environment variables:
#   RUN_ID  - GitHub Actions run id
#   REPO    - owner/repo (e.g. Akpan-byte/polymarket_strategy_stack)
#
# Optional:
#   RCLONE_CONFIG - path to rclone config file; if rclone is installed/configured,
#                   artifacts and report are synced to polybacktest:results/gh_actions/${RUN_ID}/

set -euo pipefail

RUN_ID="${RUN_ID:?RUN_ID env var required}"
REPO="${REPO:?REPO env var required}"
DEST_DIR="/tmp/gh_artifacts_${RUN_ID}"
REPORT="FINAL_REPORT_80D_IS.md"

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${REPO_ROOT}"

echo "[$(date -Iseconds)] Downloading artifacts for run ${RUN_ID} from ${REPO}..."

if ! command -v gh >/dev/null 2>&1; then
    echo "[download_and_report] ERROR: gh CLI not found" >&2
    exit 1
fi
if ! gh auth status >/dev/null 2>&1; then
    echo "[download_and_report] ERROR: gh CLI is not authenticated" >&2
    exit 1
fi

# Clean previous partial download to avoid stale data
rm -rf "${DEST_DIR}"
mkdir -p "${DEST_DIR}"

gh run download "${RUN_ID}" --repo "${REPO}" -D "${DEST_DIR}"
echo "[$(date -Iseconds)] Artifacts saved to ${DEST_DIR}"

echo "[$(date -Iseconds)] Generating final report..."
python3 runners/final_report.py --artifacts "${DEST_DIR}" --out "${REPORT}"
echo "[$(date -Iseconds)] Report saved to ${REPORT}"

if command -v rclone >/dev/null 2>&1; then
    REMOTE="polybacktest:results/gh_actions/${RUN_ID}/"
    echo "[$(date -Iseconds)] rclone available; syncing to ${REMOTE}..."
    if [[ -n "${RCLONE_CONFIG:-}" ]]; then
        export RCLONE_CONFIG="${RCLONE_CONFIG}"
    fi
    rclone sync "${DEST_DIR}/" "${REMOTE}artifacts/" --progress
    rclone copyto "${REPORT}" "${REMOTE}${REPORT}" --progress
    echo "[$(date -Iseconds)] Sync complete."
else
    echo "[$(date -Iseconds)] rclone not installed; skipping Google Drive sync."
fi
