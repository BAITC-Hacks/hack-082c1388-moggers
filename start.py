"""Start the local website on Windows, macOS or Linux: python start.py."""
from pathlib import Path
import shutil
import subprocess
import sys


def main() -> int:
    root = Path(__file__).resolve().parent
    local_python = root / ".venv" / ("Scripts/python.exe" if sys.platform == "win32" else "bin/python")
    python = str(local_python) if local_python.exists() else sys.executable
    if not (root / "out/features.parquet").exists():
        subprocess.run([python, "-X", "utf8", "-m", "moneygraph.pipeline",
                        "--data", str(root / "data"), "--out", str(root / "out")],
                       cwd=root, check=True)
    if not (root / "frontend/dist/index.html").exists():
        npm = shutil.which("npm.cmd" if sys.platform == "win32" else "npm")
        if not npm:
            raise SystemExit("Node.js/npm is required to build the frontend.")
        subprocess.run([npm, "run", "build", "--prefix", "frontend"], cwd=root, check=True)
    print("MoneyGraph: http://127.0.0.1:8000", flush=True)
    try:
        return subprocess.call([python, "-X", "utf8", "-m", "uvicorn", "moneygraph.api:app",
                                "--host", "127.0.0.1", "--port", "8000"], cwd=root)
    except KeyboardInterrupt:
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
