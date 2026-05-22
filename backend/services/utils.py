"""
services/utils.py — [섹션 1] 공통 유틸리티
app.py 섹션 1의 정규식 패턴, 헤더 노이즈 제거, 텍스트 정리 함수를 그대로 분리.
로직은 수정하지 않고 import 경로만 변경.
"""
from __future__ import annotations
import re
from typing import List, Optional, Tuple

# ── 정규식 패턴 ──────────────────────────────────────────────────────────────
_도면번호_패턴 = re.compile(
    r"(?<![가-힣A-Za-z0-9])([A-ZΑ-Ω\.가-힣][A-Z0-9Α-Ω\.가-힣]{0,4})"
    r"[\s\-_~–—−]*(\d{1,5}(?:[\s\-_~–—−]+\d{1,5}(?![가-힣㎡,]))*[A-Za-z]*|TOE)"
    r"(?!\d|[A-Za-z]|[가-힣])"
)
_축척_패턴         = re.compile(r"(1\s?[/:,]\s?([\d,]+)|NONE|N/A)", re.I)
_뷰_축척_타입_패턴 = re.compile(r'\b(A[13])\s*[-=:]\s*(1\s*/\s*[\d,]+|\d{2,5})', re.I)
_동_패턴           = re.compile(r"^([0-9A-Za-z]+동|[가-힣]{1,3}동)(?=\s|$)")

# ── 헤더 노이즈 제거 목록 ────────────────────────────────────────────────────
GLOBAL_IGNORE_HEADERS = [
    "SUBJECT TITLE", "SUBJECT", "PROJECT TITLE", "PROJECT",
    "DRAWING TITLE", "DRAWING NO.", "DRAWING NO", "DWG.NO.", "DWG. NO.", "DWG.NO", "DWG NO.", "DWG NO", "TITLE",
    "SHEET NO.", "SHEET NO", "SHT NO.", "SHT NO", "SHEET",
    "도면번호", "도연번호", "일련번호", "연번", "NO", "NO.", "도면명", "도면명칭", "축척(A1)", "축척(A3)", "축척(A0)",
    "SCALE(A1)", "SCALE(A3)", "SCALE(A0)", "축척(1:)", "축척(1/)", "SCALE(1:)", "SCALE(1/)", "(1:)", "(1/)",
    "축척", "축적", "SCALE", "비고", "REMARK", "REMARKS", "사업승인", "착공", "견적", "사용승인", "1:1"
]

CATEGORY_KEYWORDS = ["공통사항", "일반사항", "건축도면", "구조도면", "기계도면", "전기도면", "토목도면", "조경도면", "소방도면", "부분상세도"]


def _clean_text_from_headers(txt: str) -> str:
    """헤더 키워드를 텍스트에서 제거한다."""
    clean = txt
    for h in sorted(GLOBAL_IGNORE_HEADERS, key=len, reverse=True):
        clean = re.compile(re.escape(h), re.IGNORECASE).sub(" ", clean)
    clean = re.sub(r"\s+", " ", clean).strip()
    return re.sub(r"^[-_,\s]+|[-_,\s]+$", "", clean)


def _extract_dong_from_title(title: str) -> str:
    """도면명 앞에서 동 이름을 추출한다."""
    m = _동_패턴.match(title.strip())
    return m.group(1) if m else ""


def _extract_group_from_title(title: str) -> str:
    """동/그룹 정보 추출. 동을 먼저 제거한 후 남은 텍스트의 첫 토큰이 그룹인지 판단."""
    title = title.strip()
    # 동을 먼저 제거
    m = _동_패턴.match(title)
    if m:
        title = title[len(m.group(1)):].strip()
    if not title:
        return ""
    first_token = title.split(None, 1)[0]
    # 숫자·영문대문자·특수문자가 섞이면 도면명으로 시작한 것 → 그룹 없음
    if re.search(r"\d|[A-Z]|[#\-_\(\)\[\]]", first_token):
        return ""
    # 순수 한글만 → 그룹
    if re.match(r"^[가-힣]+$", first_token):
        return first_token
    return ""


def _도면번호_세척(raw_s: str) -> str:
    """도면번호 문자열 정규화 (CAD 한 글자 분리, 특수문자 치환 등)."""
    if not raw_s:
        return ""
    suffix_m = re.search(r"[a-z]+$", raw_s.strip())
    orig_suffix = suffix_m.group(0) if suffix_m else ""
    s = raw_s.strip().upper().replace("Λ", "A").replace("Δ", "A").replace("TOE", "108")
    if s.startswith("."):
        s = "AA" + s[1:]
    s = re.sub(r"\s*([-_~])\s*", r"\1", s)
    s = re.sub(r"[-_~]{2,}", "-", re.sub(r"\s+", " ", s))
    # CAD에서 한 글자씩 분리 저장된 경우 합치기
    segs = re.split(r"([-_~])", s)
    merged = []
    for i, seg in enumerate(segs):
        if i % 2 == 1:
            merged.append(seg)
        else:
            parts = [t for t in seg.split(" ") if t]
            if parts and all(len(t) == 1 for t in parts):
                merged.append("".join(parts))
            elif parts:
                buf, rp = [], []
                for p in parts:
                    if len(p) == 1:
                        buf.append(p)
                    else:
                        if buf:
                            rp.append("".join(buf))
                            buf = []
                        rp.append(p)
                if buf:
                    rp.append("".join(buf))
                merged.append(" ".join(rp))
            else:
                merged.append(seg)
    s = "".join(merged)
    # 남은 공백 → 대시 (그래픽 대시가 텍스트로 저장되지 않은 자리)
    s = re.sub(r"(?<=[A-Za-z0-9]) (?=[A-Za-z0-9])", "-", s)
    if orig_suffix:
        s = s[:-len(orig_suffix)] + orig_suffix
    return s


def _spatial_reconstruct_num_str(texts: list) -> str:
    """공간 좌표 기반으로 번호 텍스트를 결합. 단일 문자 간격이 임계값을 넘으면 '-' 삽입."""
    if not texts:
        return ""
    single_char_gaps = []
    for i in range(1, len(texts)):
        tx, _, txt_i, _ = texts[i]
        px, _, ptxt_i, _ = texts[i - 1]
        s, ps = txt_i.strip(), ptxt_i.strip()
        if (len(s) == 1 and len(ps) == 1
                and re.match(r"[0-9A-Za-z]", s)
                and re.match(r"[0-9A-Za-z]", ps)):
            single_char_gaps.append(tx - px)
    if len(single_char_gaps) >= 2:
        sorted_gaps = sorted(single_char_gaps)
        median_gap = sorted_gaps[len(sorted_gaps) // 2]
        gap_threshold = median_gap * 1.6
    elif single_char_gaps:
        avg_h = sum(t[3] for t in texts) / len(texts)
        gap_threshold = avg_h * 0.85
    else:
        gap_threshold = None
    tokens = []
    for i, t in enumerate(texts):
        tx, ty, txt_i, th = t
        stripped = txt_i.strip()
        if not stripped:
            continue
        if i > 0 and gap_threshold is not None:
            prev_tx, _, prev_txt_i, _ = texts[i - 1]
            ps = prev_txt_i.strip()
            if (len(ps) == 1 and len(stripped) == 1
                    and re.match(r"[0-9A-Za-z]", ps)
                    and re.match(r"[0-9A-Za-z]", stripped)
                    and (tx - prev_tx) > gap_threshold):
                tokens.append("-")
        tokens.append(stripped)
    return " ".join(tokens)


def _merge_title_char_runs(s: str) -> str:
    """공백으로 분리된 단일 문자 토큰을 병합 (CAD 한 글자씩 저장 복원)."""
    if not s:
        return ""
    result_parts = []
    run = []
    for tok in s.split(" "):
        if tok and len(tok) == 1:
            run.append(tok)
        else:
            if run:
                merged = "".join(run)
                if result_parts and (merged[0] in "-_~" or result_parts[-1][-1:] in "-_~"):
                    result_parts[-1] += merged
                else:
                    result_parts.append(merged)
                run = []
            if tok:
                result_parts.append(tok)
    if run:
        merged = "".join(run)
        if result_parts and (merged[0] in "-_~" or result_parts[-1][-1:] in "-_~"):
            result_parts[-1] += merged
        else:
            result_parts.append(merged)
    return " ".join(result_parts)


def _축척_텍스트_정리(txt: str) -> str:
    """축척 텍스트를 '1/N' 형식으로 정규화한다."""
    if not txt:
        return "X"
    u = txt.strip().upper()
    if "NONE" in u or "N/A" in u:
        return "NONE"
    m = _축척_패턴.search(u)
    if m and m.group(2):
        return f"1/{m.group(2).replace(',', '')}"
    plain = re.sub(r'[,\s]', '', u)
    if re.match(r'^\d+$', plain):
        return f"1/{plain}"
    return "X"


def _extract_drawing_number(text: str) -> Optional[str]:
    """텍스트에서 도면번호(AA-000-000 형식)를 추출한다."""
    for m in _도면번호_패턴.finditer(text):
        prefix = m.group(1)
        if m.group(0) in ["A1", "A3", "A0", "A2", "A4"]:
            continue
        exclude_words = [
            "상세", "일람", "배치", "전개", "마감", "계획", "조감", "구조", "코어", "지하", "옥상", "옥탑",
            "지붕", "주동", "단위", "세대", "내역", "관계", "형별", "부분", "창호", "가구", "조경", "토목",
            "기계", "전기", "범례", "개요", "표지", "도면", "시설", "센터", "주차장", "휴게소", "사무소",
            "경로당", "어린이집", "유치원", "도서관", "커뮤니티", "피트니스", "사우나", "골프", "문주", "경비실"
        ]
        if any(k in prefix for k in exclude_words):
            continue
        if prefix.endswith("도") or prefix.endswith("표") or prefix.endswith("층") or prefix.endswith("동"):
            continue
        if len(prefix) > 1 and all("가" <= c <= "힣" for c in prefix):
            continue
        result = m.group(0)
        result = re.sub(r'(?<=\d) [0-9]$', '', result)
        return result if result else None
    return None


def _정리문자열(txt: str) -> str:
    """연속 공백 제거 및 양쪽 공백 제거."""
    return re.sub(r"\s+", " ", (txt or "")).strip()


def _expand_title_keywords(title: str) -> set:
    """도면명에서 키워드 집합을 추출. 쉼표 축약형을 확장한다.
    예) '입,단면도' → {'입면도','단면도'}"""
    result = set()
    for word in title.strip().split():
        if ',' not in word:
            if word:
                result.add(word)
            continue
        parts = word.split(',')
        last = parts[-1]
        for part in parts[:-1]:
            result.add(part + last[len(part):] if len(part) < len(last) else part)
        result.add(last)
    return {w for w in result if w}


def _title_contains_view(block_title: str, view_title: str) -> bool:
    """뷰 심볼 도면명의 단어들이 도곽 도면명 안에 모두 포함되는지 확인."""
    if not view_title or not block_title:
        return False
    for bad in ('nan', 'x', 'none', ''):
        if view_title.lower().strip() == bad or block_title.lower().strip() == bad:
            return False
    # 뷰 도면명 끝 번호 제거: "입면도-1" → "입면도"
    view_stripped = re.sub(r'[\s\-_]+\d+\s*$', '', view_title.strip())
    block_words = _expand_title_keywords(block_title)
    view_words  = _expand_title_keywords(view_stripped)
    return bool(view_words) and view_words.issubset(block_words)


def _clean_title_only(title: str) -> str:
    """도면명에서 축척 표기 등 노이즈를 제거한다."""
    clean = re.sub(r"NONE|N/A|1\s?[/:,]\s?[\d,]+", " ", title, flags=re.I)
    clean = re.sub(r"(?:축척|SCALE)?\s*\(\s*1\s*[:/]\s*\)", " ", clean, flags=re.I)
    clean = re.sub(r"(?:축척|SCALE)\s*1\s*[:/]", " ", clean, flags=re.I)
    return _clean_text_from_headers(clean)


def _extract_scale_smart(
    cell_texts: List[Tuple[float, float, str, float]],
    header_a1_x: Optional[float] = None,
    header_a3_x: Optional[float] = None,
    is_list_table: bool = False
) -> Tuple[str, str]:
    """셀 텍스트 목록에서 A1/A3 축척을 추출한다."""
    texts_to_scan = []
    lone_numbers = []
    if not is_list_table:
        # 개별 도면 모드: 같은 Y 라인의 텍스트를 먼저 병합한다
        merged_texts = []
        if cell_texts:
            cell_texts_sorted = sorted(cell_texts, key=lambda t: (-t[1], t[0]))
            curr_line, curr_y = [], None
            for t in cell_texts_sorted:
                x, y, txt, h = t
                if curr_y is None:
                    curr_y = y
                    curr_line.append(t)
                elif abs(curr_y - y) <= max(h * 1.5, 1.0):
                    curr_line.append(t)
                else:
                    curr_line.sort(key=lambda item: item[0])
                    merged_texts.append((curr_line[0][0], curr_y, " ".join([item[2] for item in curr_line]), curr_line[0][3]))
                    curr_y = y
                    curr_line = [t]
            if curr_line:
                curr_line.sort(key=lambda item: item[0])
                merged_texts.append((curr_line[0][0], curr_y, " ".join([item[2] for item in curr_line]), curr_line[0][3]))
        texts_to_scan = merged_texts
    else:
        texts_to_scan = cell_texts

    a1_val, a3_val = "X", "X"
    scales, labels = [], {}
    for x, y, txt, h in texts_to_scan:
        u_txt = txt.upper()
        clean_txt = u_txt.replace(" ", "")
        m_a1 = re.search(r'A1.*?(1\s?[/:,]\s?[\d,]+|NONE|N/A)', clean_txt)
        if m_a1 and a1_val == "X":
            a1_val = _축척_텍스트_정리(m_a1.group(1))
        m_a3 = re.search(r'A3.*?(1\s?[/:,]\s?[\d,]+|NONE|N/A)', clean_txt)
        if m_a3 and a3_val == "X":
            a3_val = _축척_텍스트_정리(m_a3.group(1))
        if re.search(r'\bA1\b', u_txt):
            labels['A1'] = (x, y)
        if re.search(r'\bA3\b', u_txt):
            labels['A3'] = (x, y)
        for m in _축척_패턴.finditer(u_txt):
            val = _축척_텍스트_정리(m.group(0))
            if val != "X":
                scales.append((x, y, val))
        if not is_list_table and not _축척_패턴.search(u_txt):
            if re.search(r'^[\d,]+$', clean_txt):
                lone_numbers.append((x, y, f"1/{clean_txt.replace(',', '')}"))
            elif clean_txt in ["NONE", "N/A"]:
                lone_numbers.append((x, y, "NONE"))

    unique_scales, seen = [], set()
    for sx, sy, sval in scales + lone_numbers:
        if (sx, sy, sval) not in seen:
            seen.add((sx, sy, sval))
            unique_scales.append((sx, sy, sval))

    def dist(x1, y1, x2, y2):
        return ((x1 - x2) ** 2 + (y1 - y2) ** 2) ** 0.5

    pairings = []
    for sx, sy, sval in unique_scales:
        d_a1 = dist(sx, sy, labels['A1'][0], labels['A1'][1]) if 'A1' in labels else (abs(sx - header_a1_x) if header_a1_x is not None else float('inf'))
        d_a3 = dist(sx, sy, labels['A3'][0], labels['A3'][1]) if 'A3' in labels else (abs(sx - header_a3_x) if header_a3_x is not None else float('inf'))
        if d_a1 != float('inf') or d_a3 != float('inf'):
            if d_a1 <= d_a3:
                pairings.append((d_a1, sval, 'A1'))
            else:
                pairings.append((d_a3, sval, 'A3'))

    pairings.sort(key=lambda p: p[0])
    for _, sval, target in pairings:
        if target == 'A1' and a1_val == "X":
            a1_val = sval
        elif target == 'A3' and a3_val == "X":
            a3_val = sval

    if unique_scales:
        unique_scales.sort(key=lambda item: item[0])
        if a1_val == "X" and a3_val == "X":
            if len(unique_scales) >= 2:
                a1_val, a3_val = unique_scales[0][2], unique_scales[1][2]
            else:
                a1_val = unique_scales[0][2]
        elif a1_val == "X" and a3_val != "X":
            for _, _, sval in unique_scales:
                if sval != a3_val:
                    a1_val = sval
                    break
        elif a3_val == "X" and a1_val != "X":
            for _, _, sval in unique_scales:
                if sval != a1_val:
                    a3_val = sval
                    break
    return a1_val, a3_val
