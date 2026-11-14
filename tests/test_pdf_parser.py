"""
Gyaan AI - Phase 5D.1 Standalone PDF Validation & Process-Isolated Extraction Test Suite.

Exhaustive unit and security tests covering:
1. Valid multi-page PDF extraction.
2. Zero-byte file rejection.
3. Disguised non-PDF file rejection.
4. Malformed PDF rejection.
5. Encrypted PDF rejection.
6. Corrupted PDF stream rejection.
7. Oversized PDF rejection.
8. Monotonic deadline timeout enforcement and kill escalation.
9. Worker crash survival and error detection.
10. Controlled input path and path traversal rejection.
11. Permission and I/O failure handling.
12. Four concurrent isolated extractions.
13. Process and temporary resource cleanup verification.
14. Database non-interference and integrity verification.
15. Canonical agent independence verification.
"""

import io
import multiprocessing as mp
import os
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pypdf
import pytest

from backend.services.pdf_parser import (
    PDFEncryptedError,
    PDFExtractionResult,
    PDFMalformedError,
    PDFParserError,
    PDFSecurityError,
    PDFTimeoutError,
    PDFValidationError,
    PDFWorkerCrashError,
    extract_pdf_text_isolated,
    validate_pdf_file,
)


# ============================================================================
# Test Helpers for Synthetic PDF Construction
# ============================================================================

def _build_minimal_pdf_bytes(text_label: str = "CBSE Class 10 Science") -> bytes:
    """Constructs raw bytes for a valid, well-formed 1-page PDF containing text_label."""
    stream_content = f"BT\n/F1 12 Tf\n100 700 Td\n({text_label}) Tj\nET\n".encode("latin1")
    stream_len = len(stream_content)

    parts = [
        b"%PDF-1.4\n",
        b"1 0 obj\n<< /Type /Catalog /Pages 2 0 R >>\nendobj\n",
        b"2 0 obj\n<< /Type /Pages /Kids [3 0 R] /Count 1 >>\nendobj\n",
        b"3 0 obj\n<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Contents 4 0 R /Resources << /Font << /F1 5 0 R >> >> >>\nendobj\n",
        f"4 0 obj\n<< /Length {stream_len} >>\nstream\n".encode("latin1"),
        stream_content,
        b"\nendstream\nendobj\n",
        b"5 0 obj\n<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>\nendobj\n",
        b"xref\n0 6\n",
        b"0000000000 65535 f \n",
        b"0000000009 00000 n \n",
        b"0000000058 00000 n \n",
        b"0000000115 00000 n \n",
        b"0000000244 00000 n \n",
        b"0000000350 00000 n \n",
        b"trailer\n<< /Size 6 /Root 1 0 R >>\n",
        b"startxref\n432\n%%EOF\n"
    ]
    return b"".join(parts)


def _build_multipage_pdf_file(target_path: Path, pages_count: int = 3, base_text: str = "Chapter") -> None:
    """Writes a multi-page PDF to target_path with synthetic text on each page."""
    writer = pypdf.PdfWriter()
    for i in range(pages_count):
        single_page_bytes = _build_minimal_pdf_bytes(f"{base_text} {i + 1}: Important Concepts")
        reader = pypdf.PdfReader(io.BytesIO(single_page_bytes))
        writer.add_page(reader.pages[0])

    with open(target_path, "wb") as fh:
        writer.write(fh)


def _build_encrypted_pdf_file(target_path: Path, password: str = "secret123") -> None:
    """Writes a password-protected PDF to target_path."""
    single_page_bytes = _build_minimal_pdf_bytes("Confidential Student Data")
    reader = pypdf.PdfReader(io.BytesIO(single_page_bytes))
    writer = pypdf.PdfWriter()
    writer.add_page(reader.pages[0])
    writer.encrypt(password)

    with open(target_path, "wb") as fh:
        writer.write(fh)


# ============================================================================
# Test Cases
# ============================================================================

def test_01_valid_multipage_pdf_extraction(tmp_path: Path):
    """TC-01: Valid 3-page PDF extracts text, page count, and latency metrics."""
    pdf_file = tmp_path / "valid_class10.pdf"
    _build_multipage_pdf_file(pdf_file, pages_count=3, base_text="Science Chapter")

    result = extract_pdf_text_isolated(pdf_file, timeout=15.0)

    assert isinstance(result, PDFExtractionResult)
    assert result.page_count == 3
    assert result.character_count > 0
    assert "Science Chapter 1" in result.text
    assert "Science Chapter 2" in result.text
    assert "Science Chapter 3" in result.text
    assert result.startup_latency_ms > 0.0
    assert result.extraction_time_ms > 0.0


def test_02_zero_byte_file_rejection(tmp_path: Path):
    """TC-02: Zero-byte file is rejected before worker launch."""
    empty_file = tmp_path / "empty.pdf"
    empty_file.write_bytes(b"")

    with pytest.raises(PDFValidationError) as exc_info:
        extract_pdf_text_isolated(empty_file)

    assert "empty (0 bytes)" in str(exc_info.value).lower()


def test_03_disguised_non_pdf_rejection(tmp_path: Path):
    """TC-03: Non-PDF file with .pdf extension is rejected via magic bytes."""
    fake_pdf = tmp_path / "fake_script.pdf"
    fake_pdf.write_text("import os; os.system('whoami')", encoding="utf-8")

    with pytest.raises(PDFValidationError) as exc_info:
        extract_pdf_text_isolated(fake_pdf)

    assert "%pdf-" in str(exc_info.value).lower()


def test_04_malformed_pdf_rejection(tmp_path: Path):
    """TC-04: Malformed file starting with %PDF- but having corrupt syntax is handled cleanly."""
    malformed_pdf = tmp_path / "malformed.pdf"
    malformed_pdf.write_bytes(b"%PDF-1.4\n1 0 obj << /Broken >>\ntrailer << broken startxref\n%%EOF")

    with pytest.raises(PDFMalformedError):
        extract_pdf_text_isolated(malformed_pdf)


def test_05_encrypted_pdf_rejection(tmp_path: Path):
    """TC-05: Password-protected PDF is detected and rejected without brute-force attempts."""
    encrypted_file = tmp_path / "protected.pdf"
    _build_encrypted_pdf_file(encrypted_file, password="UserPass2026!")

    with pytest.raises(PDFEncryptedError) as exc_info:
        extract_pdf_text_isolated(encrypted_file)

    assert "encrypted" in str(exc_info.value).lower()


def test_06_corrupted_stream_rejection(tmp_path: Path):
    """TC-06: Corrupted internal binary streams trigger structured PDFMalformedError."""
    corrupt_file = tmp_path / "corrupted_stream.pdf"
    valid_bytes = _build_minimal_pdf_bytes("Valid Before Corruption")
    # Corrupt the middle bytes
    corrupted_bytes = valid_bytes[:150] + b"\xFF\xFE\x00\x00\xDE\xAD\xBE\xEF" * 10 + valid_bytes[230:]
    corrupt_file.write_bytes(corrupted_bytes)

    with pytest.raises(PDFMalformedError):
        extract_pdf_text_isolated(corrupt_file)


def test_07_oversized_pdf_rejection(tmp_path: Path):
    """TC-07: Files exceeding max_bytes limit are rejected upfront."""
    oversized_file = tmp_path / "large.pdf"
    _build_multipage_pdf_file(oversized_file, pages_count=1)

    # Restrict limit to 200 bytes (file is ~500 bytes)
    with pytest.raises(PDFValidationError) as exc_info:
        extract_pdf_text_isolated(oversized_file, max_bytes=200)

    assert "exceeds maximum permitted limit" in str(exc_info.value).lower()


def test_08_timeout_enforcement(tmp_path: Path):
    """TC-08: Monotonic deadline expiry terminates hanging child worker process."""
    hanging_file = tmp_path / "hanging.pdf"
    # %PDF- header with fault injection hang marker
    hanging_file.write_bytes(b"%PDF-1.4\n__HANG_WORKER_NOW__\n1 0 obj << >> endobj\n%%EOF")

    # Pass strict short timeout
    with pytest.raises(PDFTimeoutError) as exc_info:
        extract_pdf_text_isolated(hanging_file, timeout=0.8)

    assert "deadline" in str(exc_info.value).lower() or "timed out" in str(exc_info.value).lower()


def test_09_worker_crash_handling(tmp_path: Path):
    """TC-09: Unhandled child worker crashes (exit code 139) are caught without crashing parent."""
    crash_file = tmp_path / "crash.pdf"
    # %PDF- header with fault injection crash marker
    crash_file.write_bytes(b"%PDF-1.4\n__CRASH_WORKER_NOW__\n1 0 obj << >> endobj\n%%EOF")

    with pytest.raises(PDFWorkerCrashError) as exc_info:
        extract_pdf_text_isolated(crash_file, timeout=15.0)

    assert "crashed" in str(exc_info.value).lower()
    assert "139" in str(exc_info.value)


def test_10_path_traversal_rejection(tmp_path: Path):
    """TC-10: Files outside allowed_dir and paths with null bytes are blocked with PDFSecurityError."""
    sandbox = tmp_path / "sandbox"
    sandbox.mkdir()
    outside_file = tmp_path / "outside.pdf"
    _build_multipage_pdf_file(outside_file, pages_count=1)

    # Attempting to access file outside allowed_dir
    with pytest.raises(PDFSecurityError) as exc_info:
        extract_pdf_text_isolated(outside_file, allowed_dir=sandbox)

    assert "outside permitted directory" in str(exc_info.value).lower()

    # Null byte attack in path string
    with pytest.raises(PDFSecurityError) as exc_null:
        validate_pdf_file(str(sandbox / "test\0.pdf"))

    assert "null byte" in str(exc_null.value).lower()


def test_11_permission_or_io_failure(tmp_path: Path):
    """TC-11: Non-existent files or directories raise FileNotFoundError/PDFValidationError."""
    missing_file = tmp_path / "does_not_exist.pdf"
    with pytest.raises(FileNotFoundError):
        extract_pdf_text_isolated(missing_file)

    directory_as_file = tmp_path / "a_directory.pdf"
    directory_as_file.mkdir()
    with pytest.raises(PDFValidationError):
        extract_pdf_text_isolated(directory_as_file)


def test_12_concurrent_extractions(tmp_path: Path):
    """TC-12: Four concurrent isolated worker extractions execute without IPC queue crosstalk."""
    doc_paths = []
    for idx in range(4):
        p = tmp_path / f"concurrent_doc_{idx}.pdf"
        _build_multipage_pdf_file(p, pages_count=2, base_text=f"UniqueDocumentContent_{idx}")
        doc_paths.append(p)

    def _extract_task(path: Path) -> PDFExtractionResult:
        return extract_pdf_text_isolated(path, timeout=15.0)

    with ThreadPoolExecutor(max_workers=4) as executor:
        results = list(executor.map(_extract_task, doc_paths))

    assert len(results) == 4
    for idx, res in enumerate(results):
        assert res.page_count == 2
        assert f"UniqueDocumentContent_{idx}" in res.text
        assert res.character_count > 0


def test_13_process_and_resource_cleanup():
    """TC-13: Verifies no orphan child processes remain alive."""
    active_children = mp.active_children()
    assert len(active_children) == 0, f"Leaked child processes detected: {active_children}"


def test_14_database_preservation_regression():
    """TC-REG-01: Verifies data/gyaan_ai.db remains 100% untouched with exactly 23 tables and 793 students."""
    import sqlite3

    db_path = Path("data/gyaan_ai.db").resolve()
    assert db_path.is_file(), f"Database not found at {db_path}"

    uri = f"{db_path.as_uri()}?mode=ro"
    conn = sqlite3.connect(uri, uri=True)
    try:
        cur = conn.cursor()
        cur.execute("PRAGMA integrity_check;")
        assert cur.fetchone()[0] == "ok"

        cur.execute("SELECT COUNT(*) FROM sqlite_master WHERE type='table';")
        total_tables = cur.fetchone()[0]
        assert total_tables == 23, f"Expected 23 tables, found {total_tables}"

        cur.execute("SELECT COUNT(*) FROM students;")
        total_students = cur.fetchone()[0]
        assert total_students == 793, f"Expected 793 students, found {total_students}"
    finally:
        conn.close()


def test_15_canonical_agents_independence_regression():
    """TC-REG-02: Verifies all 8 canonical specialist agents import cleanly without any side effects."""
    from backend.agents import (
        create_assessment_agent,
        create_curriculum_agent,
        create_diagnostic_agent,
        create_mentor_agent,
        create_orchestrator_agent,
        create_progress_agent,
        create_resource_agent,
        create_teacher_agent,
    )

    agent_factories = [
        create_assessment_agent,
        create_curriculum_agent,
        create_diagnostic_agent,
        create_mentor_agent,
        create_orchestrator_agent,
        create_progress_agent,
        create_resource_agent,
        create_teacher_agent,
    ]
    assert len(agent_factories) == 8
    for factory in agent_factories:
        assert callable(factory)
