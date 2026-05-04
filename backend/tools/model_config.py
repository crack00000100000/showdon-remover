import os
from backend.config import config, BASE_DIR
from backend.tools.constant import SubtitleDetectMode

_MODEL_NAME_MAP = {
    SubtitleDetectMode.PP_OCRv5_MOBILE: "PP-OCRv5_mobile_det",
    SubtitleDetectMode.PP_OCRv5_SERVER: "PP-OCRv5_server_det",
}


class ModelConfig:
    def __init__(self):
        self.STTN_AUTO_MODEL_PATH = os.path.join(BASE_DIR, 'models', 'sttn-auto', 'infer_model.pth')
        if config.subtitleDetectMode.value == SubtitleDetectMode.PP_OCRv5_MOBILE:
            self.DET_MODEL_DIR = os.path.join(BASE_DIR, 'models', 'V5', 'ch_det_fast')
        elif config.subtitleDetectMode.value == SubtitleDetectMode.PP_OCRv5_SERVER:
            self.DET_MODEL_DIR = os.path.join(BASE_DIR, 'models', 'V5', 'ch_det')
        else:
            raise ValueError(f"Invalid subtitle detect mode: {config.subtitleDetectMode.value}")
        self.DET_MODEL_NAME = _MODEL_NAME_MAP[config.subtitleDetectMode.value]
