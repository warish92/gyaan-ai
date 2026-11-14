"""Gyaan AI - Observability In-Memory Bounded Telemetry Store.

Provides a thread-safe, bounded in-memory ring-buffer store for traces, spans, and events.
Never modifies or impacts the primary SQLite student database (data/gyaan_ai.db).
Guarantees privacy-conscious pseudonymization of student identifiers.
"""

from __future__ import annotations

from collections import deque
from datetime import datetime, timezone
import threading
from typing import Any, Dict, List, Optional

from backend.observability.redaction import pseudonymize_student_id, redact_sensitive_data
from backend.observability.schemas import (
    AgentStatusRecord,
    ObservabilityEvent,
    ObservabilityMetrics,
    SpanRecord,
    TraceRecord,
)

CANONICAL_AGENTS = [
    ("Orchestrator Agent", "Intent classification, routing, and lifecycle coordination"),
    ("Diagnostic Agent", "Prerequisite gap detection and diagnostic evaluations"),
    ("Curriculum Agent", "NCERT Class 10 curriculum alignment and sequential roadmap"),
    ("Resource Agent", "Verified textbook corpora and MCP research tool execution"),
    ("Teacher Agent", "Pedagogical concept explanation and step-by-step tutoring"),
    ("Assessment Agent", "Bloom's taxonomy quiz generation and scoring"),
    ("Progress Agent", "Mastery updates, learning velocity, and milestone tracking"),
    ("Mentor Agent", "Metacognitive motivation, study habit guidance, and feedback"),
    ("Learning Intelligence Agent (ADK)", "Deep learning trajectory and session intelligence"),
]


class ObservabilityStore:
    """Thread-safe bounded in-memory store for traces and observability events."""

    def __init__(self, max_traces: int = 1000, max_events: int = 5000) -> None:
        self.max_traces = max_traces
        self.max_events = max_events
        self._lock = threading.Lock()
        self._traces_deque: deque[str] = deque(maxlen=max_traces)
        self._traces_map: Dict[str, TraceRecord] = {}
        self._events_deque: deque[ObservabilityEvent] = deque(maxlen=max_events)
        self._errors_deque: deque[Dict[str, Any]] = deque(maxlen=500)

    def save_trace(self, trace: TraceRecord) -> None:
        """Saves or updates a root trace record with pseudonymized student identity."""
        with self._lock:
            # Enforce privacy pseudonymization on student_id
            if trace.student_id:
                trace.student_id = pseudonymize_student_id(trace.student_id)

            # If inserting a new trace and at capacity, evict the oldest from map
            if trace.trace_id not in self._traces_map and len(self._traces_deque) >= self.max_traces:
                evicted_id = self._traces_deque.popleft()
                self._traces_map.pop(evicted_id, None)

            if trace.trace_id not in self._traces_map:
                self._traces_deque.append(trace.trace_id)

            self._traces_map[trace.trace_id] = trace

    def get_trace(self, trace_id: str) -> Optional[TraceRecord]:
        """Retrieves a trace by its unique trace identifier."""
        with self._lock:
            return self._traces_map.get(trace_id)

    def list_traces(
        self,
        limit: int = 50,
        offset: int = 0,
        status: Optional[str] = None,
    ) -> List[TraceRecord]:
        """Returns a paginated list of traces in reverse chronological order."""
        with self._lock:
            # Order newest to oldest
            ordered_ids = list(reversed(self._traces_deque))
            results: List[TraceRecord] = []
            for tid in ordered_ids:
                t = self._traces_map.get(tid)
                if t:
                    if status and t.status.lower() != status.lower():
                        continue
                    results.append(t)

            bounded_limit = min(max(1, limit), 200)
            return results[offset : offset + bounded_limit]

    def add_span_to_trace(self, trace_id: str, span: SpanRecord) -> None:
        """Appends a child span to an existing trace or creates a provisional trace."""
        with self._lock:
            trace = self._traces_map.get(trace_id)
            if not trace:
                trace = TraceRecord(
                    trace_id=trace_id,
                    root_name=span.name,
                    status="started",
                    start_time=span.start_time,
                )
                if len(self._traces_deque) >= self.max_traces:
                    evicted_id = self._traces_deque.popleft()
                    self._traces_map.pop(evicted_id, None)
                self._traces_deque.append(trace_id)
                self._traces_map[trace_id] = trace

            trace.spans.append(span)
            trace.total_spans = len(trace.spans)
            if span.status == "failed":
                trace.error_count += 1
                self._errors_deque.append({
                    "trace_id": trace_id,
                    "span_id": span.span_id,
                    "name": span.name,
                    "agent_name": span.agent_name,
                    "error": redact_sensitive_data(span.error),
                    "error_category": span.error_category,
                    "timestamp": span.end_time or span.start_time,
                })

    def record_event(self, event: ObservabilityEvent) -> None:
        """Appends a point-in-time lifecycle event."""
        with self._lock:
            self._events_deque.append(event)
            if event.level == "ERROR":
                self._errors_deque.append({
                    "event_id": event.event_id,
                    "trace_id": event.trace_id,
                    "span_id": event.span_id,
                    "event_type": event.event_type,
                    "agent_name": event.agent_name,
                    "message": event.message,
                    "payload": redact_sensitive_data(event.payload),
                    "timestamp": event.timestamp,
                })

    def get_events(
        self,
        trace_id: Optional[str] = None,
        limit: int = 100,
    ) -> List[ObservabilityEvent]:
        """Returns recorded events, optionally filtered by trace_id."""
        with self._lock:
            ordered_events = list(reversed(self._events_deque))
            if trace_id:
                ordered_events = [e for e in ordered_events if e.trace_id == trace_id]
            bounded_limit = min(max(1, limit), 500)
            return ordered_events[:bounded_limit]

    def get_errors(self, limit: int = 50) -> List[Dict[str, Any]]:
        """Returns recent recorded errors."""
        with self._lock:
            bounded_limit = min(max(1, limit), 200)
            return list(reversed(self._errors_deque))[:bounded_limit]

    def get_agent_statuses(self) -> List[AgentStatusRecord]:
        """Calculates live operational telemetry for each canonical agent.

        An agent is counted as executed only when its execution span or lifecycle event occurs.
        """
        with self._lock:
            records: List[AgentStatusRecord] = []
            for agent_name, role in CANONICAL_AGENTS:
                agent_spans: List[SpanRecord] = []
                for trace in self._traces_map.values():
                    for s in trace.spans:
                        if s.agent_name and agent_name.lower() in s.agent_name.lower():
                            agent_spans.append(s)

                # Also inspect lifecycle events (e.g. task_complete, crew_kickoff)
                matching_events = [
                    e for e in self._events_deque
                    if e.agent_name and agent_name.lower() in e.agent_name.lower()
                ]

                # Invocation count reflects genuine executions
                total_invocations = max(len(agent_spans), len(matching_events))
                total_errors = sum(1 for s in agent_spans if s.status == "failed")
                total_errors += sum(1 for e in matching_events if e.level == "ERROR")

                durations = [s.duration_ms for s in agent_spans if s.duration_ms is not None]
                avg_duration = sum(durations) / len(durations) if durations else 0.0

                last_active = None
                if agent_spans:
                    sorted_spans = sorted(
                        agent_spans,
                        key=lambda x: x.end_time or x.start_time,
                        reverse=True,
                    )
                    last_active = sorted_spans[0].end_time or sorted_spans[0].start_time
                elif matching_events:
                    last_active = matching_events[-1].timestamp

                status = "idle"
                if agent_spans and agent_spans[-1].status == "started":
                    status = "active"
                elif total_errors > 0 and (total_errors / max(1, total_invocations)) > 0.5:
                    status = "error"
                elif total_invocations > 0:
                    status = "active" if (agent_spans and agent_spans[-1].status == "started") else "idle"

                records.append(
                    AgentStatusRecord(
                        agent_name=agent_name,
                        canonical_role=role,
                        total_invocations=total_invocations,
                        total_errors=total_errors,
                        last_active=last_active,
                        avg_duration_ms=round(avg_duration, 2),
                        status=status,
                    )
                )
            return records

    def get_metrics(self) -> ObservabilityMetrics:
        """Computes system-wide observability metrics."""
        with self._lock:
            total_traces = len(self._traces_map)
            all_spans: List[SpanRecord] = []
            for t in self._traces_map.values():
                all_spans.extend(t.spans)

            total_spans = len(all_spans)
            total_events = len(self._events_deque)
            total_errors = len(self._errors_deque)

            failed_spans = sum(1 for s in all_spans if s.status == "failed")
            error_rate = min(1.0, (failed_spans / total_spans)) if total_spans > 0 else 0.0

            durations = [t.duration_ms for t in self._traces_map.values() if t.duration_ms is not None]
            avg_duration = (sum(durations) / len(durations)) if durations else 0.0

            traces_by_status: Dict[str, int] = {}
            for t in self._traces_map.values():
                traces_by_status[t.status] = traces_by_status.get(t.status, 0) + 1

            spans_by_type: Dict[str, int] = {}
            for s in all_spans:
                spans_by_type[s.span_type] = spans_by_type.get(s.span_type, 0) + 1

            agent_activity: Dict[str, Dict[str, Any]] = {}
            for agent_name, _ in CANONICAL_AGENTS:
                agent_spans_count = sum(
                    1 for s in all_spans if s.agent_name and agent_name.lower() in s.agent_name.lower()
                )
                agent_events_count = sum(
                    1 for e in self._events_deque if e.agent_name and agent_name.lower() in e.agent_name.lower()
                )
                agent_activity[agent_name] = {
                    "invocations": max(agent_spans_count, agent_events_count),
                }

            return ObservabilityMetrics(
                total_traces=total_traces,
                total_spans=total_spans,
                total_events=total_events,
                total_errors=total_errors,
                error_rate=round(error_rate, 4),
                avg_trace_duration_ms=round(avg_duration, 2),
                traces_by_status=traces_by_status,
                spans_by_type=spans_by_type,
                agent_activity=agent_activity,
            )

    def clear(self) -> None:
        """Clears all buffered traces and events (used in test isolation)."""
        with self._lock:
            self._traces_deque.clear()
            self._traces_map.clear()
            self._events_deque.clear()
            self._errors_deque.clear()


# Global singleton instance for application lifetime
observability_store = ObservabilityStore()
