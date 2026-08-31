from tools.hpnet_file_generator.models.data_models import GenerationAction, ProfileConfig
from tools.hpnet_file_generator.utils.text_normalizer import sanitize_filename
from pathlib import Path

class NamingEngine:
    def __init__(self, config: ProfileConfig):
        self.config = config

    def generate_filename(self, action: GenerationAction) -> str:
        template = self.config.template
        
        # Replace placeholders safely
        replacements = {
            "{PREFIX}": self.config.prefix,
            "{MA_DVHC}": self.config.ma_dvhc,
            "{SO_TO}": action.parcel.so_to,
            "{SO_THUA}": action.parcel.so_thua,
            "{HAU_TO}": action.suffix,
            "{HO_TEN}": action.source_file.matched_person.ho_ten if action.source_file.matched_person else "",
            "{STT}": action.source_file.stt or "",
            "{SOURCE_NAME}": action.source_file.original_path.stem
        }
        
        filename = template
        for key, val in replacements.items():
            filename = filename.replace(key, val)
            
        # Clean up in case some placeholders were empty causing e.g. "___" or "--"
        # Optional: implement if needed, but simple string replace might leave artifacts
        
        # Add extension
        filename = sanitize_filename(filename) + action.source_file.extension
        return filename
