from __future__ import annotations

import struct
import subprocess
import sys
import os
import tempfile
from pathlib import Path

import pefile


def pe_subsystem(path: Path) -> int:
    data = path.read_bytes()
    pe_offset = struct.unpack_from("<I", data, 0x3C)[0]
    if data[pe_offset:pe_offset + 4] != b"PE\0\0":
        raise ValueError("File không phải PE hợp lệ.")
    optional_offset = pe_offset + 24
    return struct.unpack_from("<H", data, optional_offset + 68)[0]


def main() -> int:
    if len(sys.argv) != 2:
        print("Usage: verify_build.py <exe>")
        return 2
    executable = Path(sys.argv[1]).resolve()
    if not executable.exists():
        raise FileNotFoundError(executable)
    subsystem = pe_subsystem(executable)
    if subsystem != 2:
        raise RuntimeError(f"EXE không phải Windows GUI subsystem: {subsystem}")
    icon = executable.parent / "_internal" / "resources" / "app_icon.ico"
    icon_data = icon.read_bytes()
    count = struct.unpack_from("<H", icon_data, 4)[0]
    expected_images = set()
    for index in range(count):
        size, offset = struct.unpack_from("<II", icon_data, 6 + index * 16 + 8)
        expected_images.add(icon_data[offset:offset + size])
    with pefile.PE(str(executable)) as pe:
        embedded_images = set()
        images_by_id = {}
        groups = []
        for resource_type in pe.DIRECTORY_ENTRY_RESOURCE.entries:
            if resource_type.id == 3:  # RT_ICON: verify actual pixels, not just an icon flag.
                for resource in resource_type.directory.entries:
                    for language in resource.directory.entries:
                        data = language.data.struct
                        pixels = pe.get_data(data.OffsetToData, data.Size)
                        embedded_images.add(pixels)
                        images_by_id[resource.id] = pixels
            elif resource_type.id == 14:  # RT_GROUP_ICON: Explorer uses the first group.
                for resource in resource_type.directory.entries:
                    for language in resource.directory.entries:
                        data = language.data.struct
                        groups.append(pe.get_data(data.OffsetToData, data.Size))
        if not expected_images or not expected_images.issubset(embedded_images):
            raise RuntimeError("Icon trong EXE không khớp icon ứng dụng.")
        if not groups or struct.unpack_from("<HHH", groups[0]) != (0, 1, count):
            raise RuntimeError("Nhóm icon mặc định của EXE không hợp lệ.")
        first_group_images = set()
        for index in range(count):
            size, resource_id = struct.unpack_from("<IH", groups[0], 6 + index * 14 + 8)
            pixels = images_by_id.get(resource_id, b"")
            if len(pixels) != size:
                raise RuntimeError("Nhóm icon trỏ sai tài nguyên ảnh.")
            first_group_images.add(pixels)
        if first_group_images != expected_images:
            raise RuntimeError("Nhóm icon đầu tiên vẫn dùng hình khác.")
    flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    with tempfile.TemporaryDirectory(prefix="vbdlis-smoke-") as app_data:
        completed = subprocess.run(
            [str(executable), "--smoke-test"],
            timeout=45,
            creationflags=flags,
            env={**os.environ, "APPDATA": app_data},
            check=False,
        )
    if completed.returncode != 0:
        raise RuntimeError(f"Launch smoke-test thất bại, exit code {completed.returncode}")
    print(f"PE Subsystem=2; {count} embedded icon sizes MATCH; launch smoke-test PASS; size={executable.stat().st_size}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
