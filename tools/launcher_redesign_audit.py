"""Read-only scope verification and an explicit cleanup proposal; never deletes files."""
import argparse
import ast
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
UI_METHODS = {"__init__", "label", "setup_ui", "create_tool_card", "open_help"}


def digest(path):
    with path.open("rb") as stream: return hashlib.file_digest(stream,"sha256").hexdigest()


def snapshot():
    files={}
    for directory in (ROOT/"src/tools",ROOT/"src/nodes_tools"):
        for path in directory.rglob("*"):
            if path.is_file() and not {"__pycache__",".pytest_cache","tests"}.intersection(path.parts):
                files[path.relative_to(ROOT).as_posix()]=digest(path)
    tree=ast.parse((ROOT/"src/launcher.py").read_text(encoding="utf-8"))
    nodes={}
    for node in tree.body:
        if isinstance(node,(ast.FunctionDef,ast.AsyncFunctionDef)):
            nodes[node.name]=ast.dump(node,include_attributes=False)
        if isinstance(node,ast.ClassDef) and node.name=="ToolLauncher":
            for method in node.body:
                if isinstance(method,ast.FunctionDef) and method.name not in UI_METHODS:
                    nodes[method.name]=ast.dump(method,include_attributes=False)
        if isinstance(node,ast.Assign) and any(isinstance(n,ast.Name) and n.id=="EXTERNAL_TOOLS" for n in node.targets):
            nodes["EXTERNAL_TOOLS"]=ast.dump(node,include_attributes=False)
    return {"files":files,"launcher_logic":nodes}


def propose(output):
    targets=list((ROOT/"build").iterdir())+list((ROOT/"release").iterdir())
    targets += [ROOT/p for p in ("src/build","src/dist","HPNET & VBDLIS Tools Release.zip","patch_imports.py",
        ".pytest_cache","docs/ui-verification","docs/console-smoke.json","docs/source-smoke.json","docs/zip-extracted-smoke.json")]
    targets += list((ROOT/"src").rglob("__pycache__"))+list((ROOT/"tests").rglob("__pycache__"))
    selected=[]
    for path in sorted(set(p.resolve() for p in targets if p.exists()), key=lambda p:(len(p.parts),str(p))):
        if not any(path.is_relative_to(parent) for parent in selected): selected.append(path)
    entries=[]
    for path in selected:
        files=[p for p in path.rglob("*") if p.is_file()] if path.is_dir() else [path]
        entries.append({"path":str(path),"type":"directory" if path.is_dir() else "file","files":len(files),"bytes":sum(p.stat().st_size for p in files)})
    output.write_text(json.dumps({"status":"AWAITING_USER_CONFIRMATION","workspace":str(ROOT),"targets":entries},ensure_ascii=False,indent=2),encoding="utf-8")
    lines=["# Đề xuất dọn dẹp — CHƯA XÓA", "", "Chỉ xóa sau khi người dùng xác nhận và bản release thay thế đã được kiểm tra. Danh sách cố định tại thời điểm khảo sát, không bao gồm file/build mới sinh sau đó.", "",
           "Giữ: toàn bộ mã nghiệp vụ và asset runtime, .venv (môi trường build), tests/run_tests.py (kiểm tra hồi quy, KHÔNG đưa vào ZIP), .agents/skills, tài liệu nguồn hướng dẫn, research/notice_template (tham chiếu đang được test sử dụng), review (hồ sơ riêng).", "", "| Đường dẫn trong workspace | Số file | MiB |", "|---|---:|---:|"]
    lines += [f"| {Path(e['path']).relative_to(ROOT).as_posix()} | {e['files']} | {e['bytes']/1048576:.1f} |" for e in entries]
    lines += ["",f"Tổng: {len(entries)} mục; {sum(e['bytes'] for e in entries)/1073741824:.2f} GiB. Chưa xóa mục nào."]
    output.with_suffix(".md").write_text("\n".join(lines),encoding="utf-8")
    print(json.dumps({"targets":len(entries),"GiB":round(sum(e['bytes'] for e in entries)/1073741824,2),"manifest":str(output)},ensure_ascii=False))


if __name__=="__main__":
    parser=argparse.ArgumentParser(); parser.add_argument("mode",choices=("baseline","verify","cleanup-proposal")); parser.add_argument("path",type=Path)
    args=parser.parse_args()
    if args.mode=="baseline":
        args.path.write_text(json.dumps(snapshot(),ensure_ascii=False,indent=2),encoding="utf-8")
    elif args.mode=="cleanup-proposal": propose(args.path)
    else:
        before=json.loads(args.path.read_text(encoding="utf-8")); after=snapshot()
        assert before==after,"Protected core/assets or launcher routing changed"
        print(f"LOGIC_UNCHANGED: {len(after['files'])} files; {len(after['launcher_logic'])} launcher logic nodes")
