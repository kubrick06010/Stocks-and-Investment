"""Bounded, inert and deterministic filing section parser."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import html
import re
from stocks_investment.domain.filings import FilingDocument, FilingSection, FilingSectionKind


def _same_length_mask(value: str) -> str:
    """Remove untrusted active content without shifting source coordinates."""

    return "".join("\n" if character == "\n" else " " for character in value)


@dataclass(frozen=True, slots=True)
class ParseLimits:
    """Resource limits applied before and during normalization."""

    max_bytes: int = 5_000_000
    max_text_characters: int = 5_000_000
    max_sections: int = 100


@dataclass(frozen=True, slots=True)
class _Heading:
    item: str
    title: str
    kind: FilingSectionKind
    line_start: int
    line_end: int
    source_start: int
    source_end: int


class SafeFilingParser:
    """Extract common filing sections without executing or fetching content.

    The parser accepts only canonical document bytes supplied by a provider. It
    never follows links, parses active markup, or contacts the network. All
    repeated headings are retained; callers can inspect ``diagnostics`` and the
    ``duplicate_heading`` metadata rather than relying on a hidden TOC choice.
    """

    version = "filing_parser_v1"
    _allowed_mime_types = frozenset({"text/html", "application/xhtml+xml", "text/plain"})
    _block_tags = re.compile(r"</?(?:p|div|br|li|tr|h[1-6]|section|article|table|hr)\b[^>]*>", re.I)
    _script_block = re.compile(r"<(?:script|style|svg|iframe|object|embed|form|template)\b[^>]*>.*?</(?:script|style|svg|iframe|object|embed|form|template)\s*>", re.I | re.S)
    _active_open = re.compile(
        r"<(?:script|style|svg|iframe|object|embed|form|template)\b[^>]*>", re.I
    )
    _tag = re.compile(r"<!--.*?-->|<![^>]*>|<[^>]*>", re.S)
    _item = re.compile(
        r"^\s*(item\s+\d+[a-z]?)\s*[-.:–—]?\s*(.*?)\s*$", re.I
    )
    _title_kinds = (
        (re.compile(r"^business$", re.I), "Item 1", FilingSectionKind.BUSINESS),
        (re.compile(r"^risk\s+factors?$", re.I), "Item 1A", FilingSectionKind.RISK_FACTORS),
        (re.compile(r"^management['’]?s\s+discussion\s+and\s+analysis(?:\s+of\s+financial\s+condition\s+and\s+results\s+of\s+operations)?$", re.I), "Item 7", FilingSectionKind.MD_AND_A),
        (re.compile(r"^(?:quantitative\s+and\s+qualitative\s+disclosures\s+about\s+)?market\s+risk$", re.I), "Item 7A", FilingSectionKind.MARKET_RISK),
        (re.compile(r"^(?:financial\s+statements|financial\s+statements\s+and\s+supplementary\s+data)$", re.I), "Item 8", FilingSectionKind.FINANCIAL_STATEMENTS),
        (re.compile(r"^(?:controls(?:\s+and\s+procedures)?|controls\s+and\s+procedures)$", re.I), "Item 9A", FilingSectionKind.CONTROLS),
    )

    def __init__(self, limits: ParseLimits | None = None) -> None:
        self.limits = limits or ParseLimits()
        self.diagnostics: tuple[str, ...] = ()

    def parse(self, filing: FilingDocument, content: bytes) -> tuple[FilingSection, ...]:
        """Parse inert bytes into immutable canonical sections.

        Unsupported media and limit violations fail closed with ``ValueError``.
        Ambiguous/repeated headings do not fail closed: every occurrence is
        represented and a diagnostic is exposed on this parser instance.
        """
        self.diagnostics = ()
        mime = filing.mime_type.split(";", 1)[0].strip().lower()
        if mime not in self._allowed_mime_types:
            raise ValueError(f"unsupported filing MIME type: {mime}")
        if not content:
            raise ValueError("filing content is empty")
        if len(content) > self.limits.max_bytes:
            raise ValueError("filing content exceeds byte limit")
        try:
            raw = content.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise ValueError("filing content is not valid UTF-8") from exc
        visible, source_map = self._inert_text(raw, mime == "text/plain")
        if len(visible) > self.limits.max_text_characters:
            raise ValueError("normalized filing text exceeds character limit")
        lines = visible.splitlines(keepends=True)
        headings = self._find_headings(lines, source_map)
        if len(headings) > self.limits.max_sections:
            raise ValueError("filing section count exceeds limit")
        diagnostics: list[str] = []
        counts: dict[tuple[str, str], int] = {}
        for heading in headings:
            key = (heading.item.upper(), heading.kind.value)
            counts[key] = counts.get(key, 0) + 1
        if any(value > 1 for value in counts.values()):
            diagnostics.append("repeated section headings retained; review possible table of contents")
        self.diagnostics = tuple(diagnostics)

        sections: list[FilingSection] = []
        for ordinal, heading in enumerate(headings):
            end_line = headings[ordinal + 1].line_start if ordinal + 1 < len(headings) else len(lines)
            section_text = "".join(lines[heading.line_end:end_line]).strip()
            if not section_text:
                section_text = heading.title
            normalized = self._clean_text(section_text)
            if not normalized:
                continue
            end_char = sum(len(line) for line in lines[:end_line])
            start_char = sum(len(line) for line in lines[:heading.line_start])
            start_span = source_map[start_char] if start_char < len(source_map) else (heading.source_start, heading.source_start + 1)
            last_char = max(start_char, min(end_char, len(source_map)) - 1)
            end_raw = source_map[last_char][1] if source_map else heading.source_end
            source_start = len(raw[: start_span[0]].encode("utf-8"))
            source_end = len(raw[:end_raw].encode("utf-8"))
            digest = hashlib.sha256(normalized.encode("utf-8")).hexdigest()
            duplicate = counts.get((heading.item.upper(), heading.kind.value), 0) > 1
            sections.append(
                FilingSection(
                    id=f"{filing.id}:{ordinal}:{digest[:16]}",
                    filing_id=filing.id,
                    item=heading.item.upper(),
                    title=heading.title,
                    kind=heading.kind,
                    ordinal=ordinal,
                    normalized_text=normalized,
                    content_hash=digest,
                    source_start=source_start,
                    source_end=max(source_end, source_start + 1),
                    parser_version=self.version,
                    metadata={
                        "duplicate_heading": duplicate,
                        "diagnostic_count": len(diagnostics),
                        "source_coordinate": "utf-8-byte-offset",
                    },
                )
            )
        return tuple(sections)

    @classmethod
    def _inert_text(cls, raw: str, plain_text: bool) -> tuple[str, list[tuple[int, int]]]:
        """Return visible text and raw-character spans; active markup is discarded."""
        if plain_text:
            return cls._clean_text_with_map(raw)
        masked = cls._script_block.sub(lambda match: _same_length_mask(match.group(0)), raw)
        # A remaining active opening tag is malformed/unclosed. Fail closed for
        # the rest of the document: HTML parsing rules would otherwise treat
        # later headings and secrets as script/style/form text and promote them
        # into canonical filing evidence.
        unclosed = cls._active_open.search(masked)
        if unclosed is not None:
            masked = masked[: unclosed.start()] + _same_length_mask(masked[unclosed.start() :])
        output: list[str] = []
        mapping: list[tuple[int, int]] = []
        cursor = 0
        for match in cls._tag.finditer(masked):
            cls._append_text(masked[cursor:match.start()], cursor, output, mapping)
            if cls._block_tags.fullmatch(match.group(0)):
                output.append("\n")
                mapping.append((match.start(), match.end()))
            cursor = match.end()
        cls._append_text(masked[cursor:], cursor, output, mapping)
        return "".join(output), mapping

    @staticmethod
    def _append_text(chunk: str, offset: int, output: list[str], mapping: list[tuple[int, int]]) -> None:
        decoded = html.unescape(chunk)
        for char in decoded:
            safe = char if char in "\n\r\t" or ord(char) >= 32 else " "
            output.append(safe)
            mapping.append((offset, offset + len(chunk)))

    @classmethod
    def _clean_text_with_map(cls, raw: str) -> tuple[str, list[tuple[int, int]]]:
        output: list[str] = []
        mapping: list[tuple[int, int]] = []
        cls._append_text(raw, 0, output, mapping)
        return "".join(output), mapping

    @staticmethod
    def _clean_text(text: str) -> str:
        return re.sub(r"[ \t\r\f\v]+", " ", text).strip()

    @classmethod
    def _find_headings(cls, lines: list[str], source_map: list[tuple[int, int]]) -> list[_Heading]:
        result: list[_Heading] = []
        char_offset = 0
        for index, line in enumerate(lines):
            candidate = cls._clean_text(line)
            item_match = cls._item.match(candidate)
            item = title = ""
            kind = FilingSectionKind.OTHER
            if item_match and item_match.group(2):
                item = item_match.group(1).replace(" ", " ").upper()
                title = item_match.group(2).strip()
                item, kind = cls._classify_item(item, title)
            else:
                for pattern, mapped_item, mapped_kind in cls._title_kinds:
                    if pattern.fullmatch(candidate):
                        item, title, kind = mapped_item, candidate, mapped_kind
                        break
            if item and kind is not FilingSectionKind.OTHER:
                start = source_map[char_offset][0] if char_offset < len(source_map) else 0
                end_index = min(char_offset + len(line), len(source_map)) - 1
                end = source_map[end_index][1] if end_index >= 0 else start + 1
                result.append(_Heading(item, title, kind, index, index + 1, start, end))
            char_offset += len(line)
        return result

    @classmethod
    def _classify_item(cls, item: str, title: str) -> tuple[str, FilingSectionKind]:
        normalized = re.sub(r"\s+", " ", title).strip().lower()
        for pattern, _, kind in cls._title_kinds:
            if pattern.fullmatch(normalized):
                return item, kind
        item_number = re.search(r"\d+", item)
        mapping = {"1": FilingSectionKind.BUSINESS, "1A": FilingSectionKind.RISK_FACTORS,
                   "7": FilingSectionKind.MD_AND_A, "7A": FilingSectionKind.MARKET_RISK,
                   "8": FilingSectionKind.FINANCIAL_STATEMENTS, "9A": FilingSectionKind.CONTROLS}
        return item, mapping.get(item_number.group(0) if item_number else "", FilingSectionKind.OTHER)
