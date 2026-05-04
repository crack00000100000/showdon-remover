from enum import Enum, unique

@unique
class InpaintMode(Enum):
    """
    인페인팅 모드 enum.
    v0.2.0: STTN_DET / LAMA / PROPAINTER 제거 (이미지 모드 폐지 + 사용처 협소).
    v0.2.1: MINIMAX 롤백 — 쇼츠의 동적 객체 + 자막 겹침 케이스에서 객체 통째로 손상.
            시간축 참조 없는 diffusion + minimal hallucination 철학이 쇼츠 워크플로우에 부적합.
    """
    STTN_AUTO = "sttn-auto"
    OPENCV = "opencv"

@unique
class SubtitleDetectMode(Enum):
    """
    字幕检测算法枚举
    """
    PP_OCRv5_MOBILE = "PP_OCRv5_MOBILE"
    PP_OCRv5_SERVER = "PP_OCRv5_SERVER"