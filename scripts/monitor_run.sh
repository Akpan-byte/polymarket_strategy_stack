#!/usr/bin/env bash
# Poll a GitHub Actions run until it completes.
#
# Required environment variables:
#   RUN_ID  - GitHub Actions run id
#   REPO    - owner/repo (e.g. Akpan-byte/polymarket_strategy_stack)
#
# Optional:
#   INTERVAL - seconds between polls (default: 60)

set -euo pipefail

RUN_ID="${RUN_ID:?RUN_ID env var required}"
REPO="${REPO:?REPO env var required}"
INTERVAL="${INTERVAL:-60}"

echo "[$(date -Iseconds)] Monitoring run ${RUN_ID} in ${REPO} (poll interval ${INTERVAL}s)..."

while true; do
    if ! status_json=$(gh run view "${RUN_ID}" --repo "${REPO}" --json status,conclusion,url 2>/dev/null); then
        echo "[$(date -Iseconds)] failed to fetch run ${RUN_ID}; retrying in ${INTERVAL}s"
        sleep "${INTERVAL}"
        continue
    fi

    status=$(python3 -c "import sys,json; print(json.load(sys.stdin)['status'])") <<<"${status_json}"
    conclusion=$(python3 -c "import sys,json; print(json.load(sys.stdin).get('conclusion',''))") <<<"${status_json}"
    url=$(python3 -c "import sys,json; print(json.load(sys.stdin).get('url',''))") <<<"${status_json}"

    echo "[$(date -Iseconds)] status=${status} conclusion=${conclusion}"

    if [[ "${status}" == "completed" ]]; then
        echo "[$(date -Iseconds)] Run completed (${conclusion}): ${url}"
        if [[ "${conclusion}" == "success" ]]; then
            exit 0
        else
            exit 1
        fi
    fi

    sleep "${INTERVAL}"
done
