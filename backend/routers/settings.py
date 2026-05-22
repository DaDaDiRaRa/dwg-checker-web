"""
routers/settings.py — 추출 방식 설정 엔드포인트
GET   /api/settings/extractor   현재 추출 방식 반환
PATCH /api/settings/extractor   ezdxf / vision 전환
"""
from fastapi import APIRouter, HTTPException

from backend import config
from backend.models.schemas import ExtractorResponse, ExtractorPatchRequest

router = APIRouter(prefix="/api/settings", tags=["settings"])

VALID_EXTRACTORS = {"ezdxf", "vision"}


@router.get("/extractor", response_model=ExtractorResponse)
def get_extractor():
    """현재 설정된 추출 엔진을 반환한다."""
    return ExtractorResponse(extractor=config.EXTRACTOR)


@router.patch("/extractor", response_model=ExtractorResponse)
def set_extractor(body: ExtractorPatchRequest):
    """추출 엔진을 ezdxf 또는 vision으로 변경한다.

    vision 선택 시 NotImplementedError가 런타임에 발생하므로
    프론트에서 "준비 중" 안내를 표시해야 한다.
    """
    if body.extractor not in VALID_EXTRACTORS:
        raise HTTPException(
            status_code=400,
            detail=f"지원하지 않는 추출 방식입니다. 선택 가능: {VALID_EXTRACTORS}"
        )
    config.EXTRACTOR = body.extractor
    return ExtractorResponse(extractor=config.EXTRACTOR)
