"""Developer-friendly launcher for the FastAPI backend."""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
from pathlib import Path

import uvicorn

_BOOTSTRAP_ENV_VAR = "BACKEND_UV_BOOTSTRAPPED"


def parse_args() -> argparse.Namespace:
    """Parse CLI arguments for local development server startup."""
    parser = argparse.ArgumentParser(description="Run OptiCredit backend server.")
    parser.add_argument("--host", default="0.0.0.0", help="Host interface (default: 0.0.0.0)")
    parser.add_argument("--port", type=int, default=8000, help="Port number (default: 8000)")
    parser.add_argument(
        "--reload",
        dest="reload",
        action="store_true",
        default=True,
        help="Enable auto-reload (default: enabled)",
    )
    parser.add_argument(
        "--no-reload",
        dest="reload",
        action="store_false",
        help="Disable auto-reload",
    )
    parser.add_argument(
        "--log-level",
        default="debug",
        choices=["critical", "error", "warning", "info", "debug", "trace"],
        help="Uvicorn log level (default: debug)",
    )
    parser.add_argument(
        "--access-log",
        dest="access_log",
        action="store_true",
        default=True,
        help="Enable access logs (default: enabled)",
    )
    parser.add_argument(
        "--no-access-log",
        dest="access_log",
        action="store_false",
        help="Disable access logs",
    )
    parser.add_argument(
        "--workers",
        type=int,
        default=1,
        help="Number of workers when reload is disabled (default: 1)",
    )
    parser.add_argument(
        "--check-ocr",
        action="store_true",
        help="Only verify OCR dependencies (paddle, paddleocr, chardet) and exit.",
    )
    return parser.parse_args()


def _bootstrap_with_uv_if_needed() -> None:
    """Re-run this script with `uv run` so project .venv is used automatically."""
    if os.getenv(_BOOTSTRAP_ENV_VAR) == "1":
        return

    project_root = Path(__file__).resolve().parent
    project_venv = project_root / ".venv"
    active_venv = os.getenv("VIRTUAL_ENV")
    if active_venv and Path(active_venv).resolve() == project_venv.resolve():
        return
    if Path(sys.prefix).resolve() == project_venv.resolve():
        return

    uv_path = shutil.which("uv")
    if not uv_path:
        return

    script_path = Path(__file__).resolve()
    command = [uv_path, "run", "python", str(script_path), *sys.argv[1:]]
    env = os.environ.copy()
    env[_BOOTSTRAP_ENV_VAR] = "1"

    completed = subprocess.run(command, env=env, check=False)
    raise SystemExit(completed.returncode)


def _check_ocr_dependencies() -> None:
    """Validate OCR runtime imports from the active environment."""
    import chardet  # noqa: F401
    import paddle  # noqa: F401
    import paddleocr  # noqa: F401

    print("OCR OK")


def main() -> None:
    """Entry point used by `python main.py`."""
    _bootstrap_with_uv_if_needed()
    args = parse_args()

    if args.check_ocr:
        _check_ocr_dependencies()
        return

    uvicorn.run(
        "app.main:app",
        host=args.host,
        port=args.port,
        reload=args.reload,
        log_level=args.log_level,
        access_log=args.access_log,
        workers=1 if args.reload else args.workers,
    )


if __name__ == "__main__":
    main()
