"""
services/dwg_processor.py — [섹션 5] 단일 DWG 처리 + 멀티프로세싱 오케스트레이션
app.py의 _process_single_dwg, extract_dwg_data_multiprocess를 그대로 분리.
GUI 콜백(progress_cb) → Job 상태 업데이트 콜백으로 교체. 로직 수정 없음.
"""
from __future__ import annotations
import concurrent.futures
import logging
import math
import os
import re
import threading
import traceback
from pathlib import Path
from typing import Callable, List, Optional, Tuple

import pandas as pd

from backend.services.extractors.ezdxf_extractor import _extract_view_symbols
from backend.services.roi import (
    load_cad, find_도곽_blocks, collect_layout_texts, transform_xref_texts,
)
from backend.services.utils import (
    _정리문자열, _clean_text_from_headers, _clean_title_only,
    _extract_drawing_number, _도면번호_세척,
    _extract_dong_from_title, _extract_group_from_title,
    _extract_scale_smart, _spatial_reconstruct_num_str,
)

logger = logging.getLogger("AutoDWG")


def _process_single_dwg(
    args: Tuple[str, str, dict, float, float, List[Tuple[float, float, str, float]]]
) -> Tuple[List[dict], List[dict], str]:
    """단일 DWG 파일을 분석하여 도면 정보와 뷰심볼 목록을 반환한다.

    ProcessPoolExecutor에서 호출되므로 최상위 함수여야 한다.
    Returns:
        (도면_데이터_list, 뷰심볼_list, 에러메시지)
    """
    전체경로, 목표블록, roi_cfg, base_w, base_h, xref_texts = args
    파일명 = os.path.basename(전체경로)
    데이터, 뷰심볼, 에러메시지 = [], [], ""
    view_roi = roi_cfg.get('view_symbol_roi')
    seen_circles: set = set()  # 파일 전체 기준 원 중복 방지

    try:
        doc = load_cad(Path(전체경로))
        도곽_발견됨 = False

        for layout in doc.layouts:
            도곽들 = find_도곽_blocks(layout, 목표블록)
            if not 도곽들:
                continue
            도곽_발견됨 = True
            레이아웃_원본텍스트 = collect_layout_texts(layout)

            for 도곽 in 도곽들:
                ix, iy = float(도곽.dxf.insert.x), float(도곽.dxf.insert.y)
                xscale, yscale = abs(float(도곽.dxf.xscale)), abs(float(도곽.dxf.yscale))
                너비, 높이 = base_w * xscale, base_h * yscale
                rot_deg = getattr(도곽.dxf, 'rotation', 0.0)
                rad = math.radians(-rot_deg)
                cos_val, sin_val = math.cos(rad), math.sin(rad)

                모든텍스트 = 레이아웃_원본텍스트.copy()
                if xref_texts:
                    모든텍스트.extend(transform_xref_texts(xref_texts, ix, iy, xscale, yscale, rot_deg))

                def get_data_in_roi(roi):
                    """ROI 비율 좌표를 절대 좌표로 변환하여 내부 텍스트를 추출한다."""
                    x_min, x_max = ix + (너비 * roi[0]), ix + (너비 * roi[1])
                    y_min, y_max = iy + (높이 * roi[2]), iy + (높이 * roi[3])
                    박스내글자 = []
                    for t in 모든텍스트:
                        tx, ty, txt, th = t
                        dx, dy = tx - ix, ty - iy
                        unrot_x = ix + (dx * cos_val - dy * sin_val)
                        unrot_y = iy + (dx * sin_val + dy * cos_val)
                        if x_min <= unrot_x <= x_max and y_min <= unrot_y <= y_max:
                            if txt == "-" and th > (x_max - x_min) * 0.8:
                                continue
                            박스내글자.append((unrot_x, unrot_y, txt, th))
                    if not 박스내글자:
                        return "", []
                    # 대시(-) 텍스트 Y 보정
                    for i in range(len(박스내글자)):
                        tx, ty, txt, th = 박스내글자[i]
                        if txt.strip() in ["-", "_", "~"]:
                            closest_y = ty
                            min_dist = float('inf')
                            for j in range(len(박스내글자)):
                                if i == j:
                                    continue
                                ox, oy, otxt, oth = 박스내글자[j]
                                if otxt.strip() not in ["-", "_", "~"]:
                                    if abs(ty - oy) < 높이 * 0.025:
                                        dist_x = abs(tx - ox)
                                        if dist_x < min_dist:
                                            min_dist = dist_x
                                            closest_y = oy
                            박스내글자[i] = (tx, closest_y, txt, th)
                    박스내글자.sort(key=lambda t: -t[1])
                    lines, current_line, current_y = [], [], None
                    for t in 박스내글자:
                        if current_y is None:
                            current_y = t[1]
                            current_line.append(t)
                        elif abs(current_y - t[1]) <= 높이 * 0.015:
                            current_line.append(t)
                        else:
                            current_line.sort(key=lambda x: x[0])
                            lines.append(" ".join([x[2] for x in current_line]))
                            current_y = t[1]
                            current_line = [t]
                    if current_line:
                        current_line.sort(key=lambda x: x[0])
                        lines.append(" ".join([x[2] for x in current_line]))
                    return " ".join(lines), 박스내글자

                n_str, _ = get_data_in_roi(roi_cfg['num_roi'])
                t_str, _ = get_data_in_roi(roi_cfg['title_roi'])
                _, s_texts = get_data_in_roi(roi_cfg['scale_roi'])

                n_str_clean = _clean_text_from_headers(n_str)
                t_str_clean = _clean_text_from_headers(t_str)

                번호_후보 = _extract_drawing_number(n_str_clean)
                raw_matched_str = ""
                if 번호_후보:
                    번호 = _도면번호_세척(번호_후보)
                    raw_matched_str = 번호_후보
                else:
                    fallback_match = re.sub(r"\s*[가-힣\[<【\(].*$", "", n_str_clean).strip("-_ ")
                    번호 = _도면번호_세척(fallback_match)
                    raw_matched_str = fallback_match

                명칭 = t_str_clean
                if raw_matched_str and raw_matched_str in 명칭:
                    명칭 = 명칭.replace(raw_matched_str, "")
                dwg_dong  = _extract_dong_from_title(명칭)
                dwg_group = _extract_group_from_title(명칭) if not dwg_dong else ""
                dwg_group_info = dwg_dong or dwg_group
                if dwg_dong:
                    명칭 = re.sub(r"^" + re.escape(dwg_dong) + r"\s*", "", 명칭).strip()
                if dwg_group:
                    명칭 = re.sub(r"^" + re.escape(dwg_group) + r"\s*", "", 명칭).strip()

                명칭 = _clean_title_only(명칭)
                a1, a3 = _extract_scale_smart(s_texts, is_list_table=False)

                if 번호:
                    데이터.append({
                        "파일명":         파일명,
                        "도면번호(DWG)":  번호,
                        "구분_DWG(그룹)": dwg_group_info,
                        "도면명(DWG)":    명칭.strip(),
                        "축척_A1(DWG)":   a1,
                        "축척_A3(DWG)":   a3,
                    })
                    # 뷰심볼 추출 (view_symbol_roi 설정된 경우에만)
                    if view_roi:
                        for sym in _extract_view_symbols(layout, ix, iy, xscale, yscale, base_w, base_h, view_roi, rot_deg):
                            pos_key = (sym['_cx'], sym['_cy'])
                            if pos_key in seen_circles:
                                continue
                            seen_circles.add(pos_key)
                            sym.pop('_cx')
                            sym.pop('_cy')
                            sym.update({
                                "파일명":       파일명,
                                "도면명(DWG)":  명칭.strip(),
                                "축척_A1(DWG)": a1,
                                "축척_A3(DWG)": a3,
                            })
                            뷰심볼.append(sym)

        del doc
        if not 도곽_발견됨:
            return 데이터, 뷰심볼, "도곽 블록 없음"

    except Exception as e:
        에러메시지 = f"{type(e).__name__}: {e}\n{traceback.format_exc()}"

    return 데이터, 뷰심볼, 에러메시지


def run_multiprocess(
    target_paths: List[str],
    slave_block_name: str,
    roi_cfg: dict,
    base_w: float,
    base_h: float,
    xref_texts: List[Tuple[float, float, str, float]],
    progress_cb: Optional[Callable[[int, int, str], None]] = None,
    cancel_event: Optional[threading.Event] = None,
) -> Tuple[pd.DataFrame, pd.DataFrame]:
    """여러 DWG 파일을 병렬 처리하여 도면 데이터와 뷰심볼 데이터를 반환한다.

    Args:
        target_paths:    분석할 DWG/DXF 파일 경로 목록
        slave_block_name: 개별 도면의 도곽 블록명
        roi_cfg:         ROI 설정 dict
        base_w, base_h:  도곽 원본 크기
        xref_texts:      XREF 원본 텍스트 목록
        progress_cb:     진행률 콜백 (current, total, filename) — Job 상태 업데이트용
        cancel_event:    취소 요청 이벤트

    Returns:
        (dwg_df, view_df)
    """
    _빈_dwg = pd.DataFrame(columns=["파일명", "도면번호(DWG)", "구분_DWG(그룹)", "도면명(DWG)", "축척_A1(DWG)", "축척_A3(DWG)"])
    _빈_뷰  = pd.DataFrame(columns=["파일명", "도면명(DWG)", "축척_A1(DWG)", "축척_A3(DWG)", "뷰_도면명", "뷰_A1축척", "뷰_A3축척"])

    캐드파일들 = sorted(list(set(target_paths)))
    if not 캐드파일들:
        logger.warning("[CAD ] 처리할 도면 파일이 없습니다.")
        return _빈_dwg, _빈_뷰

    총개수 = len(캐드파일들)
    logger.info("[CAD ] 총 %d개의 개별 도면 분석 중... (터보 모드 가동 🚀)", 총개수)
    if progress_cb:
        try:
            progress_cb(0, 총개수, "")
        except Exception:
            pass

    최종_데이터, 최종_뷰심볼 = [], []
    취소됨 = False

    with concurrent.futures.ProcessPoolExecutor() as executor:
        futures = {
            executor.submit(
                _process_single_dwg,
                (path, slave_block_name.strip().lower(), roi_cfg, base_w, base_h, xref_texts)
            ): path
            for path in 캐드파일들
        }
        for i, future in enumerate(concurrent.futures.as_completed(futures), 1):
            if cancel_event is not None and cancel_event.is_set():
                logger.warning("[취소] 사용자 요청으로 잔여 작업을 중단합니다. (완료 %d / 전체 %d)", i - 1, 총개수)
                for f in futures:
                    f.cancel()
                try:
                    executor.shutdown(cancel_futures=True, wait=False)
                except TypeError:
                    executor.shutdown(wait=False)  # Python 3.8 이하 호환
                취소됨 = True
                break

            경로 = futures[future]
            파일명 = os.path.basename(경로)
            try:
                결과, 뷰심볼, 에러 = future.result()
                if 결과:
                    최종_데이터.extend(결과)
                if 뷰심볼:
                    최종_뷰심볼.extend(뷰심볼)
                에러_요약 = 에러.splitlines()[0] if 에러 else "성공"
                logger.info("   [%d/%d] %s: %s (%s)", i, 총개수, '완료' if 결과 else '패스', 파일명, 에러_요약)
                if 에러 and "\n" in 에러:
                    logger.debug("   ↳ 상세 trace:\n%s", 에러)
            except Exception:
                logger.exception("   [%d/%d] 시스템 오류: %s", i, 총개수, 파일명)

            if progress_cb:
                try:
                    progress_cb(i, 총개수, 파일명)
                except Exception:
                    pass

    if 취소됨:
        logger.warning("[취소] 완료된 %d개의 데이터까지만 리포트에 반영됩니다.", len(최종_데이터))
    elif not 최종_데이터:
        logger.warning("[경고] 개별 도면에서 추출된 데이터가 0건입니다. 도곽 블록 이름과 ROI 설정을 확인하세요.")

    dwg_df  = pd.DataFrame(최종_데이터) if 최종_데이터 else _빈_dwg
    view_df = pd.DataFrame(최종_뷰심볼) if 최종_뷰심볼 else _빈_뷰
    return dwg_df, view_df
