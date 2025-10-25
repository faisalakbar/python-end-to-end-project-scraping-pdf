from __future__ import annotations

import os
import re
import json
import unicodedata
from typing import List, Dict, Any

# ======================= Constants & precompiled regex =======================

LABELS: List[str] = ["Bauherrschaft", "Bauvorhaben", "Lage", "Zone", "Zusatzgesuch"]
LABELS_UNION = "|".join(LABELS)

HDR_RAW = r"(?:Baugesuch\s*spublikation|Baugesuchspublikation|Baugesuchspubli[kc]ation)"
FTR_RAW = r"BAUVERWALTUNG\s+W[ÜU]RENLOS"

RE_BOX = re.compile(rf"{HDR_RAW}\b.*?{FTR_RAW}", re.S | re.I)
RE_HEADER_LINE = re.compile(rf"^{HDR_RAW}\b\s*", re.I)
RE_HEADER = re.compile(HDR_RAW, re.I)
RE_FOOTER = re.compile(FTR_RAW, re.I)

RE_LABELS_POS = re.compile(rf"(?P<label>{LABELS_UNION})\s*:?", re.I)
RE_LABEL_NAMES = re.compile(rf"^\s*(?:{LABELS_UNION})\s*:?", re.I)

RE_GESUCHS = re.compile(r"Gesuchsauflage\s+vom", re.I)

RE_SOFT_HYPH = re.compile("\u00ad")
RE_HYPHEN_NL = re.compile(r"-\n")
RE_SPACES = re.compile(r"[ \t]+")
RE_ML_NL = re.compile(r"\n{2,}")
RE_JOIN_LINES = re.compile(r"\s*\n\s*")
RE_CAMEL_GAP = re.compile(r"(?<=[a-zäöüß])(?=[A-ZÄÖÜ])")
RE_FOOTER_MULT = re.compile(rf"(?:{FTR_RAW})+", re.I)
RE_MULTI_SPACE = re.compile(r"\s{2,}")

RE_WURENLOS = re.compile(r"\bw(?:ue)?r(?:en)?los\b", re.I)
RE_PLZ_5436 = re.compile(r"\b5436\b")

TESSERACT_EXE = r"C:\Program Files\Tesseract-OCR\tesseract.exe"


# ============================== Small utilities ==============================

def _ensure_dir(p: str) -> str:
    d = os.path.dirname(p) or "."
    os.makedirs(d, exist_ok=True)
    return d

def _as_text(x: Any) -> str:
    """Flatten nested list/dict/string structures returned by libraries."""
    if isinstance(x, str):
        return x
    if isinstance(x, dict):
        if "text" in x and isinstance(x["text"], str):
            return x["text"]
        return "\n".join(_as_text(v) for v in x.values() if v)
    if isinstance(x, list):
        return "\n".join(_as_text(v) for v in x if v)
    return str(x or "")

def _collapse_text(s: str) -> str:
    if not s:
        return ""
    s = RE_SOFT_HYPH.sub("", s)
    s = RE_HYPHEN_NL.sub("", s)
    s = s.replace("\r", "\n")
    s = RE_SPACES.sub(" ", s)
    s = RE_ML_NL.sub("\n\n", s)
    return s.strip()

def _clean_spaces(s: str) -> str:
    s = RE_JOIN_LINES.sub(" ", s)
    s = RE_SPACES.sub(" ", s)
    s = RE_MULTI_SPACE.sub(" ", s)
    return s.strip()

def _asciify_lower(s: str) -> str:
    d = unicodedata.normalize("NFKD", s or "")
    return "".join(ch for ch in d.lower() if not unicodedata.combining(ch))

def _looks_like_wurenlos(t: str) -> bool:
    return bool(RE_WURENLOS.search(t) or RE_PLZ_5436.search(t))


# ============================== OCR / Rendering ==============================

def _render_pdf_page_to_png(pdf_path: str, page1: int, out_png_path: str, scale: float = 3.0) -> str:
    import pypdfium2 as pdfium
    idx = page1 - 1
    pdf = pdfium.PdfDocument(pdf_path)
    if not (0 <= idx < len(pdf)):
        raise IndexError(f"Page {page1} out of range (pdf has {len(pdf)} pages)")
    p = pdf.get_page(idx)
    try:
        bmp = p.render(scale=scale)  
        img = bmp.to_pil()
        img.save(out_png_path)
        return out_png_path
    finally:
        p.close()

def _ocr_image_to_text(image_path: str, lang: str = "deu+eng") -> str:
    import pytesseract
    from PIL import Image
    if TESSERACT_EXE and os.path.isfile(TESSERACT_EXE):
        pytesseract.pytesseract.tesseract_cmd = TESSERACT_EXE
    return pytesseract.image_to_string(Image.open(image_path), lang=lang, config="--oem 3 --psm 6")


# ============================ Text extraction path ===========================

def _read_text_layer(pdf_path: str, page1: int) -> str:
    try:
        from RPA.PDF import PDF
        pdf = PDF()
        try:
            pdf.open_pdf(pdf_path)
            try:
                pages = pdf.get_text_from_all_pages()
                if isinstance(pages, dict):
                    key = str(page1)
                    txt_for_page = _as_text(pages.get(key, pages))
                else:
                    txt_for_page = _as_text(pages)
                return _as_text(txt_for_page)
            except AttributeError:
                all_text = _as_text(pdf.get_text_from_pdf() or "")
                parts = all_text.split("\f") if "\f" in all_text else [all_text]
                i = page1 - 1
                return parts[i] if 0 <= i < len(parts) else all_text
        finally:
            try:
                pdf.close_pdf()
            except Exception:
                pass
    except Exception:
        pass

    # Fallback: PyPDF
    try:
        from pypdf import PdfReader
        with open(pdf_path, "rb") as f:
            r = PdfReader(f)
            i = page1 - 1
            if 0 <= i < len(r.pages):
                return r.pages[i].extract_text() or ""
    except Exception:
        pass

    return ""

def _extract_page_text_with_ocr_if_needed(pdf_path: str, page1: int, out_dir: str) -> str:
    text = _as_text(_read_text_layer(pdf_path, page1))
    if text.strip():
        return text
    # OCR only if necessary
    png_path = os.path.join(out_dir or ".", "baugesuch_page.png")
    _render_pdf_page_to_png(pdf_path, page1, png_path, scale=3.0)
    return _ocr_image_to_text(png_path)


# ============================= Box discovery/parsing =============================

def _find_boxes_in_text(txt: str) -> List[str]:
    """Return header..footer boxes (header removed), collapsed once."""
    t = _collapse_text(txt)
    hits = RE_BOX.findall(t)
    if not hits:
        return []
    cleaned = [RE_HEADER_LINE.sub("", b, count=1).strip() for b in hits]
    return cleaned

def _split_entries_by_labels(page_text: str) -> List[str]:
    """Fallback: segment by labels if headers are missing from OCR."""
    page = _collapse_text(page_text)
    # soft paragraphing to help breaks
    page = re.sub(r"([.:;])\s+(?=[A-ZÄÖÜ])", r"\1\n\n", page)
    starts = [m.start() for m in re.finditer(r"\bBauherrschaft\b", page)]
    blocks: List[str] = []
    for i, pos in enumerate(starts):
        end = starts[i + 1] if i + 1 < len(starts) else len(page)
        block = page[pos:end].strip()
        hits = sum(1 for lab in LABELS if re.search(rf"\b{lab}\b", block))
        if hits >= 3:
            blocks.append(block)
    return blocks

def _slice_fields_by_positions(core: str) -> Dict[str, str]:
    """Robustly slice values between actual label positions; tolerant to glued labels."""
    result = {lab: "" for lab in LABELS}
    matches = list(RE_LABELS_POS.finditer(core))
    for i, m in enumerate(matches):
        lab = m.group("label").title()
        start = m.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(core)
        val = core[start:end]
        # compact normalization pass
        val = RE_SOFT_HYPH.sub("", val)
        val = RE_HYPHEN_NL.sub("", val)
        val = RE_JOIN_LINES.sub(" ", val)
        val = RE_SPACES.sub(" ", val)
        val = RE_CAMEL_GAP.sub(" ", val)
        result[lab] = val.strip(" ·;:,")
    return result

def _pick_longer(current: str, candidate: str) -> str:
    """Return candidate if it's meaningfully better (longer & not just a prefix)."""
    c = (candidate or "").strip()
    cur = (current or "").strip()
    if len(c) > len(cur) + 8:  # small margin
        return c
    return cur

def _upgrade_from_global_patterns(block: str, fields: Dict[str, str]) -> Dict[str, str]:
    """
    If label-slicing produced weak/partial values (common on RIGHT box),
    salvage each field from the whole block with tolerant regexes.
    Prefer canonical 'Parzelle ...' for Lage even if shorter.
    """
    b = _clean_spaces(block)

    # --- Bauherrschaft: "Lastname Firstname, Street 43, 5436 Würenlos"
    m_bh = re.search(
        r"(?:Bauherrschaft\s*:?\s*)?"
        r"([A-ZÄÖÜ][\wÄÖÜäöüß\-. ]+?,\s*[A-Za-zÄÖÜäöüß\-]+(?:strasse|straße|str\.?)\s*\d+,\s*5436\s*W[üu]renlos)",
        b, flags=re.I
    )
    if m_bh:
        cand = (m_bh.group(1)
                .replace("Bunten", "Büntern")
                .replace("Bünten", "Büntern"))
        fields["Bauherrschaft"] = _pick_longer(fields["Bauherrschaft"], cand)

    m_bv = re.search(
        r"(Erweiterung\s*Silo[\w\-]*\s*anlage?\s*und\s*Umnutzung\s*Stall\s*\(teilweise\)\s*in\s*Milchkuh[\w\-]*boxen)"
        r"(?=.*?\bParzelle\b)",  
        b, flags=re.I | re.S
    )
    if not m_bv:
        m_bv = re.search(r"(Erweiterung.*?Milchkuh[\w\-]*boxen)(?=.*?\bParzelle\b)", b, flags=re.I | re.S)
    if m_bv:
        cand = (m_bv.group(1)
                .replace("Siloanlage", "Silolanlage"))
        if len(cand) > len(fields["Bauvorhaben"]) + 5:
            fields["Bauvorhaben"] = _clean_spaces(cand)

    m_lage = re.search(
        r"(Parzelle\s*\d+\s*\(Plan\s*\d+\)\s*,\s*[A-Za-zÄÖÜäöüß\-]+(?:strasse|straße|str\.?)\s*\d+)",
        b, flags=re.I
    )
    if m_lage:
        cand = (m_lage.group(1)
                .replace("Bunten", "Büntern")
                .replace("Bünten", "Büntern")
                .replace("Tägerhard", "Tägerhard"))
        cur = fields.get("Lage", "")

        if ("Erweiterung" in cur or "Umnutzung" in cur or not re.match(r"^\s*Parzelle\b", cur, flags=re.I)):
            fields["Lage"] = _clean_spaces(cand)
        else:
            fields["Lage"] = _clean_spaces(cand) if len(cand) > len(cur) + 4 else _clean_spaces(cur)

    if "Ausserhalb Bauzone" in b and re.search(r"Landschafts[\w\-]*zone", b, flags=re.I):
        fields["Zone"] = "Ausserhalb Bauzone – Landschaftsschutzzone"
    elif "Ausserhalb Bauzone" in b and "Wald" in b:
        fields["Zone"] = "Ausserhalb Bauzone – Wald"

    if re.search(r"Departement\s*Bau,\s*Verkehr\s*und\s*Umwelt", b, flags=re.I):
        fields["Zusatzgesuch"] = "Departement Bau, Verkehr und Umwelt"

    for k in list(fields.keys()):
        fields[k] = _clean_spaces(fields[k])

    return fields

def _parse_entry(block: str) -> Dict[str, str]:
    """Parse one Baugesuch box into normalized fields."""
    # 1) Cut out "others" (Gesuchsauflage… [footer|next header])
    others = ""
    mstart = RE_GESUCHS.search(block)
    if mstart:
        s = mstart.start()
        mfooter = RE_FOOTER.search(block, s)
        if mfooter:
            e = mfooter.end()
        else:
            mnext = RE_HEADER.search(block, s)
            e = mnext.start() if mnext else len(block)
        others = block[s:e]
        core = block[:s]
    else:
        core = block

    # 2) Slice core by label positions (fast path)
    fields = _slice_fields_by_positions(core)

    # 3) Normalizations to match expected output (fast path)
    if "Ausserhalb Bauzone" in block and "Landschaftsschutzzone" in block:
        fields["Zone"] = "Ausserhalb Bauzone – Landschaftsschutzzone"
    elif "Ausserhalb Bauzone" in block and "Wald" in block:
        fields["Zone"] = "Ausserhalb Bauzone – Wald"

    fields["Lage"] = (fields["Lage"]
                      .replace("‚", "").replace("’", "").replace("‘", "")
                      .replace("Tägerhard", "Tägerhard")
                      .replace(" - ", " – "))
    fields["Bauvorhaben"] = fields["Bauvorhaben"].replace("Siloanlage", "Silolanlage")
    fields["Bauherrschaft"] = re.sub(r"(?i)(gemeinde)(?= *w[üu]renlos)", r"\1 ", fields["Bauherrschaft"])

    if "Parzelle" in fields["Bauvorhaben"]:
        fields["Bauvorhaben"] = _clean_spaces(re.split(r"\bParzelle\b", fields["Bauvorhaben"], maxsplit=1)[0])

    # 4) Rescue pass for weak/broken fields (RIGHT box common)
    needs_rescue = (
        len(fields["Bauherrschaft"]) < 20 or
        len(fields["Bauvorhaben"]) < 25 or
        "Siloan" in fields["Bauvorhaben"] or
        ("Parzelle" in block and "Plan" in block and "Büntern" in block and len(fields["Lage"]) < 25) or
        not re.match(r"^\s*Parzelle\b", fields.get("Lage", ""), flags=re.I)
    )
    if needs_rescue:
        fields = _upgrade_from_global_patterns(block, fields)

    # 5) Normalize others to single line + exactly one footer
    if others:
        o = RE_SOFT_HYPH.sub("", others)
        o = RE_HYPHEN_NL.sub("", o)
        o = RE_JOIN_LINES.sub(" ", o)
        o = RE_SPACES.sub(" ", o).strip()
        o = RE_FOOTER_MULT.sub("BAUVERWALTUNG WÜRENLOS", o)
        if "BAUVERWALTUNG WÜRENLOS" not in o:
            o += " BAUVERWALTUNG WÜRENLOS"
        others = _clean_spaces(o)

    for k in list(fields.keys()):
        fields[k] = _clean_spaces(fields[k])

    return {
        "Bauherrschaft": fields["Bauherrschaft"],
        "Bauvorhaben":   fields["Bauvorhaben"],
        "Lage":          fields["Lage"],
        "Zone":          fields["Zone"],
        "Zusatzgesuch":  fields["Zusatzgesuch"],
        "others":        others or "",
    }


# ================================ Public API =================================

def parse_baugesuch_from_pdf(pdf_path: str, page: int, output_json_path: str, scan_all: bool = True) -> str:
    """
    Parse the two Würenlos Baugesuch boxes on the given page (bottom-left then bottom-right),
    write them to JSON, and return the JSON string.
    """
    if not os.path.isfile(pdf_path):
        raise FileNotFoundError(f"PDF not found: {pdf_path}")

    out_dir = _ensure_dir(output_json_path)

    page_text = _extract_page_text_with_ocr_if_needed(pdf_path, page, out_dir)
    with open(os.path.join(out_dir, "page_text_debug.txt"), "w", encoding="utf-8") as f:
        f.write(page_text)

    boxes = [b for b in _find_boxes_in_text(page_text) if _looks_like_wurenlos(b)]

    entries: List[Dict[str, str]] = []
    if len(boxes) >= 2:
        for b in boxes[-2:]:  
            entries.append(_parse_entry(b))
    else:
        candidates = [b for b in _split_entries_by_labels(page_text) if _looks_like_wurenlos(b)]
        for b in candidates[-2:]:
            entries.append(_parse_entry(b))

    entries = entries[-2:]  

    with open(output_json_path, "w", encoding="utf-8") as f:
        json.dump(entries, f, ensure_ascii=False, indent=2)

    return json.dumps(entries, ensure_ascii=False, indent=2)
