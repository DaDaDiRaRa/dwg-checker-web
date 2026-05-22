"""
extractors/__init__.py — 추출 엔진 선택기
config.EXTRACTOR 값에 따라 ezdxf_extractor 또는 vision_extractor를 반환한다.
"""
from backend import config
from backend.services.extractors.base import BaseExtractor


def get_extractor() -> BaseExtractor:
    """현재 설정된 EXTRACTOR에 해당하는 구현체를 반환한다."""
    if config.EXTRACTOR == "vision":
        from backend.services.extractors.vision_extractor import VisionExtractor
        return VisionExtractor()
    # 기본값: ezdxf
    from backend.services.extractors.ezdxf_extractor import EzdxfExtractor
    return EzdxfExtractor()
