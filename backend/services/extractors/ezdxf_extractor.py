"""
extractors/ezdxf_extractor.py — [섹션 3] ezdxf 기반 DXF 파싱 엔진 (기본값)
app.py 섹션 3의 뷰심볼 추출 + 개별 도면 텍스트 추출 로직을 그대로 이식.
로직 수정 없음.
"""
from __future__ import annotations
import logging
import math
import re
from pathlib import Path
from typing import List, Tuple

from backend.services.extractors.base import BaseExtractor
from backend.services.roi import (
    load_cad, find_도곽_blocks, collect_layout_texts,
    transform_xref_texts,
)
from backend.services.utils import (
    _정리문자열, _clean_text_from_headers, _clean_title_only,
    _extract_drawing_number, _도면번호_세척,
    _extract_dong_from_title, _extract_group_from_title,
    _extract_scale_smart, _spatial_reconstruct_num_str,
    _뷰_축척_타입_패턴, _축척_텍스트_정리,
)

logger = logging.getLogger("AutoDWG")


def _extract_view_symbols(
    layout,
    ix: float, iy: float,
    xscale: float, yscale: float,
    base_w: float, base_h: float,
    view_roi: list,
    rot_deg: float
) -> List[dict]:
    """view_symbol_roi 안의 원+선 제목 기호에서 뷰 도면명과 축척을 추출.

    양식: 원의 중심을 수평 LINE이 관통하며 오른쪽으로 뻗고,
          선 위 = 도면명(한글 포함), 선 아래 = 축척(S:A3=1/200 형식).
    수평 LINE이 원을 통과하지 않는 원은 장식용으로 간주하여 무시한다.
    """
    rad = math.radians(-rot_deg)
    cos_v, sin_v = math.cos(rad), math.sin(rad)

    def _unrot(tx, ty):
        dx, dy = tx - ix, ty - iy
        return ix + dx * cos_v - dy * sin_v, iy + dx * sin_v + dy * cos_v

    def _pt_seg_dist(px, py, sx, sy, ex, ey):
        """점 (px,py)에서 선분까지의 최단 거리."""
        dx, dy = ex - sx, ey - sy
        len_sq = dx * dx + dy * dy
        if len_sq == 0:
            return math.hypot(px - sx, py - sy)
        t = max(0.0, min(1.0, ((px - sx) * dx + (py - sy) * dy) / len_sq))
        return math.hypot(px - (sx + t * dx), py - (sy + t * dy))

    x_min = ix + base_w * xscale * view_roi[0]
    x_max = ix + base_w * xscale * view_roi[1]
    y_min = iy + base_h * yscale * view_roi[2]
    y_max = iy + base_h * yscale * view_roi[3]

    def _in_roi(tx, ty):
        ux, uy = _unrot(float(tx), float(ty))
        return x_min <= ux <= x_max and y_min <= uy <= y_max

    # view_symbol_roi 박스 안의 TEXT/MTEXT만 수집
    all_texts = []
    for ent in layout.query("TEXT MTEXT"):
        try:
            tx2, ty2 = float(ent.dxf.insert.x), float(ent.dxf.insert.y)
            if not _in_roi(tx2, ty2):
                continue
            txt2 = _정리문자열(ent.dxf.text if ent.dxftype() == "TEXT" else ent.plain_text())
            if txt2:
                all_texts.append((tx2, ty2, txt2))
        except Exception:
            pass

    # INSERT 블록 내부 TEXT/MTEXT도 수집 (뷰심볼이 블록으로 정의된 경우)
    try:
        doc = layout.doc
        for ins in layout.query("INSERT"):
            try:
                ip = ins.dxf.insert
                ipx, ipy = float(ip.x), float(ip.y)
                ixs = float(ins.dxf.get('xscale', 1.0) or 1.0)
                iys = float(ins.dxf.get('yscale', 1.0) or 1.0)
                ir  = math.radians(float(ins.dxf.get('rotation', 0.0) or 0.0))
                ic, is_ = math.cos(ir), math.sin(ir)
                blk = doc.blocks.get(ins.dxf.name)
                if blk is None:
                    continue
                for sub in blk:
                    if sub.dxftype() not in ("TEXT", "MTEXT"):
                        continue
                    try:
                        lx = float(sub.dxf.insert.x) * ixs
                        ly = float(sub.dxf.insert.y) * iys
                        wx = ipx + lx * ic - ly * is_
                        wy = ipy + lx * is_ + ly * ic
                        if not _in_roi(wx, wy):
                            continue
                        stxt = _정리문자열(sub.dxf.text if sub.dxftype() == "TEXT" else sub.plain_text())
                        if stxt:
                            all_texts.append((wx, wy, stxt))
                    except Exception:
                        pass
            except Exception:
                pass
    except Exception:
        pass

    # LINE 엔티티 수집
    all_lines = []
    for ent in layout.query("LINE"):
        try:
            sx, sy = float(ent.dxf.start.x), float(ent.dxf.start.y)
            ex, ey = float(ent.dxf.end.x), float(ent.dxf.end.y)
            all_lines.append((sx, sy, ex, ey))
        except Exception:
            pass

    symbols, seen = [], set()
    for ent in layout.query("CIRCLE"):
        try:
            cx, cy = float(ent.dxf.center.x), float(ent.dxf.center.y)
            r = float(ent.dxf.radius)
        except Exception:
            continue
        if r <= 0:
            continue
        ucx, ucy = _unrot(cx, cy)
        if not (x_min <= ucx <= x_max and y_min <= ucy <= y_max):
            continue
        key = (round(cx, 1), round(cy, 1))
        if key in seen:
            continue
        seen.add(key)

        # 수평 LINE 탐색: 원 중심을 관통하며 오른쪽으로 비대칭으로 뻗은 선
        far_right_x = None
        for sx, sy, ex, ey in all_lines:
            dx_l, dy_l = ex - sx, ey - sy
            length = math.hypot(dx_l, dy_l)
            if length < r * 0.3:
                continue
            if abs(dy_l / length) > math.sin(math.radians(30)):
                continue
            if _pt_seg_dist(cx, cy, sx, sy, ex, ey) > r * 1.5:
                continue
            right_x = max(sx, ex)
            left_x  = min(sx, ex)
            right_ext = right_x - cx
            left_ext  = max(0.0, cx - left_x)
            if right_ext < r * 2:
                continue
            # 뷰심볼 선은 왼쪽보다 오른쪽이 2배 이상 길어야 함 (구조 십자선 제외)
            if left_ext > 0 and right_ext < left_ext * 2:
                continue
            if far_right_x is None or right_x > far_right_x:
                far_right_x = right_x

        if far_right_x is None:
            continue  # 뷰심볼 형태의 선 없음 → 건너뜀

        line_y = cy

        # 도면명: view_roi 박스 안, line_y 위쪽, 한글 포함 → 원 중심으로부터 2D 거리 가장 가까운 것
        title_cands = []
        for tx, ty, txt in all_texts:
            if ty <= line_y:
                continue
            if not re.search(r'[가-힣]', txt) or len(txt.replace(' ', '')) < 3:
                continue
            title_cands.append((math.hypot(tx - cx, ty - line_y), txt))
        title_text = _정리문자열(min(title_cands, key=lambda t: t[0])[1]) if title_cands else ""

        # 축척: line_y 아래쪽, 패턴 매칭 → 원 중심으로부터 2D 거리 가장 가까운 것
        scale_cands = []
        for tx, ty, txt in all_texts:
            if ty >= line_y:
                continue
            for m in _뷰_축척_타입_패턴.finditer(txt):
                scale_cands.append((math.hypot(tx - cx, line_y - ty), m.group(1).upper(), _축척_텍스트_정리(m.group(2))))
        a1_cands = [(d, v) for d, t, v in scale_cands if t == "A1"]
        a3_cands = [(d, v) for d, t, v in scale_cands if t == "A3"]
        scale_a1 = min(a1_cands, key=lambda t: t[0])[1] if a1_cands else ""
        scale_a3 = min(a3_cands, key=lambda t: t[0])[1] if a3_cands else ""

        # 도면명과 축척 둘 다 있어야 유효한 뷰심볼
        if title_text and (scale_a1 or scale_a3):
            symbols.append({'뷰_도면명': title_text, '뷰_A1축척': scale_a1, '뷰_A3축척': scale_a3,
                            '_cx': round(cx, 1), '_cy': round(cy, 1)})

    # ── ATTRIB 기반 뷰심볼 처리 ─────────────────────────────────────────────
    try:
        _doc = layout.doc
        for ins in layout.query("INSERT"):
            try:
                attrib_list = list(ins.attribs)
                if not attrib_list:
                    continue
                ipx = float(ins.dxf.insert.x)
                ipy = float(ins.dxf.insert.y)
                uipx, uipy = _unrot(ipx, ipy)
                if not (x_min <= uipx <= x_max and y_min <= uipy <= y_max):
                    continue
                _blk = _doc.blocks.get(ins.dxf.name)
                if _blk is None:
                    continue
                ixs2 = float(ins.dxf.get('xscale', 1.0) or 1.0)
                iys2 = float(ins.dxf.get('yscale', 1.0) or 1.0)
                ir2  = math.radians(float(ins.dxf.get('rotation', 0.0) or 0.0))
                ic2, is2 = math.cos(ir2), math.sin(ir2)
                circle_wcy = None
                for sub in _blk:
                    if sub.dxftype() == "CIRCLE":
                        lx2 = float(sub.dxf.center.x) * ixs2
                        ly2 = float(sub.dxf.center.y) * iys2
                        circle_wcy = ipy + lx2 * is2 + ly2 * ic2
                        break
                if circle_wcy is None:
                    continue
                line_y2 = circle_wcy
                key = (round(ipx, 1), round(ipy, 1))
                if key in seen:
                    continue
                title_cands2, scale_cands2 = [], []
                for attrib in attrib_list:
                    try:
                        aty = float(attrib.dxf.insert.y)
                        atxt = _정리문자열(attrib.dxf.text)
                        if not atxt:
                            continue
                        if aty > line_y2:
                            if re.search(r'[가-힣]', atxt) and len(atxt.replace(' ', '')) >= 3:
                                title_cands2.append((aty - line_y2, atxt))
                        else:
                            for m in _뷰_축척_타입_패턴.finditer(atxt):
                                scale_cands2.append((line_y2 - aty, m.group(1).upper(), _축척_텍스트_정리(m.group(2))))
                    except Exception:
                        pass
                title_text2 = _정리문자열(min(title_cands2, key=lambda t: t[0])[1]) if title_cands2 else ""
                a1_cands2 = [(d, v) for d, t, v in scale_cands2 if t == "A1"]
                a3_cands2 = [(d, v) for d, t, v in scale_cands2 if t == "A3"]
                scale_a1_2 = min(a1_cands2, key=lambda t: t[0])[1] if a1_cands2 else ""
                scale_a3_2 = min(a3_cands2, key=lambda t: t[0])[1] if a3_cands2 else ""
                if title_text2 and (scale_a1_2 or scale_a3_2):
                    seen.add(key)
                    symbols.append({'뷰_도면명': title_text2, '뷰_A1축척': scale_a1_2, '뷰_A3축척': scale_a3_2,
                                    '_cx': round(ipx, 1), '_cy': round(ipy, 1)})
            except Exception:
                pass
    except Exception:
        pass

    return symbols


class EzdxfExtractor(BaseExtractor):
    """ezdxf + ODA File Converter 기반 추출 엔진."""

    def extract_title_block(self, dxf_path: str, roi_config: dict) -> dict:
        """단일 DXF 파일에서 도곽 정보를 추출한다.

        dwg_processor.py의 _process_single_dwg에서 직접 호출한다.
        실제 멀티파일 처리는 dwg_processor가 담당하므로,
        이 메서드는 파일 1개 × 도곽 1개 단위로 동작한다.
        """
        path = Path(dxf_path)
        roi_cfg = roi_config
        base_w = roi_cfg.get('base_w', 594.0)
        base_h = roi_cfg.get('base_h', 420.0)
        view_roi = roi_cfg.get('view_symbol_roi')

        result = {
            "도면번호": "",
            "도면명":   "",
            "구분":     "",
            "축척_A1": "X",
            "축척_A3": "X",
            "뷰심볼":  [],
        }

        try:
            doc = load_cad(path)
            for layout in doc.layouts:
                # 도곽 블록 탐색 (블록명은 roi_config에서 전달받지 않으므로
                # dwg_processor가 block_name을 별도 인자로 넘겨 처리)
                pass  # 실제 처리는 dwg_processor._process_single_dwg가 담당
        except Exception as e:
            logger.error("EzdxfExtractor.extract_title_block 오류: %s", e)

        return result
