"""The plant harness, and the two roots every plant needs to find.

WHY THE ROOTS ARE SEARCHED FOR RATHER THAN COUNTED. These exact bytes run from two different
places. In the development repository the suite sits at `plugin/tests/`, beside the `gyroscope`
package. Here it sits at `tests/`, at the repository root and OUTSIDE `plugin/` -- because
`plugin/` is precisely what the marketplace installs (`git-subdir`, `path: "plugin"`), so a test
file inside it is a test file on every user's machine. Every module in this suite used to open
with `root = Path(__file__).resolve().parents[1]`, which names a DIFFERENT directory in each of
those two layouts; deriving the roots by looking for the package instead is what lets the two
copies stay byte-identical across the move, and is the reason that line is now written once.
"""
from __future__ import annotations

import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

# The directory `tests/` sits in: `plugin/` in development, the repository root when shipped.
# A child running `python3 -m unittest tests.…` needs this as its cwd for the target to resolve.
TESTS_CWD = Path(__file__).resolve().parents[1]

# The directory holding the `gyroscope` package. The same directory in both layouts, reached
# differently: it IS `TESTS_CWD` in development, and `TESTS_CWD / "plugin"` when shipped.
PLUGIN = TESTS_CWD if (TESTS_CWD / "gyroscope").is_dir() else TESTS_CWD / "plugin"

# The repository root, for the gates that read COMMITTED bytes through `git show`.
REPO = PLUGIN.parent

if str(PLUGIN) not in sys.path:
    # So `import gyroscope` does not depend on which directory the runner was started from.
    sys.path.insert(0, str(PLUGIN))


def smoke_replace(case: unittest.TestCase, path: Path, old: bytes, new: bytes,
                  target: str, expected: str) -> None:
    """Mutate one seam, prove the NAMED test goes red because of it, and restore the bytes.

    The child's environment is set explicitly rather than inherited, because the two directories
    it needs are no longer the same one: `TESTS_CWD` is where `tests.…` resolves from, `PLUGIN` is
    where `gyroscope` resolves from, and in the shipped layout those are parent and child. A plant
    that ran only when the parent happened to be launched from the right directory would report a
    green seam for the wrong reason.
    """
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
    done = subprocess.run(["python3", "-m", "unittest", target], cwd=TESTS_CWD,
                          text=True, capture_output=True, check=False,
                          env={**os.environ, "PYTHONPATH": str(PLUGIN)})
    output = done.stdout + done.stderr
    case.assertNotEqual(0, done.returncode, output)
    case.assertIn(expected, output)
    restore()
    case.assertEqual(original, path.read_bytes(), f"restore differs from backup: {path}")
