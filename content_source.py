# -*- coding: utf-8 -*-
from __future__ import annotations

import html
import os
import re
import tempfile
import zlib
from html.parser import HTMLParser
from pathlib import Path
from typing import Any
from urllib.parse import urlparse
from urllib.request import Request, urlopen


MAX_SOURCE_CHARS = 24000
MAX_PDF_BYTES = 18_000_000


SOURCE_KIND_LABELS = {
    "auto": "Tự động",
    "news": "Báo",
    "story": "Truyện chữ",
    "comic": "Truyện tranh",
}


class _ReadableHTMLParser(HTMLParser):
    BLOCK_TAGS = {
        "article",
        "main",
        "section",
        "div",
        "p",
        "br",
        "li",
        "h1",
        "h2",
        "h3",
        "blockquote",
    }

    SKIP_TAGS = {
        "script",
        "style",
        "noscript",
        "svg",
        "canvas",
        "iframe",
        "nav",
        "footer",
        "header",
        "form",
        "button",
        "select",
        "option",
    }

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self._skip_depth = 0
        self._chunks: list[str] = []
        self.title = ""
        self._in_title = False

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        tag = str(tag or "").lower()
        if tag in self.SKIP_TAGS:
            self._skip_depth += 1
            return
        if tag == "title":
            self._in_title = True
            return
        if self._skip_depth:
            return
        if tag in self.BLOCK_TAGS:
            self._chunks.append("\n")

    def handle_endtag(self, tag: str) -> None:
        tag = str(tag or "").lower()
        if tag in self.SKIP_TAGS and self._skip_depth:
            self._skip_depth -= 1
            return
        if tag == "title":
            self._in_title = False
            return
        if self._skip_depth:
            return
        if tag in self.BLOCK_TAGS:
            self._chunks.append("\n")

    def handle_data(self, data: str) -> None:
        if not data:
            return
        text = str(data)
        if self._in_title:
            self.title += text
            return
        if self._skip_depth:
            return
        self._chunks.append(text)

    def readable_text(self) -> str:
        raw = "".join(self._chunks)
        return _clean_readable_text(raw)


def _clean_readable_text(raw: str) -> str:
    text = html.unescape(str(raw or ""))
    text = text.replace("\r", "\n")
    text = re.sub(r"[ \t\f\v]+", " ", text)
    text = re.sub(r"\n\s+", "\n", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    lines: list[str] = []
    seen: set[str] = set()
    for line in text.splitlines():
        clean = line.strip(" \t-•")
        if len(clean) < 2:
            continue
        key = re.sub(r"\s+", " ", clean).casefold()
        if key in seen:
            continue
        seen.add(key)
        lines.append(clean)
    return "\n".join(lines).strip()


def _detect_charset(headers: Any, raw: bytes) -> str:
    try:
        content_type = str(headers.get("Content-Type") or "")
    except Exception:
        content_type = ""
    match = re.search(r"charset=([A-Za-z0-9_.-]+)", content_type, re.IGNORECASE)
    if not match:
        head = raw[:4096].decode("ascii", errors="ignore")
        match = re.search(r"<meta[^>]+charset=['\"]?([A-Za-z0-9_.-]+)", head, re.IGNORECASE)
    return str(match.group(1)).strip() if match else "utf-8"


def _decode_pdf_literal(raw: bytes) -> str:
    out = bytearray()
    i = 0
    while i < len(raw):
        ch = raw[i]
        if ch == 92 and i + 1 < len(raw):
            nxt = raw[i + 1]
            maps = {ord("n"): 10, ord("r"): 13, ord("t"): 9, ord("b"): 8, ord("f"): 12, ord("("): 40, ord(")"): 41, ord("\\"): 92}
            if nxt in maps:
                out.append(maps[nxt])
                i += 2
                continue
            if 48 <= nxt <= 55:
                octal = bytes([nxt])
                j = i + 2
                while j < len(raw) and len(octal) < 3 and 48 <= raw[j] <= 55:
                    octal += bytes([raw[j]])
                    j += 1
                try:
                    out.append(int(octal.decode("ascii"), 8))
                except Exception:
                    pass
                i = j
                continue
            if nxt in {10, 13}:
                i += 2
                if nxt == 13 and i < len(raw) and raw[i] == 10:
                    i += 1
                continue
        out.append(ch)
        i += 1
    data = bytes(out)
    encodings = ("utf-16-be", "utf-8", "latin-1") if data.startswith((b"\xfe\xff", b"\xff\xfe")) or b"\x00" in data[:12] else ("utf-8", "latin-1", "utf-16-be")
    for encoding in encodings:
        try:
            text = data.decode(encoding, errors="ignore")
            if text.strip():
                return text
        except Exception:
            continue
    return ""


def _decode_pdf_hex(raw: bytes) -> str:
    clean = re.sub(rb"[^0-9A-Fa-f]", b"", raw or b"")
    if len(clean) % 2:
        clean += b"0"
    try:
        data = bytes.fromhex(clean.decode("ascii"))
    except Exception:
        return ""
    encodings = ("utf-16-be", "utf-8", "latin-1") if data.startswith((b"\xfe\xff", b"\xff\xfe")) or b"\x00" in data[:12] else ("utf-8", "latin-1", "utf-16-be")
    for encoding in encodings:
        try:
            text = data.decode(encoding, errors="ignore")
            if text.strip():
                return text
        except Exception:
            continue
    return ""


def _extract_pdf_text_from_bytes(raw: bytes) -> str:
    chunks: list[bytes] = [raw]
    for match in re.finditer(rb"(<<.*?>>)\s*stream\r?\n(.*?)\r?\nendstream", raw, flags=re.DOTALL):
        meta = match.group(1)
        stream = match.group(2)
        if b"FlateDecode" in meta:
            try:
                stream = zlib.decompress(stream)
            except Exception:
                pass
        chunks.append(stream)

    text_parts: list[str] = []
    literal_re = re.compile(rb"\((?:\\.|[^\\()])*\)")
    hex_re = re.compile(rb"<([0-9A-Fa-f\s]+)>")
    for chunk in chunks:
        for literal in literal_re.findall(chunk):
            text = _decode_pdf_literal(literal[1:-1])
            if text:
                text_parts.append(text)
        for hex_match in hex_re.findall(chunk):
            text = _decode_pdf_hex(hex_match)
            if text:
                text_parts.append(text)

    text = " ".join(text_parts)
    text = re.sub(r"(?<=[a-zA-ZÀ-ỹ])\s+(?=[,.;:!?])", "", text)
    return _clean_readable_text(text)


def _extract_pdf_text_with_optional_libs(path: str) -> str:
    try:
        import pypdf  # type: ignore

        reader = pypdf.PdfReader(path)
        parts = [page.extract_text() or "" for page in reader.pages]
        text = _clean_readable_text("\n\n".join(parts))
        if text:
            return text
    except Exception:
        pass

    try:
        import PyPDF2  # type: ignore

        reader = PyPDF2.PdfReader(path)
        parts = [page.extract_text() or "" for page in reader.pages]
        text = _clean_readable_text("\n\n".join(parts))
        if text:
            return text
    except Exception:
        pass

    try:
        import fitz  # type: ignore

        doc = fitz.open(path)
        try:
            parts = [page.get_text("text") or "" for page in doc]
        finally:
            doc.close()
        text = _clean_readable_text("\n\n".join(parts))
        if text:
            return text
    except Exception:
        pass

    return ""


def read_pdf_text(file_path: str, max_bytes: int = MAX_PDF_BYTES) -> str:
    path = Path(str(file_path or "").strip())
    if not path.is_file():
        raise FileNotFoundError(f"Không tìm thấy file PDF: {path}")
    if path.suffix.lower() != ".pdf":
        raise ValueError("File nguồn phải là PDF.")
    if path.stat().st_size > max_bytes:
        raise ValueError(f"File PDF quá lớn. Giới hạn hiện tại là khoảng {max_bytes // 1_000_000}MB.")

    text = _extract_pdf_text_with_optional_libs(str(path))
    if not text:
        raw = path.read_bytes()
        text = _extract_pdf_text_from_bytes(raw)
    if not text:
        raise ValueError("Không trích được chữ từ PDF. PDF này có thể là ảnh scan/truyện tranh không có layer text.")
    return limit_source_text(text)


def _read_pdf_bytes(raw: bytes) -> str:
    temp_path = ""
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tf:
            temp_path = tf.name
            tf.write(raw)
        return read_pdf_text(temp_path, max_bytes=max(MAX_PDF_BYTES, len(raw) + 1))
    finally:
        if temp_path and os.path.isfile(temp_path):
            try:
                os.remove(temp_path)
            except Exception:
                pass


def fetch_url_text(url: str, timeout: int = 25, max_bytes: int = MAX_PDF_BYTES) -> str:
    clean_url = str(url or "").strip()
    parsed = urlparse(clean_url)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise ValueError("Link không hợp lệ. Link phải bắt đầu bằng http:// hoặc https://")

    request = Request(
        clean_url,
        headers={
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0 Safari/537.36"
            ),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,text/plain;q=0.8,*/*;q=0.7",
            "Accept-Language": "vi,en-US;q=0.9,en;q=0.8",
        },
    )

    with urlopen(request, timeout=timeout) as response:
        raw = response.read(max_bytes + 1)
        headers = response.headers

    content_type = str(headers.get("Content-Type") or "").lower()
    if "application/pdf" in content_type or clean_url.lower().split("?", 1)[0].endswith(".pdf") or raw.startswith(b"%PDF"):
        if len(raw) > max_bytes:
            raise ValueError(f"File PDF từ link quá lớn. Giới hạn hiện tại là khoảng {max_bytes // 1_000_000}MB.")
        return _read_pdf_bytes(raw)

    if len(raw) > max_bytes:
        raw = raw[:max_bytes]

    charset = _detect_charset(headers, raw)
    decoded = raw.decode(charset, errors="replace")
    if "\ufffd" in decoded and charset.lower() != "utf-8":
        decoded = raw.decode("utf-8", errors="replace")

    if "text/plain" in content_type:
        text = _clean_readable_text(decoded)
    else:
        parser = _ReadableHTMLParser()
        parser.feed(decoded)
        parser.close()
        title = _clean_readable_text(parser.title)
        body = parser.readable_text()
        text = "\n\n".join(part for part in (title, body) if part).strip()

    if not text:
        raise ValueError("Không đọc được nội dung chữ từ link này.")
    return limit_source_text(text)


def limit_source_text(text: str, max_chars: int = MAX_SOURCE_CHARS) -> str:
    clean = _clean_readable_text(text)
    if len(clean) <= max_chars:
        return clean
    cut = clean[:max_chars]
    last_break = max(cut.rfind("\n\n"), cut.rfind(". "), cut.rfind("! "), cut.rfind("? "))
    if last_break > int(max_chars * 0.65):
        cut = cut[: last_break + 1]
    return cut.strip() + "\n\n[Đã rút gọn nội dung nguồn để tránh vượt giới hạn prompt.]"


def build_source_to_video_idea(
    *,
    source_text: str,
    source_mode: str = "manual",
    source_kind: str = "auto",
    source_url: str = "",
    extra_note: str = "",
) -> str:
    kind_label = SOURCE_KIND_LABELS.get(str(source_kind or "auto"), SOURCE_KIND_LABELS["auto"])
    source_mode_clean = str(source_mode or "").strip()
    if source_mode_clean == "link":
        mode_label = "Từ link"
    elif source_mode_clean == "pdf":
        mode_label = "Từ file PDF"
    else:
        mode_label = "Tự nhập"
    source = limit_source_text(source_text)
    note = str(extra_note or "").strip()

    parts = [
        "SOURCE-TO-VIDEO ADAPTATION TASK",
        f"Input mode: {mode_label}",
        f"Source kind: {kind_label}",
    ]
    if source_url:
        parts.append(f"Source URL: {source_url}")
    if note:
        parts.append(f"User note: {note}")

    parts.extend(
        [
            "",
            "Adapt the source into a complete short video script with a clear opening, body/development, and ending/resolution.",
            "Do not copy the source wording line by line. Preserve the core idea, facts/events, emotional arc, and useful details.",
            "For news/article sources: keep the factual meaning neutral and clear, avoid inventing unsupported claims, and turn the article into visual news scenes.",
            "For text-story sources: adapt the chapter/story into cinematic scenes with coherent character actions and dialogue.",
            "For comic/manga sources: treat the source as panel/page material; infer a visual sequence from narration, dialogue, captions, page order, and panel descriptions. Preserve the story flow, character roles, key actions, and emotional beats, but output scenes in the selected app style.",
            "The final visual look is controlled only by the selected output style in the app. Do not preserve the source medium unless it matches that selected style.",
            "No visible subtitles, captions, logos, watermarks, UI, or on-screen text in the generated video prompts.",
            "",
            "SOURCE TEXT:",
            source,
        ]
    )
    return "\n".join(parts).strip()
