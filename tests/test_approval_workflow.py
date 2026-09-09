"""Run approval workflow doubles without sending documents to HPNet."""
import shutil
import subprocess
from pathlib import Path

import pytest


def test_approval_workflow():
    root = Path(__file__).resolve().parents[1]
    node = root / 'src/nodes_tools/runtime/node.exe'
    executable = str(node) if node.exists() else shutil.which('node')
    if not executable:
        pytest.skip('Node runtime unavailable')
    result = subprocess.run([executable, str(root / 'tests/approval_workflow.cjs')],
                            capture_output=True, timeout=30)
    assert result.returncode == 0, result.stdout + result.stderr
    assert b'APPROVAL_WORKFLOW_TEST_OK' in result.stdout
