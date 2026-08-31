import os
from pathlib import Path

def get_unique_path(target_path: Path, conflict_dir: Path) -> Path:
    """
    If target_path exists, generates a unique name in conflict_dir
    """
    conflict_dir.mkdir(parents=True, exist_ok=True)
    
    base_name = target_path.stem
    ext = target_path.suffix
    
    counter = 1
    while True:
        new_name = f"{base_name}__CONFLICT_{counter:03d}{ext}"
        new_path = conflict_dir / new_name
        if not new_path.exists():
            return new_path
        counter += 1
