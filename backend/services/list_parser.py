"""
services/list_parser.py — [섹션 4] 도면목록표 파싱
app.py의 extract_dwg_list_table 함수를 그대로 분리. 로직 수정 없음.
"""
from __future__ import annotations
import logging
import math
import re
from pathlib import Path
from typing import List, Tuple

import pandas as pd

from backend.services.roi import (
    load_cad, find_도곽_blocks, collect_layout_texts, transform_xref_texts,
)
from backend.services.utils import (
    _정리문자열, _clean_text_from_headers, _clean_title_only,
    _extract_drawing_number, _도면번호_세척,
    _extract_dong_from_title, _extract_group_from_title,
    _extract_scale_smart, _spatial_reconstruct_num_str,
    _merge_title_char_runs,
    GLOBAL_IGNORE_HEADERS, CATEGORY_KEYWORDS,
)

logger = logging.getLogger("AutoDWG")


def parse_list_dwg(
    dwg_path: str,
    block_name: str,
    roi_cfg: dict,
    base_w: float,
    base_h: float,
    xref_texts: List[Tuple[float, float, str, float]]
) -> pd.DataFrame:
    """도면목록표 DWG를 파싱하여 DataFrame으로 반환한다.

    Returns:
        컬럼: 도면번호(LIST), 구분_LIST(그룹), 도면명(LIST), 축척_A1(LIST), 축척_A3(LIST)
    """
    logger.info("[LIST] DWG 도면목록표 분석 시작: %s", Path(dwg_path).name)
    데이터 = []
    list_rois = roi_cfg.get('list_rois', [])
    global_ignores_stripped = [h.replace(" ", "").upper() for h in GLOBAL_IGNORE_HEADERS]
    도곽_발견_레이아웃 = 0

    try:
        doc = load_cad(Path(dwg_path))
        for layout in doc.layouts:
            도곽들 = find_도곽_blocks(layout, block_name)
            if not 도곽들:
                continue
            도곽_발견_레이아웃 += 1
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

                target_ranges = list_rois if list_rois else [[0.0, 1.0, 0.0, 1.0]]
                for roi in target_ranges:
                    min_x, max_x = ix + (너비 * roi[0]), ix + (너비 * roi[1])
                    y_min, y_max = iy + (높이 * roi[2]), iy + (높이 * roi[3])
                    roi_w = max_x - min_x

                    num_x_cands, title_x_cands, remark_x_cands = [], [], []
                    a1_matches, a3_matches, 구역_텍스트 = [], [], []

                    for t in 모든텍스트:
                        tx, ty, txt, th = t
                        dx, dy = tx - ix, ty - iy
                        unrot_x = ix + (dx * cos_val - dy * sin_val)
                        unrot_y = iy + (dx * sin_val + dy * cos_val)
                        if not (min_x <= unrot_x <= max_x and y_min <= unrot_y <= y_max):
                            continue
                        clean_t = txt.replace(" ", "").replace("\n", "").strip().upper()
                        if clean_t in ["도면번호", "도연번호", "DWG.NO", "DWG.NO.", "DWGNO", "DRAWINGNO", "번호"]:
                            num_x_cands.append(unrot_x)
                        if clean_t in ["도면명", "DRAWINGTITLE", "TITLE", "도면명칭"]:
                            title_x_cands.append(unrot_x)
                        if clean_t in ["비고", "REMARK", "REMARKS"]:
                            remark_x_cands.append(unrot_x)
                        if txt == "-" and th > roi_w * 0.8:
                            continue
                        if not _extract_drawing_number(txt):
                            if re.search(r"\bA1\b", txt.upper()):
                                a1_matches.append((unrot_x, unrot_y, txt, th))
                            if re.search(r"\bA3\b", txt.upper()):
                                a3_matches.append((unrot_x, unrot_y, txt, th))
                        if any(ih == clean_t for ih in global_ignores_stripped):
                            continue
                        구역_텍스트.append((unrot_x, unrot_y, txt, th))

                    if not 구역_텍스트:
                        continue

                    header_num_x   = sum(num_x_cands) / len(num_x_cands) if num_x_cands else min_x + (roi_w * 0.15)
                    header_title_x = sum(title_x_cands) / len(title_x_cands) if title_x_cands else min_x + (roi_w * 0.5)
                    header_remark_x = sum(remark_x_cands) / len(remark_x_cands) if remark_x_cands else max_x

                    header_a1_cands = [m for m in a1_matches if abs(m[0] - header_num_x) > abs(m[0] - header_title_x)]
                    header_a3_cands = [m for m in a3_matches if abs(m[0] - header_num_x) > abs(m[0] - header_title_x)]
                    header_a1_item  = sorted(header_a1_cands, key=lambda v: -v[1])[0] if header_a1_cands else None
                    header_a3_item  = sorted(header_a3_cands, key=lambda v: -v[1])[0] if header_a3_cands else None
                    if header_a1_item and header_a1_item in 구역_텍스트:
                        구역_텍스트.remove(header_a1_item)
                    if header_a3_item and header_a3_item in 구역_텍스트:
                        구역_텍스트.remove(header_a3_item)
                    header_a1_x = header_a1_item[0] if header_a1_item else None
                    header_a3_x = header_a3_item[0] if header_a3_item else None

                    # 대시(-) 텍스트의 Y를 가장 가까운 실제 텍스트 행의 Y로 보정
                    for i in range(len(구역_텍스트)):
                        tx, ty, txt, th = 구역_텍스트[i]
                        if txt.strip() in ["-", "_", "~"]:
                            closest_y = ty
                            min_dist = float('inf')
                            for j in range(len(구역_텍스트)):
                                if i == j:
                                    continue
                                ox, oy, otxt, oth = 구역_텍스트[j]
                                if otxt.strip() not in ["-", "_", "~"]:
                                    if abs(ty - oy) < 높이 * 0.025:
                                        dist_x = abs(tx - ox)
                                        if dist_x < min_dist:
                                            min_dist = dist_x
                                            closest_y = oy
                            구역_텍스트[i] = (tx, closest_y, txt, th)

                    # Y 내림차순 정렬 후 같은 행으로 묶기
                    구역_텍스트.sort(key=lambda x: -x[1])
                    sub_lines, curr_sub, curr_y = [], [], None
                    for t in 구역_텍스트:
                        if curr_y is None or abs(curr_y - t[1]) <= 높이 * 0.012:
                            curr_y = t[1]
                            curr_sub.append(t)
                        else:
                            curr_sub.sort(key=lambda x: x[0])
                            sub_lines.append({'y': curr_y, 'texts': curr_sub})
                            curr_y = t[1]
                            curr_sub = [t]
                    if curr_sub:
                        curr_sub.sort(key=lambda x: x[0])
                        sub_lines.append({'y': curr_y, 'texts': curr_sub})

                    # 도면번호가 있는 행과 없는 행 분리
                    rows, unassigned_sub_lines = [], []
                    for sub in sub_lines:
                        full_str = " ".join([t[2] for t in sub['texts']])
                        num_texts = [t for t in sub['texts'] if abs(t[0] - header_num_x) <= abs(t[0] - header_title_x)]
                        num_str = _spatial_reconstruct_num_str(num_texts)
                        has_draw_num = bool(_extract_drawing_number(num_str) or _extract_drawing_number(full_str))
                        is_category = False
                        if not has_draw_num:
                            if any(kw in full_str.replace(" ", "") for kw in CATEGORY_KEYWORDS):
                                is_category = True
                            elif re.search(r"^[A-Z0-9\-_]*\s*[\[<【].+?[\]>】]\s*$", full_str):
                                is_category = True
                        if is_category:
                            continue
                        raw_drw_no = _extract_drawing_number(num_str) or _extract_drawing_number(full_str)
                        drw_no, raw_matched_str = "", ""
                        if raw_drw_no:
                            drw_no = _도면번호_세척(raw_drw_no)
                            raw_matched_str = raw_drw_no
                        else:
                            if num_texts:
                                fallback_match = re.sub(r"\s*[가-힣\[<【\(].*$", "", num_str).strip("-_ ")
                                if not fallback_match:
                                    fallback_match = num_str.strip()
                                if re.search(r"\d", fallback_match) and len(fallback_match) >= 3 and not re.search(r"[\[\]<>\(【】]", fallback_match):
                                    drw_no = _도면번호_세척(fallback_match)
                                    raw_matched_str = fallback_match
                        if drw_no:
                            rows.append({'anchor_y': sub['y'], 'sub_lines': [{'y': sub['y'], 'texts': sub['texts'], 'raw_drw_no': raw_matched_str}], 'drw_no': drw_no})
                        else:
                            unassigned_sub_lines.append({'y': sub['y'], 'texts': sub['texts']})

                    # 도면번호 없는 행을 가장 가까운 도면번호 행에 붙이기
                    for sub in unassigned_sub_lines:
                        if not rows:
                            continue
                        closest_row = min(rows, key=lambda r: abs(r['anchor_y'] - sub['y']))
                        if abs(closest_row['anchor_y'] - sub['y']) < 높이 * 0.04:
                            closest_row['sub_lines'].append(sub)

                    # 1차 패스: 모든 행의 도면명과 그룹 후보를 미리 계산
                    precomputed = []
                    for row in rows:
                        row['sub_lines'].sort(key=lambda s: -s['y'])
                        pw, at = [], []
                        for sub in row['sub_lines']:
                            sts = sorted(sub['texts'], key=lambda x: x[0])
                            tt = [t for t in sts if not (header_remark_x and abs(t[0] - header_remark_x) < abs(t[0] - header_title_x))]
                            rls = _spatial_reconstruct_num_str(tt)
                            to = rls
                            if sub.get('raw_drw_no') and sub['raw_drw_no'] in rls:
                                parts = rls.split(sub['raw_drw_no'], 1)
                                to = parts[1] if len(parts) > 1 else ""
                            to = _merge_title_char_runs(to)
                            cl = _clean_title_only(to)
                            if cl:
                                pw.append(cl)
                            at.extend(sts)
                        m = " ".join(pw).strip()
                        ed = _extract_dong_from_title(m)
                        eg = _extract_group_from_title(m) if not ed else ""
                        precomputed.append({'drw_no': row['drw_no'], 'title': m, 'dong': ed, 'group': eg, 'candidate': ed or eg, 'all_texts': at})

                    # 2차 패스: 연속 행에 같은 후보가 반복되면 그룹이 아닌 도면명 일부로 처리
                    prop_group = ""
                    for i, pc in enumerate(precomputed):
                        번호 = pc['drw_no']
                        명칭 = pc['title']
                        extracted_dong  = pc['dong']
                        extracted_group = pc['group']
                        candidate       = pc['candidate']
                        all_texts       = pc['all_texts']
                        if candidate:
                            prev_cand = precomputed[i - 1]['candidate'] if i > 0 else ""
                            next_cand = precomputed[i + 1]['candidate'] if i + 1 < len(precomputed) else ""
                            if next_cand == candidate or prev_cand == candidate:
                                current_group = prop_group
                            else:
                                if extracted_dong:
                                    명칭 = re.sub(r"^" + re.escape(extracted_dong) + r"\s*", "", 명칭).strip()
                                if extracted_group:
                                    명칭 = re.sub(r"^" + re.escape(extracted_group) + r"\s*", "", 명칭).strip()
                                prop_group = candidate
                                current_group = candidate
                        else:
                            current_group = prop_group

                        a1, a3 = _extract_scale_smart(all_texts, header_a1_x, header_a3_x, is_list_table=True)
                        데이터.append({
                            "도면번호(LIST)":  번호,
                            "구분_LIST(그룹)": current_group,
                            "도면명(LIST)":    명칭,
                            "축척_A1(LIST)":   a1,
                            "축척_A3(LIST)":   a3,
                        })

    except Exception:
        logger.exception("목록표 분석 중 오류")

    if 도곽_발견_레이아웃 == 0:
        logger.warning(
            "[경고] 도면목록표에서 '%s' 도곽 블록을 찾지 못했습니다. 블록 이름과 ROI 설정을 확인하세요.",
            block_name
        )

    df = pd.DataFrame(데이터)
    if df.empty:
        logger.warning("[경고] 도면목록표 추출 결과가 0건입니다. ROI(단 박스) 범위를 다시 확인해 주세요.")
        return pd.DataFrame(columns=["도면번호(LIST)", "구분_LIST(그룹)", "도면명(LIST)", "축척_A1(LIST)", "축척_A3(LIST)"])

    before = len(df)
    df = df.drop_duplicates(subset=["도면번호(LIST)"]).reset_index(drop=True)
    if before != len(df):
        logger.warning("[경고] 도면목록표에 도면번호 중복 행 %d개 발견 → 첫 행만 채택했습니다.", before - len(df))
    return df
