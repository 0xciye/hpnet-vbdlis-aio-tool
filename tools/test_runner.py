"""One-click launcher for the repository's offline test suite."""
from pathlib import Path
import subprocess
import sys


def find_project_root() -> Path:
    executable_dir = Path(sys.executable).resolve().parent
    source_dir = Path(__file__).resolve().parents[1]
    for candidate in (executable_dir, executable_dir.parent, source_dir):
        if (candidate / "run_tests.py").is_file() and (candidate / "src").is_dir():
            return candidate
    raise FileNotFoundError("Khong tim thay run_tests.py va thu muc src canh file EXE.")


def main() -> int:
    try:
        root = find_project_root()
        bundle_dir = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent))
        script = bundle_dir / "kiem_tra_phan_mem.ps1"
        result = subprocess.run(
            ["powershell.exe", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(script), "-ProjectRoot", str(root)],
            cwd=root,
        )
        return result.returncode
    except Exception as exc:
        print(f"[FAIL] {exc}")
        return 1
    finally:
        try:
            input("\nNhan Enter de dong cua so...")
        except EOFError:
            pass


if __name__ == "__main__":
    raise SystemExit(main())
