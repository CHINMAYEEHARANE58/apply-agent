import io
import zipfile

import pytest

from app.resumes.processing import (
    DOCX_MIME_TYPE,
    MAX_RESUME_SIZE_BYTES,
    PDF_MIME_TYPE,
    ResumeProcessingError,
    parse_resume_text,
    process_resume_upload,
    validate_resume_upload,
)


def assert_processing_error(error: pytest.ExceptionInfo[ResumeProcessingError], code: str) -> None:
    assert error.value.code == code


def test_resume_requires_supported_extension_and_matching_mime_type() -> None:
    with pytest.raises(ResumeProcessingError) as unsupported:
        validate_resume_upload(filename="resume.txt", content_type="text/plain", content=b"hello")
    assert_processing_error(unsupported, "unsupported_file_type")

    with pytest.raises(ResumeProcessingError) as mismatched:
        validate_resume_upload(
            filename="resume.pdf", content_type=DOCX_MIME_TYPE, content=b"%PDF-1.7\n%%EOF"
        )
    assert_processing_error(mismatched, "invalid_content_type")


def test_resume_rejects_forged_signature_and_oversized_upload() -> None:
    with pytest.raises(ResumeProcessingError) as forged_pdf:
        validate_resume_upload(
            filename="resume.pdf", content_type=PDF_MIME_TYPE, content=b"this is not a PDF"
        )
    assert_processing_error(forged_pdf, "invalid_file_signature")

    with pytest.raises(ResumeProcessingError) as oversized:
        validate_resume_upload(
            filename="resume.pdf",
            content_type=PDF_MIME_TYPE,
            content=b"%PDF-1.7\n" + (b"x" * MAX_RESUME_SIZE_BYTES),
        )
    assert_processing_error(oversized, "file_too_large")


def test_docx_zip_must_contain_required_office_parts() -> None:
    payload = io.BytesIO()
    with zipfile.ZipFile(payload, "w") as archive:
        archive.writestr("not-a-docx.txt", "not a Word document")

    with pytest.raises(ResumeProcessingError) as malformed:
        validate_resume_upload(
            filename="resume.docx", content_type=DOCX_MIME_TYPE, content=payload.getvalue()
        )
    assert_processing_error(malformed, "malformed_docx")


def test_docx_rejects_macro_payload_before_xml_parsing() -> None:
    payload = _docx_payload("<w:document xmlns:w=\"urn:word\" />", include_macro=True)

    with pytest.raises(ResumeProcessingError) as macro_document:
        process_resume_upload(filename="resume.docx", content_type=DOCX_MIME_TYPE, content=payload)

    assert_processing_error(macro_document, "unsupported_docx_content")


def test_safe_docx_extraction_uses_only_document_text() -> None:
    pytest.importorskip("defusedxml.ElementTree")
    payload = _docx_payload(
        """<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
        <w:body>
          <w:p><w:r><w:t>SUMMARY</w:t></w:r></w:p>
          <w:p><w:r><w:t>Built accessible user interfaces.</w:t></w:r></w:p>
          <w:p><w:r><w:t>SKILLS</w:t></w:r></w:p>
          <w:p><w:r><w:t>TypeScript, React</w:t></w:r></w:p>
        </w:body>
        </w:document>"""
    )

    processed = process_resume_upload(
        filename="master-resume.docx", content_type=DOCX_MIME_TYPE, content=payload
    )

    assert processed.text == "SUMMARY\nBuilt accessible user interfaces.\nSKILLS\nTypeScript, React"
    assert processed.structured_resume["summary"] == "Built accessible user interfaces."
    assert processed.structured_resume["skills"] == ["TypeScript", "React"]


def test_docx_rejects_xml_entity_payload() -> None:
    pytest.importorskip("defusedxml.ElementTree")
    payload = _docx_payload(
        """<!DOCTYPE doc [<!ENTITY untrusted "must not expand">]>
        <w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
          <w:body><w:p><w:r><w:t>&untrusted;</w:t></w:r></w:p></w:body>
        </w:document>"""
    )

    with pytest.raises(ResumeProcessingError) as malicious_xml:
        process_resume_upload(filename="resume.docx", content_type=DOCX_MIME_TYPE, content=payload)

    assert_processing_error(malicious_xml, "malformed_docx")


def _docx_payload(document_xml: str, *, include_macro: bool = False) -> bytes:
    payload = io.BytesIO()
    with zipfile.ZipFile(payload, "w") as archive:
        archive.writestr(
            "[Content_Types].xml",
            """<?xml version="1.0" encoding="UTF-8"?>
            <Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
              <Override PartName="/word/document.xml"
                ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml" />
            </Types>""",
        )
        archive.writestr("word/document.xml", document_xml)
        if include_macro:
            archive.writestr("word/vbaProject.bin", b"untrusted macro bytes")
    return payload.getvalue()


def test_parser_only_returns_text_present_in_resume() -> None:
    source = """Ada Example
ada@example.com | +1 (555) 123-4567 | https://github.com/ada
SUMMARY
Built web applications for student organizations.
EDUCATION
Example University — B.S. Computer Science
EXPERIENCE
Campus Lab — Student Developer
PROJECTS
Portfolio Site — React application
SKILLS
Python, TypeScript | React
CERTIFICATIONS
AWS Cloud Practitioner
ACHIEVEMENTS
Hackathon finalist
"""

    parsed = parse_resume_text(source)

    assert parsed["contact"] == {"email": "ada@example.com", "phone": "+1 (555) 123-4567"}
    assert parsed["summary"] == "Built web applications for student organizations."
    assert parsed["education"] == ["Example University — B.S. Computer Science"]
    assert parsed["experience"] == ["Campus Lab — Student Developer"]
    assert parsed["projects"] == ["Portfolio Site — React application"]
    assert parsed["skills"] == ["Python", "TypeScript", "React"]
    assert "Kubernetes" not in str(parsed)


def test_safe_pdf_processing_rejects_malformed_content() -> None:
    pytest.importorskip("pypdf")

    with pytest.raises(ResumeProcessingError) as malformed:
        process_resume_upload(
            filename="resume.pdf", content_type=PDF_MIME_TYPE, content=b"%PDF-1.7\n%%EOF"
        )

    assert_processing_error(malformed, "malformed_pdf")


def test_safe_pdf_processing_accepts_a_valid_document_without_executing_it() -> None:
    pypdf = pytest.importorskip("pypdf")
    payload = io.BytesIO()
    writer = pypdf.PdfWriter()
    writer.add_blank_page(width=612, height=792)
    writer.write(payload)

    processed = process_resume_upload(
        filename="master-resume.pdf", content_type=PDF_MIME_TYPE, content=payload.getvalue()
    )

    assert processed.extension == ".pdf"
    assert processed.structured_resume == {
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
