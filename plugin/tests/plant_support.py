from __future__ import annotations

import subprocess
import tempfile
import unittest
from pathlib import Path


def smoke_replace(case: unittest.TestCase, path: Path, old: bytes, new: bytes,
                  target: str, cwd: Path, expected: str) -> None:
    original = path.read_bytes()
    case.assertIn(old, original, f"plant seam changed in {path}")
    backup = tempfile.NamedTemporaryFile(prefix=path.name + ".", delete=False)
    backup_path = Path(backup.name)
    backup.write(original)
    backup.close()
    def restore() -> None:
        if backup_path.exists():
            path.write_bytes(backup_path.read_bytes())
            backup_path.unlink()
    case.addCleanup(restore)
    path.write_bytes(original.replace(old, new, 1))
    done = subprocess.run(["python3", "-m", "unittest", target], cwd=cwd,
                          text=True, capture_output=True, check=False)
    output = done.stdout + done.stderr
    case.assertNotEqual(0, done.returncode, output)
    case.assertIn(expected, output)
    restore()
    case.assertEqual(original, path.read_bytes(), f"restore differs from backup: {path}")
