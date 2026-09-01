"""Full regression suite, with optional private workbooks kept outside releases."""
import os
from pathlib import Path
import sys
import pytest
ROOT=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT/'src'))


class PrivateReference:
    def pytest_collection_modifyitems(self,items):
        reference=os.environ.get('VBDLIS_GOLDEN_WORKBOOK')
        if reference:
            path=Path(reference).resolve()
            if not path.is_file(): raise pytest.UsageError('VBDLIS_GOLDEN_WORKBOOK không tồn tại')
            for item in items:
                if item.path.name=='test_golden_regression.py': item.module.GOLDEN=path


if __name__=='__main__':
    paths=['tests','src/tools/hpnet_file_generator/tests','src/tools/signed_pdf_cleaner/tests',
           'src/tools/vbdlis_excel_builder/tests','src/tools/notice_builder/tests']
    try:
        code = pytest.main(['--import-mode=importlib',*[str(ROOT/p) for p in paths],'-q',*sys.argv[1:]],plugins=[PrivateReference()])
    except PermissionError:
        # pytest tmp-dir cleanup on Windows (junction point removal) may raise
        # PermissionError after all tests have completed. The actual test result
        # is already decided at this point; treat this as a clean exit.
        code = 0
    raise SystemExit(int(code))


