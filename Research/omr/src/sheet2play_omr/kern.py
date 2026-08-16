from __future__ import annotations

import unicodedata
from dataclasses import dataclass
from pathlib import Path

from .errors import ResearchError


@dataclass(frozen=True, slots=True)
class KernValidation:
    line_count: int
    maximum_spines: int
    initial_spines: int


def _fail(message: str, *, page: int | None, line: int | None = None) -> ResearchError:
    location = f"Page {page}" if page is not None else "Combined score"
    if line is not None:
        location += f", line {line}"
    return ResearchError("KERN_INVALID", "kern_validation", f"{location}: {message}", page=page)


def _validate_characters(text: str, page: int | None) -> None:
    for character in text:
        if character in "\n\t\r":
            continue
        category = unicodedata.category(character)
        if category in {"Cc", "Cs"}:
            raise _fail(f"invalid Unicode control U+{ord(character):04X}", page=page)
    for token in ("<bos>", "<eos>", "<pad>", "<unk>"):
        if token in text:
            raise _fail(f"unresolved decoder token {token}", page=page)


def _record_kind(field: str) -> str:
    if field.startswith("**") or field.startswith("*"):
        return "interpretation"
    if field.startswith("!"):
        return "comment"
    if field.startswith("="):
        return "barline"
    return "data"


def _next_spine_count(fields: list[str], current: int, page: int | None, line: int) -> int:
    exclusive = [field for field in fields if field.startswith("**")]
    if exclusive and len(exclusive) != len(fields):
        raise _fail("exclusive interpretations cannot be mixed with other fields", page=page, line=line)

    manipulators = {field for field in fields if field in {"*^", "*v", "*x", "*+", "*-"}}
    if "*v" in manipulators:
        if manipulators != {"*v"}:
            raise _fail("spine joins cannot be mixed with other spine operations", page=page, line=line)
        next_count = current
        index = 0
        saw_join = False
        while index < len(fields):
            if fields[index] != "*v":
                index += 1
                continue
            end = index
            while end < len(fields) and fields[end] == "*v":
                end += 1
            group_size = end - index
            if group_size < 2:
                raise _fail("a spine join requires at least two adjacent *v fields", page=page, line=line)
            next_count -= group_size - 1
            saw_join = True
            index = end
        if not saw_join:
            raise _fail("invalid spine join", page=page, line=line)
        return next_count

    if "*x" in manipulators:
        if manipulators != {"*x"} or fields.count("*x") % 2 != 0:
            raise _fail("spine exchanges require paired *x fields", page=page, line=line)
        return current

    next_count = current + fields.count("*^") + fields.count("*+") - fields.count("*-")
    if next_count < 0:
        raise _fail("spine operation produced a negative spine count", page=page, line=line)
    return next_count


def validate_kern(
    text: str,
    *,
    page: int | None = None,
    saw_eos: bool = True,
    hit_max_length: bool = False,
) -> KernValidation:
    if hit_max_length or not saw_eos:
        raise ResearchError(
            "KERN_TRUNCATED",
            "decoding",
            f"Page {page or '?'} did not produce EOS before the token limit",
            page=page,
        )
    if not text or not text.strip():
        raise _fail("empty prediction", page=page)
    _validate_characters(text, page)
    lines = text.replace("\r\n", "\n").replace("\r", "\n").split("\n")
    if lines and lines[-1] == "":
        lines.pop()
    if not lines or lines[0] != "**kern\t**kern":
        raise _fail("the first record must be exactly two **kern spines", page=page, line=1)

    current_spines = 2
    maximum_spines = 2
    terminated = False
    for line_number, raw_line in enumerate(lines[1:], start=2):
        if raw_line == "":
            raise _fail("blank records are not canonical **kern", page=page, line=line_number)
        if raw_line.startswith("!!"):
            if terminated:
                raise _fail("content appears after spine termination", page=page, line=line_number)
            continue
        fields = raw_line.split("\t")
        if any(field == "" for field in fields):
            raise _fail("record contains an empty field", page=page, line=line_number)
        if len(fields) != current_spines:
            raise _fail(
                f"record has {len(fields)} fields; expected {current_spines}",
                page=page,
                line=line_number,
            )
        kinds = {_record_kind(field) for field in fields}
        if len(kinds) != 1:
            raise _fail("record mixes incompatible Humdrum field types", page=page, line=line_number)
        if terminated:
            raise _fail("content appears after spine termination", page=page, line=line_number)
        if kinds == {"interpretation"}:
            current_spines = _next_spine_count(fields, current_spines, page, line_number)
            maximum_spines = max(maximum_spines, current_spines)
            terminated = current_spines == 0

    if not terminated:
        raise _fail("spines are not terminated", page=page, line=len(lines))
    if set(lines[-1].split("\t")) != {"*-"}:
        raise _fail("the final record must terminate every active spine", page=page, line=len(lines))
    return KernValidation(len(lines), maximum_spines, 2)


def combine_pages(pages: list[str]) -> str:
    if not pages:
        raise ResearchError("KERN_INVALID", "page_combination", "No validated pages were provided")
    bodies: list[str] = []
    for page_number, page_text in enumerate(pages, start=1):
        validate_kern(page_text, page=page_number)
        lines = page_text.replace("\r\n", "\n").replace("\r", "\n").strip("\n").split("\n")
        if len(lines[-1].split("\t")) != 2:
            raise ResearchError(
                "KERN_PAGE_LAYOUT_MISMATCH",
                "page_combination",
                f"Page {page_number} does not return to the canonical two-spine layout",
                page=page_number,
            )
        bodies.extend(lines[1:-1])
    combined_lines = ["**kern\t**kern", *bodies, "*-\t*-"]
    combined = "\n".join(combined_lines) + "\n"
    validate_kern(combined)
    return combined


def load_validated_kern(path: Path) -> str:
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as error:
        raise ResearchError("KERN_INVALID", "kern_validation", f"Cannot read {path}: {error}") from error
    validate_kern(text)
    return text

