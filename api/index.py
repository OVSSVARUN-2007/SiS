import sys
from pathlib import Path

# Ensure project root is importable when running from /api on Vercel.
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.append(str(ROOT))

from main import app  # noqa: E402
