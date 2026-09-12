from typing import List
from pathlib import Path
from tools.hpnet_file_generator.models.data_models import SourceFile, GenerationAction, ActionStatus, ProfileConfig
from tools.hpnet_file_generator.core.naming_engine import NamingEngine
from tools.hpnet_file_generator.utils.path_utils import get_unique_path

class ActionPlanner:
    def __init__(self, source_files: List[SourceFile], output_folder: str, config: ProfileConfig):
        self.source_files = source_files
        self.output_folder = Path(output_folder)
        self.config = config
        self.naming_engine = NamingEngine(config)
        self.conflict_folder = self.output_folder / "CONFLICT"

    def build_plan(self) -> List[GenerationAction]:
        actions = []
        target_map = {} # target_path: Action to detect conflicts
        reserved_conflict_paths = set()

        for sf in self.source_files:
            if sf.is_ambiguous:
                # Add a warning action just for display
                actions.append(GenerationAction(
                    source_file=sf,
                    parcel=None, # type: ignore
                    suffix="",
                    target_filename="",
                    target_path=Path(""),
                    status=ActionStatus.WARNING,
                    reason=sf.match_issue or "Không thể xác định duy nhất người trong Excel"
                ))
                continue
                
            if not sf.matched_person:
                actions.append(GenerationAction(
                    source_file=sf,
                    parcel=None, # type: ignore
                    suffix="",
                    target_filename="",
                    target_path=Path(""),
                    status=ActionStatus.WARNING,
                    reason=sf.match_issue or "Không tìm thấy tên trong Excel"
                ))
                continue

            for issue in sf.matched_person.data_issues:
                actions.append(GenerationAction(
                    source_file=sf,
                    parcel=None, # type: ignore
                    suffix="",
                    target_filename="",
                    target_path=Path(""),
                    status=ActionStatus.WARNING,
                    reason=issue,
                ))
                
            if not sf.matched_person.parcels and not sf.matched_person.data_issues:
                actions.append(GenerationAction(
                    source_file=sf,
                    parcel=None, # type: ignore
                    suffix="",
                    target_filename="",
                    target_path=Path(""),
                    status=ActionStatus.WARNING,
                    reason="Người dùng không có thông tin Số tờ/Số thửa hợp lệ"
                ))
                continue
                
            # Create actions for each parcel and each suffix
            for parcel in sf.matched_person.parcels:
                for suffix in self.config.suffixes:
                    action = GenerationAction(
                        source_file=sf,
                        parcel=parcel,
                        suffix=suffix,
                        target_filename="",
                        target_path=Path("")
                    )
                    
                    target_name = self.naming_engine.generate_filename(action)
                    target_path = self.output_folder / target_name
                    
                    action.target_filename = target_name
                    action.target_path = target_path
                    
                    # Detect conflicts
                    if target_path in target_map:
                        # Existing action generated same path!
                        action.status = ActionStatus.CONFLICT
                        action.reason = "Trùng tên file được tạo ra bởi người khác"
                        action.conflict_path = get_unique_path(target_path, self.conflict_folder, reserved_conflict_paths)
                        reserved_conflict_paths.add(action.conflict_path)

                        # Không để bản đầu tiên lọt vào thư mục kết quả chính khi chính
                        # tên đích đó có nhiều nguồn cạnh tranh.
                        original = target_map[target_path]
                        if original.status == ActionStatus.READY:
                            original.status = ActionStatus.CONFLICT
                            original.reason = "Trùng tên file được tạo ra bởi người khác"
                            original.conflict_path = get_unique_path(target_path, self.conflict_folder, reserved_conflict_paths)
                            reserved_conflict_paths.add(original.conflict_path)
                    elif target_path.exists():
                        # File already exists on disk
                        action.status = ActionStatus.CONFLICT
                        action.reason = "File đích đã tồn tại trên ổ cứng"
                        action.conflict_path = get_unique_path(target_path, self.conflict_folder, reserved_conflict_paths)
                        reserved_conflict_paths.add(action.conflict_path)
                    else:
                        action.status = ActionStatus.READY
                        target_map[target_path] = action
                        
                    actions.append(action)
                    
        return actions
