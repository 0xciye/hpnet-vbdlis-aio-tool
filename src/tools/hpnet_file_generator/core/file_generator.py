import shutil
import os
from tools.hpnet_file_generator.models.data_models import GenerationAction, ActionStatus

class FileGenerator:
    def __init__(self):
        pass

    def execute_action(self, action: GenerationAction) -> GenerationAction:
        if action.status not in (ActionStatus.READY, ActionStatus.CONFLICT):
            return action
            
        temp_target = None
        try:
            source = action.source_file.original_path
            
            if action.status == ActionStatus.READY:
                target = action.target_path
            else: # CONFLICT
                target = action.conflict_path
                target.parent.mkdir(parents=True, exist_ok=True)
                
            # Copy to temp first to ensure safety
            temp_target = target.with_suffix('.tmp_hpnet')
            shutil.copy2(source, temp_target)
            
            # Verify size
            if os.path.getsize(source) != os.path.getsize(temp_target):
                os.remove(temp_target)
                raise Exception("Lỗi copy: Kích thước file không khớp.")
                
            # Rename temp to final
            os.rename(temp_target, target)
            
            action.status = ActionStatus.SUCCESS
            action.reason = f"Đã copy thành công tới: {target}"
            
        except Exception as e:
            action.status = ActionStatus.ERROR
            action.reason = str(e)
        finally:
            if temp_target is not None and temp_target.exists():
                temp_target.unlink()
            
        return action
