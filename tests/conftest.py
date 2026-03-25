import os
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
PACKAGE_PARENT = REPO_ROOT.parent

if str(PACKAGE_PARENT) not in sys.path:
    sys.path.insert(0, str(PACKAGE_PARENT))

# Force keyring to use a no-op fail backend in tests.  This prevents the
# SecretService backend from attempting a D-Bus connection (which hangs in
# headless / CI environments) and keeps tests fast and deterministic.
# Production code running inside a real QGIS session on a desktop will use
# whatever backend the OS provides.
os.environ.setdefault("PYTHON_KEYRING_BACKEND", "keyring.backends.fail.Keyring")
