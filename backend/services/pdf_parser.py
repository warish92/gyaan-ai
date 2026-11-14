"""
Gyaan AI - Phase 5D.1 Standalone PDF Validation & Process-Isolated Extraction Service.

Strictly standalone utility providing:
- File boundary & directory traversal validation (allowed_dir confinement)
- Maximum file size enforcement (10 MB default)
- PDF magic-byte validation (%PDF-)
- Encrypted/password-protected PDF rejection
- Malformed/corrupted PDF handling
- Process-isolated extraction via Windows multiprocessing spawn
- True monotonic 15-second deadline enforcement with termination and kill escalation
- Zero persistent storage, zero database access, zero application state
"""

import multiprocessing as mp
import os
import queue
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pypdf
from pypdf.errors import PdfReadError


# ============================================================================
# 1. Structured Exception Hierarchy
# ============================================================================

class PDFParserError(Exception):
    """Base exception for all PDF parsing and validation failures."""
    pass


class PDFValidationError(PDFParserError):
    """Raised when file validation fails (size limit, empty file, invalid magic bytes)."""
    pass


class PDFSecurityError(PDFParserError):
    """Raised on path traversal or access outside permitted directory boundaries."""
    pass


class PDFEncryptedError(PDFParserError):
    """Raised when the document is encrypted or password-protected."""
    pass


class PDFMalformedError(PDFParserError):
    """Raised when PDF syntax, xref table, or stream dictionaries are corrupt."""
    pass


class PDFTimeoutError(PDFParserError):
    """Raised when process startup, extraction, or collection exceeds the monotonic deadline."""
    pass


class PDFWorkerCrashError(PDFParserError):
    """Raised when the worker child process terminates abnormally or exits non-zero."""
    pass


class PDFIOError(PDFParserError):
    """Raised when underlying file I/O or permissions fail."""
    pass


# ============================================================================
# 2. Structured Extraction Result
# ============================================================================

@dataclass(frozen=True)
class PDFExtractionResult:
    """Immutable data container for successful extraction outputs."""
    text: str
    page_count: int
    character_count: int
    metadata: dict[str, Any]
    extraction_time_ms: float
    startup_latency_ms: float


# ============================================================================
# 3. Controlled Path and File Validation
# ============================================================================

def validate_pdf_file(
    file_path: Path | str,
    allowed_dir: Path | str | None = None,
    max_bytes: int = 10 * 1024 * 1024,
) -> dict[str, Any]:
    """
    Validates a PDF file for existence, directory confinement, size, and magic bytes.

    Args:
        file_path: Path to the target PDF file.
        allowed_dir: Optional canonical parent directory; path must reside within this root.
        max_bytes: Maximum allowed file size in bytes (default 10 MB).

    Returns:
        dict containing verified path, canonical path, and size in bytes.

    Raises:
        FileNotFoundError: If the file does not exist.
        PDFSecurityError: If path traversal or directory escaping is detected.
        PDFValidationError: If size is 0, size > max_bytes, or magic bytes are missing.
        PDFIOError: If permissions or OS I/O fail.
    """
    # 1. Null-byte validation
    str_path = str(file_path)
    if "\0" in str_path:
        raise PDFSecurityError("Access denied: File path contains prohibited null byte characters.")

    # 2. Path resolution
    try:
        raw_path = Path(file_path)
        resolved_path = raw_path.resolve()
    except Exception as exc:
        raise PDFSecurityError(f"Failed to resolve input path '{file_path}': {exc}") from exc

    # 3. Controlled directory confinement
    if allowed_dir is not None:
        try:
            resolved_allowed = Path(allowed_dir).resolve()
            if not resolved_path.is_relative_to(resolved_allowed):
                raise PDFSecurityError(
                    f"Access denied: Target path '{resolved_path}' is outside permitted directory '{resolved_allowed}'."
                )
        except ValueError as exc:
            raise PDFSecurityError(f"Access denied: Path traversal detected: {exc}") from exc

    # 4. Regular file verification
    if not resolved_path.exists():
        raise FileNotFoundError(f"PDF file does not exist: '{resolved_path}'")

    if not resolved_path.is_file():
        raise PDFValidationError(f"Target path is not a regular file: '{resolved_path}'")

    # 5. File size verification
    try:
        stat_result = resolved_path.stat()
        file_size = stat_result.st_size
    except PermissionError as exc:
        raise PDFIOError(f"Permission denied accessing '{resolved_path}': {exc}") from exc
    except OSError as exc:
        raise PDFIOError(f"OS error inspecting file '{resolved_path}': {exc}") from exc

    if file_size == 0:
        raise PDFValidationError(f"File is empty (0 bytes): '{resolved_path}'")

    if file_size > max_bytes:
        raise PDFValidationError(
            f"File size ({file_size:,} bytes) exceeds maximum permitted limit ({max_bytes:,} bytes / 10 MB)."
        )

    # 6. PDF magic-byte validation (%PDF-)
    try:
        with open(resolved_path, "rb") as fh:
            header_bytes = fh.read(1024)
    except PermissionError as exc:
        raise PDFIOError(f"Permission denied reading header of '{resolved_path}': {exc}") from exc
    except OSError as exc:
        raise PDFIOError(f"I/O error reading header of '{resolved_path}': {exc}") from exc

    if b"%PDF-" not in header_bytes:
        raise PDFValidationError(
            f"Invalid file format: '{resolved_path.name}' does not contain required '%PDF-' magic bytes."
        )

    return {
        "file_path": str(resolved_path),
        "file_name": resolved_path.name,
        "size_bytes": file_size,
    }


# ============================================================================
# 4. Top-Level Worker Entrypoint (Windows spawn-compatible)
# ============================================================================

def _pdf_extract_worker(file_path_str: str, result_queue: Any) -> None:
    """
    Top-level worker entrypoint executed in a fresh child process via Windows spawn.

    Extracts text and metadata using pypdf in complete isolation from the caller.
    Communicates results back via a bounded IPC queue.
    """
    try:
        # Simulation hooks for fault injection (used by test suite)
        try:
            with open(file_path_str, "rb") as fh:
                first_kilo = fh.read(1024)
                if b"__CRASH_WORKER_NOW__" in first_kilo:
                    os._exit(139)  # Simulate unhandled segfault / C-level crash
                if b"__HANG_WORKER_NOW__" in first_kilo:
                    time.sleep(30)  # Simulate infinite loop / pathological computation
        except Exception:
            pass

        reader = pypdf.PdfReader(file_path_str)

        # Encryption detection
        if reader.is_encrypted:
            result_queue.put({"status": "encrypted"})
            return

        total_pages = len(reader.pages)
        if total_pages == 0:
            result_queue.put({
                "status": "malformed",
                "error": "Document contains zero pages."
            })
            return

        # Text extraction page-by-page
        extracted_pages: list[str] = []
        has_page_errors = False
        for page_idx, page in enumerate(reader.pages):
            try:
                page_text = page.extract_text() or ""
                extracted_pages.append(page_text)
            except Exception:
                has_page_errors = True
                extracted_pages.append("")

        full_text = "\n\n".join(extracted_pages).strip()
        if (has_page_errors and not full_text) or not full_text:
            result_queue.put({
                "status": "malformed",
                "error": "No readable text extracted from corrupted PDF streams."
            })
            return

        # Sanitize metadata to primitives
        raw_meta = reader.metadata or {}
        safe_meta: dict[str, Any] = {}
        for key, val in raw_meta.items():
            str_key = str(key).lstrip("/")
            safe_meta[str_key] = str(val) if val is not None else ""

        result_queue.put({
            "status": "success",
            "text": full_text,
            "page_count": total_pages,
            "character_count": len(full_text),
            "metadata": safe_meta,
        })

    except PdfReadError as exc:
        result_queue.put({
            "status": "malformed",
            "error": f"Corrupt or malformed PDF structure: {exc}"
        })
    except Exception as exc:
        result_queue.put({
            "status": "error",
            "error": f"Unhandled extraction exception: {exc}"
        })


def _escalate_kill_process(proc: mp.Process) -> None:
    """
    Terminates a process, joins it, escalates to kill if still alive, and confirms termination.
    """
    if proc.is_alive():
        try:
            proc.terminate()
        except Exception:
            pass
        proc.join(timeout=0.5)

    if proc.is_alive():
        try:
            proc.kill()
        except Exception:
            pass
        proc.join(timeout=0.5)


# ============================================================================
# 5. Process-Isolated Extraction with Monotonic Deadline
# ============================================================================

def extract_pdf_text_isolated(
    file_path: Path | str,
    allowed_dir: Path | str | None = None,
    timeout: float = 15.0,
    max_bytes: int = 10 * 1024 * 1024,
) -> PDFExtractionResult:
    """
    Extracts text and metadata from a PDF file using an isolated child process.

    Enforces:
    - Path and boundary validation before spawn
    - A strict monotonic master deadline covering startup, extraction, and collection
    - Two-stage termination and kill escalation on timeout
    - Clean IPC handle and queue closure
    - Detection of worker crashes, abnormal exit codes, and empty queues

    Args:
        file_path: Path to target PDF.
        allowed_dir: Optional directory to which file_path must be confined.
        timeout: Total operation budget in seconds (default 15.0s).
        max_bytes: Maximum allowed file size in bytes (default 10 MB).

    Returns:
        PDFExtractionResult containing extracted text, counts, and latency metrics.

    Raises:
        PDFValidationError: If file fails size or magic byte checks.
        PDFSecurityError: If path violates allowed_dir confinement.
        PDFEncryptedError: If document is encrypted/password-protected.
        PDFMalformedError: If document structure or streams are corrupt.
        PDFTimeoutError: If execution exceeds the monotonic deadline.
        PDFWorkerCrashError: If child process dies or delivers empty results.
    """
    start_monotonic = time.monotonic()
    master_deadline = start_monotonic + timeout

    # 1. Pre-spawn validation (deducted from master deadline)
    validation_info = validate_pdf_file(file_path=file_path, allowed_dir=allowed_dir, max_bytes=max_bytes)
    resolved_path_str = validation_info["file_path"]

    # 2. Check remaining time before process launch
    remaining = master_deadline - time.monotonic()
    if remaining <= 0:
        raise PDFTimeoutError(
            f"Pre-flight validation consumed entire budget; timed out before worker launch ({timeout:.2f}s budget)."
        )

    # 3. Create isolated spawn context and IPC channel
    ctx = mp.get_context("spawn")
    result_queue = ctx.Queue(maxsize=1)
    proc = ctx.Process(target=_pdf_extract_worker, args=(resolved_path_str, result_queue))

    startup_latency_ms = 0.0
    payload: dict[str, Any] | None = None

    try:
        # Measure actual process start latency
        t_spawn_start = time.monotonic()
        proc.start()
        t_spawn_end = time.monotonic()
        startup_latency_ms = (t_spawn_end - t_spawn_start) * 1000.0

        # Check if startup itself exceeded master deadline
        remaining = master_deadline - time.monotonic()
        if remaining <= 0:
            _escalate_kill_process(proc)
            raise PDFTimeoutError(
                f"Process startup latency ({startup_latency_ms:.1f}ms) exceeded total extraction budget of {timeout:.1f}s."
            )

        # 4. Join process with remaining deadline
        proc.join(timeout=max(0.0, remaining))

        # 5. Check if process is still alive after timeout
        if proc.is_alive():
            _escalate_kill_process(proc)
            if proc.is_alive():
                raise RuntimeError(f"FATAL: Child worker process (PID {proc.pid}) could not be terminated.")
            raise PDFTimeoutError(
                f"PDF extraction exceeded strict monotonic deadline of {timeout:.1f}s (startup took {startup_latency_ms:.1f}ms)."
            )

        # 6. Verify worker exit code
        if proc.exitcode != 0:
            raise PDFWorkerCrashError(
                f"Worker process crashed abnormally with exit code {proc.exitcode}."
            )

        # 7. Calculate remaining time for result collection
        remaining = master_deadline - time.monotonic()
        if remaining <= 0:
            raise PDFTimeoutError(
                f"PDF extraction completed but result collection exceeded master deadline of {timeout:.1f}s."
            )

        try:
            payload = result_queue.get(timeout=max(0.0, remaining))
        except queue.Empty:
            raise PDFWorkerCrashError(
                "Worker process exited cleanly but delivered no result payload (IPC empty)."
            )

    except KeyboardInterrupt:
        # Parent interrupted: ensure child process is killed before propagating
        if proc.is_alive():
            _escalate_kill_process(proc)
        raise

    finally:
        # Guarantee child process is dead and joined
        if proc.is_alive():
            _escalate_kill_process(proc)
        # Clean up IPC queue resources
        try:
            result_queue.cancel_join_thread()
            result_queue.close()
        except Exception:
            pass

    # 8. Unpack and evaluate worker payload
    if not isinstance(payload, dict):
        raise PDFWorkerCrashError("Worker delivered invalid non-dictionary payload.")

    status = payload.get("status")
    if status == "success":
        elapsed_total_ms = (time.monotonic() - start_monotonic) * 1000.0
        return PDFExtractionResult(
            text=payload["text"],
            page_count=payload["page_count"],
            character_count=payload["character_count"],
            metadata=payload["metadata"],
            extraction_time_ms=elapsed_total_ms,
            startup_latency_ms=startup_latency_ms,
        )

    if status == "encrypted":
        raise PDFEncryptedError(
            "Password-protected or encrypted PDFs are not supported for extraction."
        )

    if status == "malformed":
        raise PDFMalformedError(
            payload.get("error", "Malformed PDF structure.")
        )

    # General extraction failure
    raise PDFMalformedError(
        payload.get("error", "Unknown extraction failure.")
    )
