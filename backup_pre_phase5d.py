"""
Gyaan AI - Phase 5D Pre-Implementation Atomic SQLite Backup Utility.

Authoritative standalone backup script. Creates an atomic, transaction-consistent
online backup of data/gyaan_ai.db into data/backups/gyaan_ai_pre_phase5d_backup.db
using SQLite native online backup API, exclusive OS reservation handoff,
full schema and 23-table row-count parity verification, and strict no-overwrite
atomic promotion.
"""

import os
import sqlite3
import sys
from pathlib import Path


def execute_atomic_backup() -> bool:
    print("=" * 60)
    print("       GYAAN AI - PRE-PHASE 5D ATOMIC SQLITE BACKUP         ")
    print("=" * 60)

    # 1. Path definitions using Pathlib
    source_file = Path("data/gyaan_ai.db").resolve()
    backup_dir = Path("data/backups").resolve()
    final_backup_file = (backup_dir / "gyaan_ai_pre_phase5d_backup.db").resolve()
    temp_backup_file = (backup_dir / "gyaan_ai_pre_phase5d_backup.tmp.db").resolve()

    # 2. Source database existence verification
    if not source_file.is_file():
        raise FileNotFoundError(f"ABORTED: Source database not found at '{source_file}'.")

    # 3. Verify backup directory resides on the same filesystem volume
    if source_file.drive.lower() != backup_dir.drive.lower():
        raise ValueError(
            f"ABORTED: Backup directory drive '{backup_dir.drive}' differs from source drive '{source_file.drive}'. "
            "Cross-volume atomic renames are not supported."
        )

    # 4. Refuse to overwrite an existing final backup
    if final_backup_file.exists():
        final_size = final_backup_file.stat().st_size
        raise FileExistsError(
            f"ABORTED: Final backup already exists at '{final_backup_file}' ({final_size:,} bytes). "
            "Automated overwrite is prohibited. Backup cancelled."
        )

    # 5. Check whether temporary backup already exists
    if temp_backup_file.exists():
        temp_size = temp_backup_file.stat().st_size
        raise FileExistsError(
            f"ABORTED: A temporary backup file already exists at '{temp_backup_file}' ({temp_size:,} bytes). "
            "Automated deletion or overwrite is prohibited. Please inspect and resolve this file before proceeding."
        )

    # Ensure backup directory exists
    backup_dir.mkdir(parents=True, exist_ok=True)

    # Ensure temp and final backups reside in the exact same directory for atomic rename
    if temp_backup_file.parent != final_backup_file.parent:
        raise ValueError("ABORTED: Temporary and final backup paths must reside in the exact same directory.")

    reservation_handle = None
    src_conn = None
    temp_conn = None

    try:
        # 6. Reserve temporary filename exclusively (mode 'xb' via OS CREATE_NEW / O_CREAT | O_EXCL)
        # The reservation handle is kept OPEN while SQLite connects to eliminate TOCTOU gaps.
        try:
            reservation_handle = open(temp_backup_file, "xb")
        except FileExistsError:
            temp_size = temp_backup_file.stat().st_size if temp_backup_file.exists() else 0
            raise FileExistsError(
                f"ABORTED: Exclusive reservation failed. File appeared concurrently at '{temp_backup_file}' "
                f"({temp_size:,} bytes). Overwriting is prohibited."
            )

        # 7. Construct Windows-safe read-only SQLite URI with URL-encoded spaces
        source_uri = f"{source_file.as_uri()}?mode=ro"

        # 8. Open source database in strictly read-only URI mode
        src_conn = sqlite3.connect(source_uri, uri=True)
        src_cur = src_conn.cursor()

        # 9. Run source integrity check
        src_cur.execute("PRAGMA integrity_check;")
        src_integrity = src_cur.fetchone()[0]
        if src_integrity != "ok":
            raise RuntimeError(f"ABORTED: Source database failed integrity check: {src_integrity}")

        # 10. Dynamically capture source schema definitions (tables, indexes, triggers)
        src_cur.execute("SELECT type, name, sql FROM sqlite_master WHERE sql IS NOT NULL ORDER BY type, name;")
        src_schema = src_cur.fetchall()

        # Dynamically capture source table names
        src_cur.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name;")
        src_tables = [r[0] for r in src_cur.fetchall()]
        src_table_count = len(src_tables)

        # 11. Capture key metric row counts
        src_cur.execute("SELECT COUNT(*) FROM students;")
        src_students = src_cur.fetchone()[0]

        src_cur.execute("SELECT COUNT(*) FROM student_sessions;")
        src_auth_sessions = src_cur.fetchone()[0]

        src_cur.execute("SELECT COUNT(*) FROM learning_sessions;")
        src_learning_sessions = src_cur.fetchone()[0]

        # Dynamically record row counts for all 23 tables
        src_table_counts = {}
        for tbl in src_tables:
            src_cur.execute(f'SELECT COUNT(*) FROM "{tbl}";')
            src_table_counts[tbl] = src_cur.fetchone()[0]

        source_size = source_file.stat().st_size
        print(f"Source Database Verified: {source_file} ({source_size:,} bytes)")
        print(f"  Integrity Status   : {src_integrity}")
        print(f"  Total Tables       : {src_table_count}")
        print(f"  Registered Students: {src_students:,}")
        print(f"  Auth Sessions      : {src_auth_sessions:,}")
        print(f"  Learning Sessions  : {src_learning_sessions:,}")

        # 12. Connect SQLite to temporary backup file WHILE reservation handle remains open
        # Windows allows this because Python CRT uses _SH_DENYNO and SQLite uses FILE_SHARE_READ | FILE_SHARE_WRITE
        temp_conn = sqlite3.connect(str(temp_backup_file))

        # 13. Safely release reservation handle now that SQLite holds the file open
        reservation_handle.close()
        reservation_handle = None

        # 14. Stream online backup using SQLite native backup API
        with temp_conn:
            src_conn.backup(temp_conn, pages=-1)

        print(f"Online backup stream completed to temporary file: {temp_backup_file}")

    finally:
        # Guarantee reservation handle closes if an exception occurred before handoff
        if reservation_handle is not None:
            try:
                reservation_handle.close()
            except Exception:
                pass
            reservation_handle = None

        # Guarantee both backup stream connections close before independent verification
        if temp_conn is not None:
            try:
                temp_conn.close()
            except Exception:
                pass
            temp_conn = None
        if src_conn is not None:
            try:
                src_conn.close()
            except Exception:
                pass
            src_conn = None

    # At this point, backup stream connections are 100% closed.
    verify_conn = None
    try:
        # 15. Open temporary backup in read-only URI mode for independent verification
        temp_uri = f"{temp_backup_file.as_uri()}?mode=ro"
        verify_conn = sqlite3.connect(temp_uri, uri=True)
        verify_cur = verify_conn.cursor()

        # 16. Verify temporary backup integrity independently
        verify_cur.execute("PRAGMA integrity_check;")
        dst_integrity = verify_cur.fetchone()[0]
        if dst_integrity != "ok":
            raise RuntimeError(f"ABORTED: Temporary backup failed integrity check: {dst_integrity}")

        # 17. Verify exact schema definition parity (all tables, indexes, triggers)
        verify_cur.execute("SELECT type, name, sql FROM sqlite_master WHERE sql IS NOT NULL ORDER BY type, name;")
        dst_schema = verify_cur.fetchall()
        if dst_schema != src_schema:
            raise AssertionError("ABORTED: Schema definition parity mismatch between source and backup!")

        # 18. Verify exact table-name parity
        verify_cur.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name;")
        dst_tables = [r[0] for r in verify_cur.fetchall()]
        if dst_tables != src_tables:
            missing = set(src_tables) - set(dst_tables)
            extra = set(dst_tables) - set(src_tables)
            raise AssertionError(f"ABORTED: Table parity mismatch! Missing: {missing}, Extra: {extra}")

        # 19. Verify full-table row count parity across all 23 tables
        for tbl in src_tables:
            verify_cur.execute(f'SELECT COUNT(*) FROM "{tbl}";')
            dst_cnt = verify_cur.fetchone()[0]
            if dst_cnt != src_table_counts[tbl]:
                raise AssertionError(
                    f"ABORTED: Row count parity failed on table '{tbl}'! Source={src_table_counts[tbl]}, Backup={dst_cnt}"
                )

        temp_size = temp_backup_file.stat().st_size
        print("Parity Verification PASSED:")
        print(f"  Source Size: {source_size:,} bytes | Temp Backup Size: {temp_size:,} bytes")
        print(f"  Schema Parity: 100% match across {len(dst_schema)} database objects")
        print(f"  Tables Verified: {len(dst_tables)}/{src_table_count} match")
        print(f"  Row Counts Verified: 100% match across all {len(src_tables)} tables")
        print(f"  Students: {src_students:,} | Auth Sessions: {src_auth_sessions:,} | Learning Sessions: {src_learning_sessions:,}")

    finally:
        # Guarantee verification connection closes cleanly before promotion
        if verify_conn is not None:
            try:
                verify_conn.close()
            except Exception:
                pass
            verify_conn = None

    # At this point, ALL database connections and file handles are completely closed.
    # 20. Promote temporary backup using safe no-overwrite rename
    if final_backup_file.exists():
        final_size = final_backup_file.stat().st_size
        raise FileExistsError(
            f"ABORTED: Final backup path '{final_backup_file}' appeared unexpectedly before rename. "
            f"Temporary verified backup preserved at '{temp_backup_file}'."
        )

    # os.rename refuses to overwrite on Windows if destination exists
    os.rename(str(temp_backup_file), str(final_backup_file))
    final_size = final_backup_file.stat().st_size

    # 21. Preserve original database under all circumstances
    print("=" * 60)
    print("       ATOMIC BACKUP SUCCESSFULLY PROMOTED & VERIFIED       ")
    print("=" * 60)
    print(f"  Final Backup File : {final_backup_file} ({final_size:,} bytes)")
    print(f"  Source Database   : {source_file} (UNTOUCHED, {source_size:,} bytes)")
    print("=" * 60)
    return True


if __name__ == "__main__":
    try:
        execute_atomic_backup()
    except Exception as exc:
        print("!" * 60)
        print(f"BACKUP FAILED: {exc}")
        print("SAFETY GUARANTEE: Original source database was NOT modified.")
        temp_check = Path("data/backups/gyaan_ai_pre_phase5d_backup.tmp.db")
        if temp_check.exists():
            print(f"SAFETY NOTICE: Temporary file preserved for inspection at '{temp_check.resolve()}'.")
        print("!" * 60)
        sys.exit(1)
