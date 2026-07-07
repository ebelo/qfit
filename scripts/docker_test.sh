#!/usr/bin/env bash
# Run qfit tests inside a QGIS Docker container.
#
# Usage:
#   scripts/docker_test.sh [3|4] [pytest args...]
#
# Examples:
#   scripts/docker_test.sh 3                    # run QGIS runtime tests on QGIS 3
#   scripts/docker_test.sh 4                    # run QGIS runtime tests on QGIS 4
#   scripts/docker_test.sh 3 -x -q              # fast fail, quiet
#   scripts/docker_test.sh 4 tests/test_activity_query.py  # specific file
#
# The script mounts the qfit repo at /tests_directory/qfit inside the
# container, uses QGIS's built-in qgis_setup.sh to link the plugin, and
# runs pytest.

set -euo pipefail

QGIS_VERSION="${1:-3}"
shift || true

if [[ "$#" -eq 0 ]]; then
  set -- tests/test_qgis_smoke.py tests/test_qt6_class_enum_probe.py -q --tb=short
fi

case "$QGIS_VERSION" in
  3)
    IMAGE="qgis/qgis:3.44.11"
    CONTAINER_NAME="qfit-test-qgis3"
    ;;
  4)
    IMAGE="qgis/qgis:4.2.0"
    CONTAINER_NAME="qfit-test-qgis4"
    ;;
  *)
    echo "Usage: $0 [3|4] [pytest args...]"
    exit 1
    ;;
esac

REPO_DIR="$(cd "$(dirname "$0")/.." && pwd)"

echo "=== qfit Docker test runner ==="
echo "QGIS image:  $IMAGE"
echo "Repo:        $REPO_DIR"
echo "Pytest args: $*"
echo

# Clean up any previous container with the same name
sudo docker rm -f "$CONTAINER_NAME" 2>/dev/null || true

# Start container with repo mounted as /tests_directory/qfit
sudo docker run -dt \
  --name "$CONTAINER_NAME" \
  -v "${REPO_DIR}:/tests_directory/qfit" \
  -e QT_QPA_PLATFORM=offscreen \
  "$IMAGE"

# Ensure container is always cleaned up, even on test failure
trap "sudo docker rm -f \"$CONTAINER_NAME\" > /dev/null 2>&1 || true" EXIT

# Set up QGIS profile and link the plugin
echo "--- Setting up QGIS profile and linking plugin ---"
sudo docker exec "$CONTAINER_NAME" bash -c "qgis_setup.sh qfit"

# Install test dependencies inside the container
echo "--- Installing test dependencies ---"
sudo docker exec "$CONTAINER_NAME" bash -c "pip3 install --quiet --break-system-packages pytest pytest-cov pytest-qt pypdf 2>/dev/null || true"

# Run pytest (capture exit code without triggering set -e)
EXIT_CODE=0
sudo docker exec -e QT_QPA_PLATFORM=offscreen -e QFIT_REQUIRE_QGIS=1 "$CONTAINER_NAME" \
  bash -c 'cd /tests_directory/qfit && python3 -m pytest "$@"' bash "$@" || EXIT_CODE=$?

# Clean up (also handled by trap, but keep explicit for clarity)
sudo docker rm -f "$CONTAINER_NAME" > /dev/null 2>&1 || true

echo
echo "=== Done (exit code: $EXIT_CODE) ==="
exit $EXIT_CODE
