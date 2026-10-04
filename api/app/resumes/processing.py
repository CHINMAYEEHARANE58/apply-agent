"""Safe, deterministic processing for uploaded resume files.

This module deliberately treats every uploaded byte as untrusted data.  It
validates the filename, declared media type, and file signature before parsing
only the text needed to construct a source-faithful resume document.  Neither
PDF nor DOCX content is executed, rendered, fetched, or written to disk here.
"""

from __future__ import annotations

import io
import re
import stat
import zipfile
from dataclasses import dataclass
from importlib import import_module
from pathlib import PurePosixPath
from typing import Any, Literal, TypedDict, cast

MAX_RESUME_SIZE_BYTES = 5 * 1024 * 1024
# Multipart boundaries and the field header are permitted in addition to the
# strict 5 MB file cap enforced by ``validate_resume_upload``.
MAX_RESUME_UPLOAD_REQUEST_BYTES = MAX_RESUME_SIZE_BYTES + (256 * 1024)
MAX_EXTRACTED_TEXT_CHARS = 500_000
MAX_PDF_PAGES = 100
# pypdf's defaults are intentionally generous for general documents. Resume
# uploads are small, so use a much smaller decoded-stream budget to avoid a
# compressed PDF consuming large amounts of memory before text limits apply.
MAX_PDF_DECODED_STREAM_BYTES = 5 * 1024 * 1024
MAX_PDF_PAGE_TREE_DEPTH = 20
MAX_PDF_XFORM_INVOCATIONS = 500
MAX_DOCX_MEMBERS = 1_000
MAX_DOCX_MEMBER_UNCOMPRESSED_BYTES = 10 * 1024 * 1024
MAX_DOCX_TOTAL_UNCOMPRESSED_BYTES = 25 * 1024 * 1024
MAX_DOCX_COMPRESSION_RATIO = 100

PDF_MIME_TYPE = "application/pdf"
DOCX_MIME_TYPE = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"

ResumeExtension = Literal[".pdf", ".docx"]

_EXPECTED_MIME_TYPES: dict[ResumeExtension, str] = {
    ".pdf": PDF_MIME_TYPE,
    ".docx": DOCX_MIME_TYPE,
}
_DOCX_REQUIRED_PARTS = frozenset({"[Content_Types].xml", "word/document.xml"})
_DOCX_MAIN_DOCUMENT_CONTENT_TYPE = (
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"
)
_URL_PATTERN = re.compile(r"https?://[^\s<>()\[\]{}]+", re.IGNORECASE)
_EMAIL_PATTERN = re.compile(r"(?<![\w.+-])[\w.+-]+@[\w-]+(?:\.[\w-]+)+(?![\w.-])")
_PHONE_PATTERN = re.compile(r"(?<!\w)(?:\+?\d[\d().\-\s]{6,}\d)(?!\w)")
_PDF_HEADER_PATTERN = re.compile(rb"%PDF-\d\.\d")


class ParsedResumeJSON(TypedDict):
    """The persisted structured-resume shape; values always originate in the upload."""

    contact: dict[str, str]
    summary: str
    education: list[str]
    experience: list[str]
    internships: list[str]
    projects: list[str]
    skills: list[str]
    certifications: list[str]
    achievements: list[str]
    links: list[str]


class ResumeProcessingError(ValueError):
    """A safe, machine-readable validation or parsing failure for an upload."""

    def __init__(self, code: str, message: str) -> None:
        self.code = code
        self.message = message
        super().__init__(message)


@dataclass(frozen=True)
class ValidatedResumeUpload:
    """A validated in-memory upload.  Callers are responsible for private storage."""

    filename: str
    extension: ResumeExtension
    content_type: str
    content: bytes


@dataclass(frozen=True)
class ResumeProcessingResult:
    """Text and structured facts extracted without inference or enrichment."""

    filename: str
    extension: ResumeExtension
    content_type: str
    text: str
    structured_resume: ParsedResumeJSON


def validate_resume_upload(
    *, filename: str, content_type: str | None, content: bytes
) -> ValidatedResumeUpload:
    """Validate an untrusted PDF or DOCX upload before attempting extraction.

    Browser supplied MIME types are not trusted by themselves.  The exact
    extension/MIME pair and a format signature are all required.
    """

    safe_filename, extension = _validate_filename(filename)
    normalized_content_type = _normalize_content_type(content_type)
    expected_content_type = _EXPECTED_MIME_TYPES[extension]

    if normalized_content_type != expected_content_type:
        raise ResumeProcessingError(
            "invalid_content_type",
            "The file's MIME type does not match its resume file extension.",
        )
    if not isinstance(content, bytes):
        raise ResumeProcessingError("invalid_upload", "The uploaded file content is invalid.")
    if not content:
        raise ResumeProcessingError("empty_file", "The uploaded resume cannot be empty.")
    if len(content) > MAX_RESUME_SIZE_BYTES:
        raise ResumeProcessingError(
            "file_too_large", "The uploaded resume must be 5 MB or smaller."
        )

    if extension == ".pdf":
        _validate_pdf_signature(content)
    else:
        _validate_docx_signature(content)

    return ValidatedResumeUpload(
        filename=safe_filename,
        extension=extension,
        content_type=normalized_content_type,
        content=content,
    )


def process_resume_upload(
    *, filename: str, content_type: str | None, content: bytes
) -> ResumeProcessingResult:
    """Validate and safely extract a source-faithful structured resume document."""

    upload = validate_resume_upload(filename=filename, content_type=content_type, content=content)
    text = extract_resume_text(upload)
    return ResumeProcessingResult(
        filename=upload.filename,
        extension=upload.extension,
        content_type=upload.content_type,
        text=text,
        structured_resume=parse_resume_text(text),
    )


def extract_resume_text(upload: ValidatedResumeUpload) -> str:
    """Extract text only; no uploaded content is executed or followed externally."""

    if upload.extension == ".pdf":
        return _extract_pdf_text(upload.content)
    return _extract_docx_text(upload.content)


def empty_structured_resume() -> ParsedResumeJSON:
    """Return the canonical empty resume schema without adding inferred values."""

    return {
        "contact": {},
        "summary": "",
        "education": [],
        "experience": [],
        "internships": [],
        "projects": [],
        "skills": [],
        "certifications": [],
        "achievements": [],
        "links": [],
    }


def parse_resume_text(text: str) -> ParsedResumeJSON:
    """Build a conservative structured view using only exact text from the resume.

    This is intentionally not an AI parser: it does not infer missing fields,
    normalize dates, manufacture skill names, or enrich the candidate profile.
    """

    if not isinstance(text, str):
        raise ResumeProcessingError("invalid_extracted_text", "The extracted resume text is invalid.")
    if len(text) > MAX_EXTRACTED_TEXT_CHARS:
        raise ResumeProcessingError("resume_text_too_large", "The extracted resume text is too large.")

    result = empty_structured_resume()
    normalized_text = _normalize_text(text)
    result["contact"] = _extract_contact(normalized_text)
    result["links"] = _extract_urls(normalized_text)

    sections = _split_sections(normalized_text)
    result["summary"] = _join_source_lines(sections.get("summary", []))
    result["education"] = _source_lines(sections.get("education", []))
    result["experience"] = _source_lines(sections.get("experience", []))
    result["internships"] = _source_lines(sections.get("internships", []))
    result["projects"] = _source_lines(sections.get("projects", []))
    result["skills"] = _extract_skills(sections.get("skills", []))
    result["certifications"] = _source_lines(sections.get("certifications", []))
    result["achievements"] = _source_lines(sections.get("achievements", []))
    return result


def _validate_filename(filename: str) -> tuple[str, ResumeExtension]:
    if not isinstance(filename, str) or not filename.strip() or "\x00" in filename:
        raise ResumeProcessingError("invalid_filename", "The uploaded resume filename is invalid.")

    # Do not preserve a client path as part of an internal storage reference.
    safe_filename = filename.replace("\\", "/").rsplit("/", maxsplit=1)[-1].strip()
    if not safe_filename or safe_filename in {".", ".."}:
        raise ResumeProcessingError("invalid_filename", "The uploaded resume filename is invalid.")
    if len(safe_filename) > 255:
        raise ResumeProcessingError("invalid_filename", "The uploaded resume filename is too long.")
    extension = "." + safe_filename.rsplit(".", maxsplit=1)[-1].lower() if "." in safe_filename else ""
    if extension not in _EXPECTED_MIME_TYPES:
        raise ResumeProcessingError(
            "unsupported_file_type", "Only PDF and DOCX resumes are supported."
        )
    return safe_filename, extension


def _normalize_content_type(content_type: str | None) -> str:
    if not content_type:
        raise ResumeProcessingError("missing_content_type", "The uploaded resume must include a MIME type.")
    return content_type.split(";", maxsplit=1)[0].strip().lower()


def _validate_pdf_signature(content: bytes) -> None:
    if not _PDF_HEADER_PATTERN.match(content[:16]):
        raise ResumeProcessingError("invalid_file_signature", "The uploaded file is not a valid PDF.")
    # A PDF trailer is needed for the parser to safely locate its cross-reference data.
    if b"%%EOF" not in content[-1024:]:
        raise ResumeProcessingError("malformed_pdf", "The uploaded PDF is malformed.")


def _validate_docx_signature(content: bytes) -> None:
    if not content.startswith(b"PK") or not zipfile.is_zipfile(io.BytesIO(content)):
        raise ResumeProcessingError("invalid_file_signature", "The uploaded file is not a valid DOCX document.")
    try:
        with zipfile.ZipFile(io.BytesIO(content)) as archive:
            _validate_docx_archive(archive)
    except ResumeProcessingError:
        raise
    except (OSError, RuntimeError, ValueError, zipfile.BadZipFile) as exc:
        raise ResumeProcessingError("malformed_docx", "The uploaded DOCX document is malformed.") from exc


def _extract_pdf_text(content: bytes) -> str:
    pdf_reader_class, apply_configuration = _load_pdf_processing_components()
    try:
        with apply_configuration(
            maximum_declared_stream_length=MAX_PDF_DECODED_STREAM_BYTES,
            array_based_stream_maximum_output_length=MAX_PDF_DECODED_STREAM_BYTES,
            jbig2_maximum_output_length=MAX_PDF_DECODED_STREAM_BYTES,
            lzw_maximum_output_length=MAX_PDF_DECODED_STREAM_BYTES,
            run_length_maximum_output_length=MAX_PDF_DECODED_STREAM_BYTES,
            zlib_maximum_output_length=MAX_PDF_DECODED_STREAM_BYTES,
            zlib_maximum_recovery_input_length=MAX_PDF_DECODED_STREAM_BYTES,
            image_maximum_buffer_size=MAX_PDF_DECODED_STREAM_BYTES,
            xmp_maximum_input_length=MAX_PDF_DECODED_STREAM_BYTES,
            page_tree_maximum_entries=MAX_PDF_PAGES,
            page_tree_maximum_depth=MAX_PDF_PAGE_TREE_DEPTH,
            xform_maximum_invocations_per_extraction=MAX_PDF_XFORM_INVOCATIONS,
            # pypdf can otherwise discover and execute a local jbig2dec
            # binary for JBIG2 image streams. Resume bytes must never cause an
            # external program to run.
            jbig2dec_binary=None,
        ):
            reader = pdf_reader_class(io.BytesIO(content), strict=True)
            if bool(getattr(reader, "is_encrypted", False)):
                raise ResumeProcessingError(
                    "encrypted_pdf", "Password-protected resumes cannot be processed."
                )
            pages = reader.pages
            if len(pages) > MAX_PDF_PAGES:
                raise ResumeProcessingError("too_many_pages", "The uploaded PDF has too many pages.")

            fragments: list[str] = []
            total_characters = 0
            for page in pages:
                page_text = page.extract_text() or ""
                total_characters += len(page_text)
                if total_characters > MAX_EXTRACTED_TEXT_CHARS:
                    raise ResumeProcessingError(
                        "resume_text_too_large", "The extracted resume text is too large."
                    )
                fragments.append(page_text)
    except ResumeProcessingError:
        raise
    except Exception as exc:
        raise ResumeProcessingError("malformed_pdf", "The uploaded PDF is malformed.") from exc
    return _normalize_text("\n".join(fragments))


def _extract_docx_text(content: bytes) -> str:
    try:
        with zipfile.ZipFile(io.BytesIO(content)) as archive:
            _validate_docx_archive(archive)
            content_types = _read_docx_member(archive, "[Content_Types].xml")
            document_xml = _read_docx_member(archive, "word/document.xml")
    except ResumeProcessingError:
        raise
    except (OSError, RuntimeError, ValueError, zipfile.BadZipFile) as exc:
        raise ResumeProcessingError("malformed_docx", "The uploaded DOCX document is malformed.") from exc

    content_types_root = _safe_xml_root(content_types, "DOCX content types")
    if not _has_docx_main_document_content_type(content_types_root):
        raise ResumeProcessingError("malformed_docx", "The uploaded DOCX document is malformed.")
    document_root = _safe_xml_root(document_xml, "DOCX document")
    if _local_name(getattr(document_root, "tag", "")) != "document":
        raise ResumeProcessingError("malformed_docx", "The uploaded DOCX document is malformed.")
    return _extract_docx_paragraphs(document_root)


def _validate_docx_archive(archive: zipfile.ZipFile) -> None:
    members = archive.infolist()
    if not members or len(members) > MAX_DOCX_MEMBERS:
        raise ResumeProcessingError("malformed_docx", "The uploaded DOCX document is malformed.")

    member_names: set[str] = set()
    total_uncompressed_size = 0
    for member in members:
        _validate_docx_member(member, member_names)
        member_names.add(member.filename)
        if not member.is_dir():
            total_uncompressed_size += member.file_size
    if total_uncompressed_size > MAX_DOCX_TOTAL_UNCOMPRESSED_BYTES:
        raise ResumeProcessingError("docx_too_large", "The uploaded DOCX expands to an unsafe size.")
    if not _DOCX_REQUIRED_PARTS.issubset(member_names):
        raise ResumeProcessingError("malformed_docx", "The uploaded DOCX document is malformed.")
    if "word/vbaProject.bin" in member_names:
        raise ResumeProcessingError("unsupported_docx_content", "Macro-enabled resumes are not supported.")


def _validate_docx_member(member: zipfile.ZipInfo, member_names: set[str]) -> None:
    path = PurePosixPath(member.filename)
    if (
        not member.filename
        or member.filename in member_names
        or path.is_absolute()
        or ".." in path.parts
        or "\\" in member.filename
        or "\x00" in member.filename
    ):
        raise ResumeProcessingError("malformed_docx", "The uploaded DOCX document is malformed.")
    if member.flag_bits & 0x1:
        raise ResumeProcessingError("encrypted_docx", "Password-protected resumes cannot be processed.")
    unix_file_mode = member.external_attr >> 16
    if stat.S_ISLNK(unix_file_mode):
        raise ResumeProcessingError("malformed_docx", "The uploaded DOCX document is malformed.")
    if member.is_dir():
        return
    if member.compress_type not in {zipfile.ZIP_STORED, zipfile.ZIP_DEFLATED}:
        raise ResumeProcessingError(
            "unsupported_docx_compression", "The uploaded DOCX uses an unsupported compression method."
        )
    if member.file_size > MAX_DOCX_MEMBER_UNCOMPRESSED_BYTES:
        raise ResumeProcessingError("docx_too_large", "The uploaded DOCX contains an oversized file.")
    if member.file_size and not member.compress_size:
        raise ResumeProcessingError("malformed_docx", "The uploaded DOCX document is malformed.")
    if member.compress_size and member.file_size / member.compress_size > MAX_DOCX_COMPRESSION_RATIO:
        raise ResumeProcessingError("unsafe_docx_compression", "The uploaded DOCX has an unsafe compression ratio.")


def _read_docx_member(archive: zipfile.ZipFile, name: str) -> bytes:
    try:
        return archive.read(name)
    except (KeyError, OSError, RuntimeError, zipfile.BadZipFile) as exc:
        raise ResumeProcessingError("malformed_docx", "The uploaded DOCX document is malformed.") from exc


def _load_pdf_processing_components() -> tuple[type[Any], Any]:
    try:
        module = import_module("pypdf")
        reader_class = module.PdfReader
        apply_configuration = module.apply_configuration
    except (ImportError, AttributeError) as exc:
        raise ResumeProcessingError(
            "processor_unavailable", "Resume processing is temporarily unavailable."
        ) from exc
    return cast(type[Any], reader_class), apply_configuration


def _safe_xml_root(xml_bytes: bytes, document_name: str) -> Any:
    """Parse DOCX XML only with defusedxml; never fall back to stdlib XML parsing."""

    try:
        element_tree = import_module("defusedxml.ElementTree")
        fromstring = element_tree.fromstring
        return fromstring(xml_bytes)
    except ResumeProcessingError:
        raise
    except ImportError as exc:
        raise ResumeProcessingError(
            "processor_unavailable", "Resume processing is temporarily unavailable."
        ) from exc
    except Exception as exc:
        raise ResumeProcessingError(
            "malformed_docx", f"The uploaded {document_name} is malformed."
        ) from exc


def _has_docx_main_document_content_type(root: Any) -> bool:
    for child in root:
        if (
            _local_name(getattr(child, "tag", "")) == "Override"
            and child.attrib.get("PartName") == "/word/document.xml"
            and child.attrib.get("ContentType") == _DOCX_MAIN_DOCUMENT_CONTENT_TYPE
        ):
            return True
    return False


def _extract_docx_paragraphs(root: Any) -> str:
    paragraphs: list[str] = []
    total_characters = 0
    for element in root.iter():
        if _local_name(getattr(element, "tag", "")) != "p":
            continue
        fragments: list[str] = []
        for child in element.iter():
            child_name = _local_name(getattr(child, "tag", ""))
            if child_name == "t" and child.text:
                fragments.append(str(child.text))
            elif child_name == "tab":
                fragments.append("\t")
            elif child_name in {"br", "cr"}:
                fragments.append("\n")
        paragraph = "".join(fragments)
        total_characters += len(paragraph)
        if total_characters > MAX_EXTRACTED_TEXT_CHARS:
            raise ResumeProcessingError(
                "resume_text_too_large", "The extracted resume text is too large."
            )
        if paragraph.strip():
            paragraphs.append(paragraph)
    return _normalize_text("\n".join(paragraphs))


def _local_name(tag: Any) -> str:
    return str(tag).rsplit("}", maxsplit=1)[-1]


_SECTION_ALIASES: dict[str, frozenset[str]] = {
    "summary": frozenset({"summary", "professional summary", "profile", "objective", "about me"}),
    "education": frozenset({"education", "academic background"}),
    "experience": frozenset(
        {"experience", "work experience", "professional experience", "employment history"}
    ),
    "internships": frozenset({"internships", "internship experience"}),
    "projects": frozenset({"projects", "personal projects", "academic projects"}),
    "skills": frozenset({"skills", "technical skills", "technologies", "skills and technologies"}),
    "certifications": frozenset({"certifications", "certificates", "licenses and certifications"}),
    "achievements": frozenset({"achievements", "awards", "honors", "honors and awards"}),
}


def _split_sections(text: str) -> dict[str, list[str]]:
    sections: dict[str, list[str]] = {}
    current_section: str | None = None
    for line in text.splitlines():
        header = _section_for_heading(line)
        if header is not None:
            current_section = header
            sections.setdefault(header, [])
        elif current_section is not None:
            sections[current_section].append(line)
    return sections


def _section_for_heading(line: str) -> str | None:
    candidate = re.sub(r"\s+", " ", line.strip().rstrip(":"))
    if not candidate or len(candidate) > 50:
        return None
    normalized = re.sub(r"[^a-z0-9& ]", "", candidate.lower()).replace("&", "and")
    normalized = re.sub(r"\s+", " ", normalized).strip()
    for section, aliases in _SECTION_ALIASES.items():
        if normalized in aliases:
            return section
    return None


def _source_lines(lines: list[str]) -> list[str]:
    return [line.strip() for line in lines if line.strip()]


def _join_source_lines(lines: list[str]) -> str:
    return "\n".join(_source_lines(lines))


def _extract_skills(lines: list[str]) -> list[str]:
    skills: list[str] = []
    seen: set[str] = set()
    for line in _source_lines(lines):
        values = re.split(r"[,;|]", line)
        for value in values:
            skill = value.strip().lstrip("•*- ").strip()
            if skill and skill.casefold() not in seen:
                skills.append(skill)
                seen.add(skill.casefold())
    return skills


def _extract_contact(text: str) -> dict[str, str]:
    contact: dict[str, str] = {}
    email = _EMAIL_PATTERN.search(text)
    if email:
        contact["email"] = email.group(0)
    phone = _PHONE_PATTERN.search(text)
    if phone:
        contact["phone"] = phone.group(0).strip()
    return contact


def _extract_urls(text: str) -> list[str]:
    links: list[str] = []
    seen: set[str] = set()
    for match in _URL_PATTERN.finditer(text):
        link = match.group(0).rstrip(".,;:!?")
        if link and link.casefold() not in seen:
            links.append(link)
            seen.add(link.casefold())
    return links


def _normalize_text(text: str) -> str:
    return text.replace("\r\n", "\n").replace("\r", "\n").replace("\x00", "")
