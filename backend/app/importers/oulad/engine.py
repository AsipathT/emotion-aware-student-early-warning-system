"""
backend/app/importers/oulad/engine.py

Feature 26: High-Performance OULAD Ingestion and Rollback Engine.
Uses SYNCHRONOUS PyMongo with tz_aware=True.
Provides:
  - Fast CSV parsing and schema validation.
  - Chunked streaming for large files (studentVle.csv).
  - Bulk upserts for small collections and bulk unordered inserts for activity_events.
  - Deterministic sampling and module filtering.
  - Idempotent execution and complete rollback capabilities.
  - Ingestion run tracking and audit logging.
"""

import csv
import io
import logging
import random
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Dict, Generator, List, Optional, Set, Tuple, Union

from pydantic import ValidationError
from pymongo import MongoClient, UpdateOne
from pymongo.errors import BulkWriteError, OperationFailure

from app.core.config import settings
from app.db import collections as col
from app.db.storage_models import (
    ActivityEventStorage,
    AssignmentStorage,
    CourseStorage,
    CourseWeekStorage,
    EnrolmentStorage,
    GradeStorage,
    IdentityVaultStorage,
    IngestionRunStorage,
    SubmissionStorage,
)
from app.importers.oulad import mappings
from app.schemas.audit import AuditAction, AuditLogBase, AuditOutcome

logger = logging.getLogger("app.importers.oulad")

# Expected CSV file headers for early validation
REQUIRED_CSV_HEADERS: Dict[str, Set[str]] = {
    "courses.csv": {"code_module", "code_presentation", "module_presentation_length"},
    "vle.csv": {"id_site", "code_module", "code_presentation", "activity_type"},
    "studentRegistration.csv": {"code_module", "code_presentation", "id_student", "date_registration", "date_unregistration"},
    "studentInfo.csv": {"code_module", "code_presentation", "id_student", "final_result"},
    "assessments.csv": {"code_module", "code_presentation", "id_assessment", "assessment_type", "date", "weight"},
    "studentAssessment.csv": {"id_assessment", "id_student", "date_submitted", "is_banked", "score"},
    "studentVle.csv": {"code_module", "code_presentation", "id_student", "id_site", "date", "sum_click"},
}

TARGET_IMPORT_COLLECTIONS = (
    col.IDENTITY_VAULT,
    col.COURSES,
    col.COURSE_WEEKS,
    col.ENROLMENTS,
    col.ASSIGNMENTS,
    col.SUBMISSIONS,
    col.GRADES,
    col.ACTIVITY_EVENTS,
    col.INGESTION_RUNS,
)


class OuladImportEngine:
    """Ingestion engine managing OULAD dataset loading and rollback."""

    def __init__(
        self,
        data_dir: Path,
        mongo_uri: Optional[str] = None,
        db_name: Optional[str] = None,
        chunk_size: int = 50000,
        sample_size: Optional[int] = None,
        seed: int = 42,
        modules: Optional[List[str]] = None,
        dry_run: bool = False,
    ):
        self.data_dir = Path(data_dir).resolve()
        self.mongo_uri = mongo_uri or settings.mongo_uri
        self.db_name = db_name or settings.mongo_db_name
        self.chunk_size = max(100, int(chunk_size))
        self.sample_size = sample_size
        self.seed = seed
        self.modules = [m.strip() for m in modules] if modules else None
        self.dry_run = dry_run

        self.client: Optional[MongoClient] = None
        self.db: Any = None
        self.run_id = f"oulad_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:6]}"

        # Run statistics
        self.stats: Dict[str, Any] = {
            "run_id": self.run_id,
            "started_at": datetime.now(timezone.utc),
            "ended_at": None,
            "duration_seconds": 0.0,
            "dry_run": self.dry_run,
            "collections_written": {},
            "records_skipped_duplicate": 0,
            "records_beyond_course_length": 0,
            "rejected_records": {},
            "total_records_processed": 0,
            "sampled_students_count": None,
        }

    # ── Database Connection ───────────────────────────────────────────────────

    def connect(self) -> None:
        """Establishes synchronous MongoClient connection with tz_aware=True."""
        if not self.dry_run:
            self.client = MongoClient(self.mongo_uri, tz_aware=True)
            self.db = self.client[self.db_name]

    def close(self) -> None:
        """Closes MongoDB connection."""
        if self.client:
            self.client.close()
            self.client = None

    # ── Header Validation ─────────────────────────────────────────────────────

    def validate_headers(self) -> None:
        """Inspects all required CSV files and verifies expected column headers."""
        if not self.data_dir.exists() or not self.data_dir.is_dir():
            raise FileNotFoundError(f"Specified OULAD directory does not exist: {self.data_dir}")

        missing_files: List[str] = []
        header_errors: List[str] = []

        for filename, expected_headers in REQUIRED_CSV_HEADERS.items():
            file_path = self.data_dir / filename
            if not file_path.exists():
                missing_files.append(filename)
                continue

            with open(file_path, "r", encoding="utf-8-sig") as f:
                reader = csv.reader(f)
                headers = next(reader, None)
                if not headers:
                    header_errors.append(f"{filename}: File is empty.")
                    continue

                clean_headers = {h.strip() for h in headers if h}
                missing_cols = expected_headers - clean_headers
                if missing_cols:
                    header_errors.append(f"{filename}: Missing required column(s): {sorted(missing_cols)}")

        if missing_files:
            raise FileNotFoundError(f"Missing required OULAD CSV files in {self.data_dir}: {missing_files}")

        if header_errors:
            raise ValueError(f"OULAD CSV header validation failed:\n" + "\n".join(header_errors))

    # ── CSV Helper Readers ────────────────────────────────────────────────────

    def _read_csv(self, filename: str) -> List[Dict[str, str]]:
        """Reads small CSV file into memory with clean string values."""
        file_path = self.data_dir / filename
        rows: List[Dict[str, str]] = []
        with open(file_path, "r", encoding="utf-8-sig") as f:
            reader = csv.DictReader(f)
            for raw_row in reader:
                row = {k.strip(): (v.strip() if v is not None else "") for k, v in raw_row.items() if k}
                rows.append(row)
        return rows

    def _stream_csv_chunks(self, filename: str) -> Generator[List[Dict[str, str]], None, None]:
        """Streams large CSV file in configurable chunks."""
        file_path = self.data_dir / filename
        with open(file_path, "r", encoding="utf-8-sig") as f:
            reader = csv.DictReader(f)
            chunk: List[Dict[str, str]] = []
            for raw_row in reader:
                row = {k.strip(): (v.strip() if v is not None else "") for k, v in raw_row.items() if k}
                chunk.append(row)
                if len(chunk) >= self.chunk_size:
                    yield chunk
                    chunk = []
            if chunk:
                yield chunk

    # ── Validation & Rejection Recording ──────────────────────────────────────

    def _validate_record(self, model_cls: Any, doc: Dict[str, Any]) -> bool:
        """Validates a document against its Pydantic storage model."""
        try:
            model_cls.model_validate(doc)
            return True
        except ValidationError as val_err:
            reason = f"{model_cls.__name__}: {val_err.errors()[0].get('msg', 'validation error')} at {val_err.errors()[0].get('loc')}"
            self.stats["rejected_records"][reason] = self.stats["rejected_records"].get(reason, 0) + 1
            return False

    # ── Bulk Writing Helpers ──────────────────────────────────────────────────

    def _bulk_upsert(self, collection_name: str, operations: List[UpdateOne], batch_size: int = 5000) -> int:
        """Executes unordered bulk upserts on small collections."""
        if not operations or self.dry_run:
            return len(operations)

        total_upserted = 0
        for i in range(0, len(operations), batch_size):
            batch = operations[i : i + batch_size]
            if not batch:
                continue
            res = self.db[collection_name].bulk_write(batch, ordered=False)
            total_upserted += (res.upserted_count + res.modified_count + res.matched_count)
        return total_upserted

    def _bulk_insert_activity_events(self, docs: List[Dict[str, Any]], batch_size: int = 5000) -> Tuple[int, int]:
        """
        Inserts activity events in unordered batches.
        Treats duplicate-key errors as already-loaded documents.
        """
        if not docs or self.dry_run:
            return len(docs), 0

        inserted = 0
        duplicates = 0
        for i in range(0, len(docs), batch_size):
            batch = docs[i : i + batch_size]
            if not batch:
                continue
            try:
                res = self.db[col.ACTIVITY_EVENTS].insert_many(batch, ordered=False)
                inserted += len(res.inserted_ids)
            except BulkWriteError as bwe:
                write_errors = bwe.details.get("writeErrors", [])
                dup_count = sum(1 for err in write_errors if err.get("code") == 11000)
                duplicates += dup_count
                inserted += bwe.details.get("nInserted", 0)
                non_dup_errors = [err for err in write_errors if err.get("code") != 11000]
                if non_dup_errors:
                    raise
        return inserted, duplicates

    # ── Execution Logic ───────────────────────────────────────────────────────

    def run_import(self) -> Dict[str, Any]:
        """Executes full OULAD ingestion workflow."""
        start_time = time.time()
        self.validate_headers()
        self.connect()

        try:
            # 1. Load small CSVs
            courses_raw = self._read_csv("courses.csv")
            vle_raw = self._read_csv("vle.csv")
            reg_raw = self._read_csv("studentRegistration.csv")
            info_raw = self._read_csv("studentInfo.csv")
            assessments_raw = self._read_csv("assessments.csv")
            student_assessments_raw = self._read_csv("studentAssessment.csv")

            # 2. Module Filtering
            if self.modules:
                allowed_modules = set(self.modules)
                courses_raw = [c for c in courses_raw if c.get("code_module") in allowed_modules]
                vle_raw = [v for v in vle_raw if v.get("code_module") in allowed_modules]
                reg_raw = [r for r in reg_raw if r.get("code_module") in allowed_modules]
                info_raw = [inf for inf in info_raw if inf.get("code_module") in allowed_modules]
                assessments_raw = [a for a in assessments_raw if a.get("code_module") in allowed_modules]

            # 3. Deterministic Student Sampling
            allowed_student_ids: Optional[Set[str]] = None
            if self.sample_size is not None and self.sample_size > 0:
                all_student_ids = sorted(list({r["id_student"] for r in info_raw if r.get("id_student")}))
                rng = random.Random(self.seed)
                sampled = rng.sample(all_student_ids, min(self.sample_size, len(all_student_ids)))
                allowed_student_ids = set(sampled)
                self.stats["sampled_students_count"] = len(sampled)

                # Filter student-bound data
                reg_raw = [r for r in reg_raw if r.get("id_student") in allowed_student_ids]
                info_raw = [inf for inf in info_raw if inf.get("id_student") in allowed_student_ids]
                student_assessments_raw = [sa for sa in student_assessments_raw if sa.get("id_student") in allowed_student_ids]

            # 4. In-Memory Lookups
            # Course presentation length map: (code_module, code_presentation) -> length
            presentation_lengths: Dict[Tuple[str, str], int] = {}
            for c in courses_raw:
                key = (c["code_module"], c["code_presentation"])
                try:
                    presentation_lengths[key] = int(c.get("module_presentation_length", 268))
                except ValueError:
                    presentation_lengths[key] = 268

            # VLE lookup: (code_module, code_presentation, id_site) -> activity_type
            vle_lookup: Dict[Tuple[str, str, str], str] = {}
            for v in vle_raw:
                v_key = (v["code_module"], v["code_presentation"], str(v["id_site"]).strip())
                vle_lookup[v_key] = v.get("activity_type", "resource")

            # Info lookup for ground truth: (code_module, code_presentation, id_student) -> final_result
            info_lookup: Dict[Tuple[str, str, str], str] = {}
            unique_students: Set[str] = set()
            for inf in info_raw:
                inf_key = (inf["code_module"], inf["code_presentation"], str(inf["id_student"]).strip())
                info_lookup[inf_key] = inf.get("final_result", "")
                unique_students.add(str(inf["id_student"]).strip())

            # Assessments lookup: (id_assessment) -> assessment_dict
            assessment_lookup: Dict[str, Dict[str, str]] = {
                str(a["id_assessment"]).strip(): a for a in assessments_raw
            }

            # ── 5. Process Courses & Course Weeks ─────────────────────────────
            course_ops: List[UpdateOne] = []
            week_ops: List[UpdateOne] = []
            for c in courses_raw:
                mod = c["code_module"]
                pres = c["code_presentation"]
                length = presentation_lengths.get((mod, pres), 268)

                course_doc = mappings.build_course_doc(mod, pres, length, self.run_id)
                if self._validate_record(CourseStorage, course_doc):
                    course_ops.append(UpdateOne({"course_id": course_doc["course_id"]}, {"$set": course_doc}, upsert=True))

                week_docs = mappings.build_course_week_docs(mod, pres, length, self.run_id)
                for wdoc in week_docs:
                    if self._validate_record(CourseWeekStorage, wdoc):
                        week_ops.append(UpdateOne(
                            {"course_id": wdoc["course_id"], "week_index": wdoc["week_index"]},
                            {"$set": wdoc},
                            upsert=True,
                        ))

            courses_count = self._bulk_upsert(col.COURSES, course_ops)
            weeks_count = self._bulk_upsert(col.COURSE_WEEKS, week_ops)
            self.stats["collections_written"][col.COURSES] = courses_count
            self.stats["collections_written"][col.COURSE_WEEKS] = weeks_count

            # ── 6. Process Identity Vault ─────────────────────────────────────
            vault_ops: List[UpdateOne] = []
            for stu_id in unique_students:
                vault_doc = mappings.build_identity_vault_doc(stu_id, self.run_id)
                if self._validate_record(IdentityVaultStorage, vault_doc):
                    vault_ops.append(UpdateOne({"pid": vault_doc["pid"]}, {"$set": vault_doc}, upsert=True))

            vault_count = self._bulk_upsert(col.IDENTITY_VAULT, vault_ops)
            self.stats["collections_written"][col.IDENTITY_VAULT] = vault_count

            # ── 7. Process Enrolments ─────────────────────────────────────────
            enrolment_ops: List[UpdateOne] = []
            for r in reg_raw:
                mod = r["code_module"]
                pres = r["code_presentation"]
                stu_id = str(r["id_student"]).strip()
                final_result = info_lookup.get((mod, pres, stu_id), "")

                enr_doc = mappings.build_enrolment_doc(
                    code_module=mod,
                    code_presentation=pres,
                    id_student=stu_id,
                    date_registration=r.get("date_registration"),
                    date_unregistration=r.get("date_unregistration"),
                    final_result=final_result,
                    run_id=self.run_id,
                )
                if self._validate_record(EnrolmentStorage, enr_doc):
                    enrolment_ops.append(UpdateOne(
                        {"pid": enr_doc["pid"], "course_id": enr_doc["course_id"]},
                        {"$set": enr_doc},
                        upsert=True,
                    ))

            enr_count = self._bulk_upsert(col.ENROLMENTS, enrolment_ops)
            self.stats["collections_written"][col.ENROLMENTS] = enr_count

            # ── 8. Process Assignments ────────────────────────────────────────
            asg_ops: List[UpdateOne] = []
            for a in assessments_raw:
                mod = a["code_module"]
                pres = a["code_presentation"]
                length = presentation_lengths.get((mod, pres), 268)

                asg_doc = mappings.build_assignment_doc(
                    code_module=mod,
                    code_presentation=pres,
                    id_assessment=a["id_assessment"],
                    assessment_type=a["assessment_type"],
                    date=a.get("date"),
                    weight=a.get("weight"),
                    presentation_length=length,
                    run_id=self.run_id,
                )
                if self._validate_record(AssignmentStorage, asg_doc):
                    asg_ops.append(UpdateOne(
                        {"assignment_id": asg_doc["assignment_id"], "course_id": asg_doc["course_id"]},
                        {"$set": asg_doc},
                        upsert=True,
                    ))

            asg_count = self._bulk_upsert(col.ASSIGNMENTS, asg_ops)
            self.stats["collections_written"][col.ASSIGNMENTS] = asg_count

            # ── 9. Process Submissions & Grades ───────────────────────────────
            sub_ops: List[UpdateOne] = []
            grd_ops: List[UpdateOne] = []
            for sa in student_assessments_raw:
                asg_id = str(sa["id_assessment"]).strip()
                asg_meta = assessment_lookup.get(asg_id)
                if not asg_meta:
                    continue

                mod = asg_meta["code_module"]
                pres = asg_meta["code_presentation"]
                stu_id = str(sa["id_student"]).strip()
                length = presentation_lengths.get((mod, pres), 268)

                # Build Submission
                sub_doc = mappings.build_submission_doc(
                    code_module=mod,
                    code_presentation=pres,
                    id_assessment=asg_id,
                    id_student=stu_id,
                    date_submitted=sa.get("date_submitted"),
                    is_banked=sa.get("is_banked"),
                    score=sa.get("score"),
                    assessment_date=asg_meta.get("date"),
                    run_id=self.run_id,
                )
                if self._validate_record(SubmissionStorage, sub_doc):
                    sub_ops.append(UpdateOne(
                        {"submission_id": sub_doc["submission_id"]},
                        {"$set": sub_doc},
                        upsert=True,
                    ))

                # Build Grade
                grd_doc = mappings.build_grade_doc(
                    code_module=mod,
                    code_presentation=pres,
                    id_assessment=asg_id,
                    id_student=stu_id,
                    date_submitted=sa.get("date_submitted"),
                    score=sa.get("score"),
                    weight=asg_meta.get("weight"),
                    assessment_date=asg_meta.get("date"),
                    presentation_length=length,
                    run_id=self.run_id,
                )
                if self._validate_record(GradeStorage, grd_doc):
                    grd_ops.append(UpdateOne(
                        {"pid": grd_doc["pid"], "course_id": grd_doc["course_id"], "assessment_id": grd_doc["assessment_id"]},
                        {"$set": grd_doc},
                        upsert=True,
                    ))

            sub_count = self._bulk_upsert(col.SUBMISSIONS, sub_ops)
            grd_count = self._bulk_upsert(col.GRADES, grd_ops)
            self.stats["collections_written"][col.SUBMISSIONS] = sub_count
            self.stats["collections_written"][col.GRADES] = grd_count

            # ── 10. Stream and Process studentVle.csv in Chunks ───────────────
            total_activity_events = 0
            total_vle_dups = 0

            for chunk in self._stream_csv_chunks("studentVle.csv"):
                # Filter chunk by modules and sampled students
                if self.modules:
                    chunk = [row for row in chunk if row.get("code_module") in allowed_modules]
                if allowed_student_ids:
                    chunk = [row for row in chunk if row.get("id_student") in allowed_student_ids]

                if not chunk:
                    continue

                # In-chunk aggregation for identical (pid, course, site, day)
                chunk_aggregated: Dict[Tuple[str, str, str, int], int] = {}
                chunk_meta: Dict[Tuple[str, str, str, int], Tuple[str, str, str, int]] = {}

                for row in chunk:
                    mod = row["code_module"]
                    pres = row["code_presentation"]
                    stu_id = str(row["id_student"]).strip()
                    site_id = str(row["id_site"]).strip()
                    try:
                        day = int(row.get("date", 0))
                        clicks = int(row.get("sum_click", 1))
                    except ValueError:
                        continue

                    pid = mappings.oulad_pid(stu_id)
                    course_id = f"{mod}_{pres}"
                    agg_key = (pid, course_id, site_id, day)

                    chunk_aggregated[agg_key] = chunk_aggregated.get(agg_key, 0) + clicks
                    chunk_meta[agg_key] = (mod, pres, stu_id, day)

                # Build event documents
                event_docs: List[Dict[str, Any]] = []
                for agg_key, total_clicks in chunk_aggregated.items():
                    pid, course_id, site_id, day = agg_key
                    mod, pres, stu_id, _ = chunk_meta[agg_key]
                    length = presentation_lengths.get((mod, pres), 268)
                    act_type = vle_lookup.get((mod, pres, site_id), "resource")

                    ev_doc, is_beyond = mappings.build_activity_event_doc(
                        code_module=mod,
                        code_presentation=pres,
                        id_student=stu_id,
                        id_site=site_id,
                        day=day,
                        sum_click=total_clicks,
                        activity_type=act_type,
                        presentation_length=length,
                        run_id=self.run_id,
                    )
                    if is_beyond:
                        self.stats["records_beyond_course_length"] += 1

                    if self._validate_record(ActivityEventStorage, ev_doc):
                        event_docs.append(ev_doc)

                # Flush activity events batch
                ins_count, dup_count = self._bulk_insert_activity_events(event_docs)
                total_activity_events += ins_count
                total_vle_dups += dup_count

            self.stats["collections_written"][col.ACTIVITY_EVENTS] = total_activity_events
            self.stats["records_skipped_duplicate"] += total_vle_dups

            # Total processed across all target collections
            total_records = sum(self.stats["collections_written"].values())
            self.stats["total_records_processed"] = total_records
            self.stats["ended_at"] = datetime.now(timezone.utc)
            self.stats["duration_seconds"] = round(time.time() - start_time, 2)

            # ── 11. Record Run Summary in ingestion_runs & audit_logs ─────────
            if not self.dry_run:
                self._record_ingestion_summary(status="completed")
                self._record_audit_log(AuditAction.DATA_IMPORTED, outcome=AuditOutcome.SUCCESS)

            return self.stats

        except Exception as exc:
            self.stats["ended_at"] = datetime.now(timezone.utc)
            self.stats["duration_seconds"] = round(time.time() - start_time, 2)
            if not self.dry_run:
                self._record_ingestion_summary(status="failed", error_message=str(exc))
                self._record_audit_log(AuditAction.DATA_IMPORTED, outcome=AuditOutcome.FAILED, reason=f"Import error: {str(exc)[:100]}")
            raise
        finally:
            self.close()

    # ── Rollback Engine ───────────────────────────────────────────────────────

    def rollback(self) -> Dict[str, int]:
        """
        Deletes all documents tagged with source='oulad' from target collections.
        Audit logs and consent records are never deleted.
        """
        start_time = time.time()
        self.connect()
        deleted_counts: Dict[str, int] = {}

        try:
            filter_query = {"source": mappings.SOURCE_TAG}
            collections_to_clean = (
                col.ACTIVITY_EVENTS,
                col.GRADES,
                col.SUBMISSIONS,
                col.ASSIGNMENTS,
                col.ENROLMENTS,
                col.COURSE_WEEKS,
                col.COURSES,
                col.IDENTITY_VAULT,
                col.INGESTION_RUNS,
            )

            for col_name in collections_to_clean:
                if self.dry_run:
                    count = self.db[col_name].count_documents(filter_query) if self.db else 0
                else:
                    res = self.db[col_name].delete_many(filter_query)
                    count = res.deleted_count
                deleted_counts[col_name] = count

            if not self.dry_run:
                self._record_audit_log(
                    AuditAction.DATA_ROLLBACK,
                    outcome=AuditOutcome.SUCCESS,
                    reason="OULAD dataset batch rollback",
                    details={"deleted_counts": deleted_counts},
                )

            return deleted_counts
        finally:
            self.close()

    # ── Administrative & Audit Logging ────────────────────────────────────────

    def _record_ingestion_summary(self, status: str = "completed", error_message: Optional[str] = None) -> None:
        """Writes ingestion run summary document into ingestion_runs."""
        summary_doc = {
            "_id": f"run_{self.run_id}",
            "run_id": self.run_id,
            "component": "oulad_importer",
            "started_at": self.stats["started_at"],
            "ended_at": self.stats["ended_at"],
            "status": status,
            "records_processed": self.stats["total_records_processed"],
            "error_message": error_message,
            "details": {
                "collections_written": self.stats["collections_written"],
                "records_skipped_duplicate": self.stats["records_skipped_duplicate"],
                "records_beyond_course_length": self.stats["records_beyond_course_length"],
                "rejected_records": self.stats["rejected_records"],
                "duration_seconds": self.stats["duration_seconds"],
                "dry_run": self.dry_run,
            },
            "dry_run": self.dry_run,
            "source": mappings.SOURCE_TAG,
            "ingestion_run_id": self.run_id,
            "schema_version": 1,
            "ingested_at": datetime.now(timezone.utc),
            "source_version": "1.0",
        }
        self.db[col.INGESTION_RUNS].insert_one(summary_doc)

    def _record_audit_log(
        self,
        action: AuditAction,
        outcome: AuditOutcome,
        reason: str = "OULAD operation",
        details: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Persists audit log entry without requiring an HTTP request."""
        clean_details = details or {
            "run_id": self.run_id,
            "collections_written": self.stats.get("collections_written"),
            "total_records": self.stats.get("total_records_processed"),
        }
        audit_entry = AuditLogBase(
            id=str(uuid.uuid4()),
            timestamp=datetime.now(timezone.utc),
            actor_id="system:oulad_importer",
            actor_role="system",
            action=action,
            target_type="dataset",
            target_id="oulad",
            outcome=outcome,
            reason=reason,
            ip_address="127.0.0.1",
            user_agent="cli/oulad_importer",
            request_id=str(uuid.uuid4()),
            details=clean_details,
            schema_version=1,
        )
        doc = audit_entry.model_dump(by_alias=True)
        doc["_id"] = audit_entry.id
        doc["id"] = audit_entry.id
        doc["timestamp"] = audit_entry.timestamp
        self.db[col.AUDIT_LOGS].insert_one(doc)
