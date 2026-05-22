"""
extractors/base.py — 추출기 추상 인터페이스
모든 추출 구현체는 이 클래스를 상속하고 extract_title_block을 구현해야 한다.
"""
from __future__ import annotations
from abc import ABC, abstractmethod


class BaseExtractor(ABC):

    @abstractmethod
    def extract_title_block(self, dxf_path: str, roi_config: dict) -> dict:
        """도곽에서 도면 정보를 추출한다.

        Args:
            dxf_path:   변환 완료된 DXF 파일 경로
            roi_config: SET_ROI.lsp가 생성한 ROI 설정 dict
                        키: base_w, base_h, num_roi, title_roi, scale_roi,
                            list_rois, view_symbol_roi

        Returns:
            {
                "도면번호":  str,
                "도면명":    str,
                "구분":      str,   # 동/그룹 정보
                "축척_A1":  str,
                "축척_A3":  str,
                "뷰심볼":   list[dict]  # 뷰심볼 검토용 (없으면 빈 리스트)
            }
        """
        ...
