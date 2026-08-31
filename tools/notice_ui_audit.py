"""Compare business code before/after the notice UI and help-only update."""
import argparse
import ast
import copy
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PRESENTATION = {
    'src/tools/notice_builder/ui.py',
    'src/tools/notice_builder/presentation.py',
    'src/tools/notice_builder/assets/ui-chevron-down.svg',
    'src/tools/notice_builder/assets/ui-chevron-up.svg',
    'src/tools/notice_builder/assets/ui-check.svg',
}


def snapshot():
    files = {}
    for directory in (ROOT/'src/tools', ROOT/'src/nodes_tools'):
        for path in directory.rglob('*'):
            relative = path.relative_to(ROOT).as_posix()
            if (path.is_file() and relative not in PRESENTATION
                    and not {'__pycache__', '.pytest_cache', 'tests'}.intersection(path.parts)):
                files[relative] = hashlib.sha256(path.read_bytes()).hexdigest()
    for name in ('src/launcher.py', 'docs/HUONG_DAN_BAN_SUA.txt', 'Huong_dan_su_dung_chi_tiet.txt', 'README.txt'):
        files[name] = hashlib.sha256((ROOT/name).read_bytes()).hexdigest()
    tree = ast.parse((ROOT/'src/tools/notice_builder/ui.py').read_text(encoding='utf-8'))
    methods = {}
    for node in tree.body:
        if isinstance(node, ast.ClassDef):
            for method in node.body:
                if isinstance(method, ast.FunctionDef):
                    preserved = copy.deepcopy(method)
                    if node.name == 'MainWindow' and method.name == '__init__':
                        # The only addition allowed inside the existing constructor.
                        preserved.body = [statement for statement in preserved.body
                            if not (isinstance(statement, ast.Expr)
                                and ast.dump(statement.value, include_attributes=False) == ast.dump(
                                    ast.parse('apply_presentation(self)', mode='eval').body, include_attributes=False))]
                    methods[f'{node.name}.{method.name}'] = ast.dump(preserved, include_attributes=False)
    return {'files': files, 'notice_methods': methods}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('mode', choices=('baseline', 'verify'))
    parser.add_argument('path', type=Path)
    args = parser.parse_args()
    if args.mode == 'baseline':
        if args.path.exists(): raise SystemExit('Refusing to replace the original baseline')
        args.path.write_text(json.dumps(snapshot(), ensure_ascii=False, indent=2), encoding='utf-8')
    else:
        after = snapshot()
        assert json.loads(args.path.read_text(encoding='utf-8')) == after, 'Business code, guides or resources changed'
        print(f"UNCHANGED: {len(after['files'])} files; {len(after['notice_methods'])} notice methods")
