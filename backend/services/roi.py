"""
services/roi.py — [섹션 2] ROI/ODA/도곽 탐색 엔진
app.py 섹션 2의 함수를 그대로 분리. 로직 수정 없음.
"""
from __future__ import annotations
import glob
import json
import logging
import math
import os
from pathlib import Path
from typing import List, Optional, Tuple

import ezdxf

from backend import config

logger = logging.getLogger("AutoDWG")


# ── ROI 설정 로드 ────────────────────────────────────────────────────────────

def load_roi_config(block_name: str) -> Optional[dict]:
    """블록명에 해당하는 ROI JSON을 CONFIG_DIR에서 로드한다.
    cp949 → utf-8 → euc-kr 순으로 인코딩을 시도한다."""
    config_path = config.CONFIG_DIR / f"{block_name}.json"
    if config_path.exists():
        for enc in ['cp949', 'utf-8', 'euc-kr']:
            try:
                with open(config_path, 'r', encoding=enc) as f:
                    return json.load(f)
            except Exception:
                continue
    return None


def list_roi_configs() -> List[str]:
    """CONFIG_DIR에 저장된 모든 블록명 목록을 반환한다."""
    return [p.stem for p in config.CONFIG_DIR.glob("*.json")]


# ── ODA File Converter 환경 설정 ──────────────────────────────────────────────

def setup_oda() -> str:
    """ODA File Converter 실행 파일 경로를 탐색하여 ezdxf에 등록한다.
    환경변수 ODA_EXEC_PATH가 있으면 우선 사용하고,
    없으면 Windows/Linux 기본 경로를 순서대로 탐색한다."""
    # 환경변수로 명시적으로 지정된 경우 바로 사용
    if config.ODA_EXEC_PATH and os.path.isfile(config.ODA_EXEC_PATH):
        found_path = config.ODA_EXEC_PATH
    else:
        found_path = ""
        # Windows 기본 경로
        search_roots = [
            r"C:\Program Files\ODA",
            r"C:\Program Files (x86)\ODA",
        ]
        # TODO: Linux(Docker) 환경에서 ODA 설치 후 실제 경로를 여기에 추가하거나
        #       ODA_EXEC_PATH 환경변수로 Dockerfile에서 주입한다.
        # 예시) "/opt/ODA/ODAFileConverter", "/usr/bin/ODAFileConverter"
        for root in search_roots:
            matches = glob.glob(os.path.join(root, "**", "ODAFileConverter.exe"), recursive=True)
            if matches:
                found_path = sorted(matches, reverse=True)[0]
                break

    if found_path:
        folder = os.path.dirname(found_path)
        if folder not in os.environ.get("PATH", ""):
            os.environ["PATH"] = folder + os.pathsep + os.environ.get("PATH", "")
        try:
            ezdxf.options.odafc_win_exec_path = found_path
        except AttributeError:
            try:
                ezdxf.options.set('odafc', 'win_exec_path', found_path)
            except Exception:
                pass
    return found_path


# ── CAD 파일 로드 ─────────────────────────────────────────────────────────────

def load_cad(path: Path):
    """DXF는 직접 읽고, DWG는 ODA를 통해 변환 후 읽는다."""
    if path.suffix.lower() == ".dxf":
        return ezdxf.readfile(str(path))
    setup_oda()
    from ezdxf.addons import odafc
    return odafc.readfile(str(path))


# ── 도곽 블록 탐색 ────────────────────────────────────────────────────────────

def find_도곽_blocks(layout, target_block: str) -> list:
    """도곽 INSERT를 탐색한다. 정확일치 우선, 없으면 부분일치 폴백."""
    target = target_block.strip().lower()
    if not target:
        return []
    all_inserts = list(layout.query("INSERT"))
    exact = [ins for ins in all_inserts if ins.dxf.name.strip().lower() == target]
    if exact:
        return exact
    partial = [ins for ins in all_inserts if target in ins.dxf.name.lower()]
    if partial:
        matched_names = sorted({ins.dxf.name for ins in partial})
        logger.warning(
            "[경고] '%s' 정확히 일치하는 도곽 없음 → 부분일치로 사용: %s",
            target_block, ", ".join(matched_names)
        )
    return partial


# ── 텍스트 엔티티 추출 ────────────────────────────────────────────────────────

def _get_safe_point(ent) -> Tuple[float, float]:
    """TEXT/ATTRIB의 삽입점을 안전하게 반환한다."""
    p = ent.dxf.insert
    if getattr(ent.dxf, "halign", 0) > 0 or getattr(ent.dxf, "valign", 0) > 0:
        ap = getattr(ent.dxf, "align_point", None)
        if ap and (round(ap[0], 2) != 0 or round(ap[1], 2) != 0):
            p = ap
    return float(p[0]), float(p[1])


def extract_text_entity(ent) -> List[Tuple[float, float, str, float]]:
    """단일 DXF 엔티티에서 (x, y, text, height) 튜플 목록을 추출한다."""
    from backend.services.utils import _정리문자열
    유형 = ent.dxftype()
    결과 = []
    try:
        if 유형 in ["TEXT", "ATTRIB"]:
            px, py = _get_safe_point(ent)
            txt = (ent.dxf.text or "").strip()
            if txt:
                결과.append((px, py, txt, float(getattr(ent.dxf, "height", 10.0))))
        elif 유형 == "MTEXT":
            h = getattr(ent.dxf, "char_height", 10.0)
            bx, by = float(ent.dxf.insert[0]), float(ent.dxf.insert[1])
            for i, line in enumerate(ent.plain_text().split('\n')):
                txt = line.strip()
                if txt:
                    결과.append((bx, by - (i * h * 1.5), txt, float(h)))
        elif 유형 == "ATTDEF":
            px, py = _get_safe_point(ent)
            txt = getattr(ent.dxf, 'tag', '').strip()
            if not txt:
                txt = getattr(ent.dxf, 'text', '').strip()
            if txt:
                결과.append((px, py, txt, float(getattr(ent.dxf, "height", 10.0))))
    except Exception as e:
        logger.debug("텍스트 엔티티 처리 건너뜀: %s", e)
    return 결과


def collect_layout_texts(layout) -> List[Tuple[float, float, str, float]]:
    """레이아웃 전체의 텍스트를 수집하여 중복 제거 후 반환한다."""
    from backend.services.utils import _정리문자열
    texts = []
    try:
        for ent in layout.query("TEXT MTEXT LINE LWPOLYLINE INSERT ATTDEF"):
            if ent.dxftype() in ["TEXT", "MTEXT", "LINE", "LWPOLYLINE", "ATTDEF"]:
                texts.extend(extract_text_entity(ent))
            elif ent.dxftype() == "INSERT":
                for att in getattr(ent, "attribs", []):
                    texts.extend(extract_text_entity(att))
                try:
                    for v_ent in ent.virtual_entities():
                        if v_ent.dxftype() in ["TEXT", "MTEXT", "LINE", "LWPOLYLINE", "ATTDEF"]:
                            texts.extend(extract_text_entity(v_ent))
                        elif v_ent.dxftype() == "INSERT":
                            for v_att in getattr(v_ent, "attribs", []):
                                texts.extend(extract_text_entity(v_att))
                except Exception as e:
                    logger.debug("가상 엔티티 처리 건너뜀: %s", e)
    except Exception as e:
        logger.debug("레이아웃 텍스트 수집 건너뜀: %s", e)

    seen, out = set(), []
    for x, y, txt, h in texts:
        clean = _정리문자열(txt)
        key = (round(x, 2), round(y, 2), clean)
        if key not in seen:
            seen.add(key)
            out.append((float(x), float(y), clean, float(h)))
    return out


def parse_xref_original(xref_path: str) -> List[Tuple[float, float, str, float]]:
    """XREF 원본 DWG를 스캔하여 고정 텍스트를 수집한다 (엑스레이 스캔)."""
    from backend.services.utils import _정리문자열
    logger.info("[XREF] 도곽 원본 스캔 중... (%s)", os.path.basename(xref_path))
    try:
        doc = load_cad(Path(xref_path))
        texts = []
        for ent in doc.modelspace().query("TEXT MTEXT INSERT ATTDEF"):
            if ent.dxftype() in ["TEXT", "MTEXT", "ATTDEF"]:
                texts.extend(extract_text_entity(ent))
            elif ent.dxftype() == "INSERT":
                for att in getattr(ent, "attribs", []):
                    texts.extend(extract_text_entity(att))
                try:
                    for v_ent in ent.virtual_entities():
                        if v_ent.dxftype() in ["TEXT", "MTEXT", "ATTDEF"]:
                            texts.extend(extract_text_entity(v_ent))
                except Exception as e:
                    logger.debug("XREF 가상 엔티티 처리 건너뜀: %s", e)
        seen, out = set(), []
        for x, y, txt, h in texts:
            clean = _정리문자열(txt)
            key = (round(x, 2), round(y, 2), clean)
            if key not in seen:
                seen.add(key)
                out.append((float(x), float(y), clean, float(h)))
        logger.info("  -> 엑스레이 스캔 성공! %d개의 고정 텍스트 암기 완료.", len(out))
        return out
    except Exception as e:
        logger.error("XREF 스캔 실패: %s", e)
        return []


def transform_xref_texts(
    xref_texts: List[Tuple[float, float, str, float]],
    ix: float, iy: float,
    xscale: float, yscale: float,
    rot_deg: float
) -> List[Tuple[float, float, str, float]]:
    """XREF 원본 텍스트를 현재 도면의 도곽 위치·스케일·회전에 맞게 변환한다."""
    transformed = []
    rad = math.radians(rot_deg)
    cos_val, sin_val = math.cos(rad), math.sin(rad)
    for x, y, txt, h in xref_texts:
        sx = x * xscale
        sy = y * yscale
        rx = sx * cos_val - sy * sin_val
        ry = sx * sin_val + sy * cos_val
        transformed.append((ix + rx, iy + ry, txt, h * yscale))
    return transformed
