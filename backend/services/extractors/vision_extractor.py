"""
extractors/vision_extractor.py — Vision AI 기반 추출 엔진 (준비 중 stub)
이 파일은 향후 Vision API 연동 시 구현한다.
현재는 호출 시 NotImplementedError를 raise한다.
"""
from backend.services.extractors.base import BaseExtractor


class VisionExtractor(BaseExtractor):
    """Vision AI 기반 추출 엔진 — 현재 미구현."""

    def extract_title_block(self, dxf_path: str, roi_config: dict) -> dict:
        raise NotImplementedError(
            "Vision AI 추출 엔진은 아직 준비 중입니다. "
            "설정에서 추출 방식을 'ezdxf'로 변경하세요."
        )
