#!/usr/bin/env bash
# Run on the Akpan laptop to tar the IS data and upload to GitHub Release, then trigger GH Actions.
set -e

REPO="Akpan-byte/polymarket_strategy_stack"
RELEASE_TAG="data-v1"
DATA_DIR="$HOME/polybacktest_btc5m/is_full"
TARBALL="/tmp/is_data.tar.gz"

echo "Tarring IS data from $DATA_DIR ..."
rm -f "$TARBALL"
tar czf "$TARBALL" -C "$DATA_DIR" .
echo "Tarball size: $(du -h "$TARBALL" | cut -f1)"

echo "Creating release $RELEASE_TAG (if missing) and uploading asset..."
gh release create "$RELEASE_TAG" "$TARBALL" \
  --repo "$REPO" \
  --title "IS Data $RELEASE_TAG" \
  --notes "In-sample BTC 5m Polymarket data" \
  --clobber

echo "Triggering GH Actions workflow..."
gh workflow run backtest.yml \
  --repo "$REPO" \
  --ref main \
  -f data_release="$RELEASE_TAG" \
  -f max_sweeps=13

echo "Done. Monitor at: https://github.com/$REPO/actions"
