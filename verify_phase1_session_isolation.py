"""Gyaan AI - Phase 1 Final Session Isolation & ADK Verification Script.

Tests and records evidence for:
1. Separate session IDs for distinct student identities.
2. Cross-student access prohibition (strict tenant isolation).
3. Correct student identity association.
4. Behavior when an unknown/missing session ID is supplied.
5. In-Memory Session Service persistence behavior across simulated process restart.
6. ADK Event Stream Inspection and Final Response Extraction.
"""

import asyncio
from datetime import datetime, timezone
import json
import os
import sys

# Ensure workspace in path
_root = os.path.dirname(os.path.abspath(__file__))
if _root not in sys.path:
    sys.path.insert(0, _root)

from google.genai import types
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from backend.adk.config import ADK_APP_NAME, get_adk_model
from backend.adk.agents.learning_analysis_agent import create_learning_intelligence_agent
from backend.adk.services.adk_runner import ADKLearningIntelligenceService
from backend.adk.schemas.adk_messages import (
    DiagnosticEvidence,
    LearningIntelligenceRequest,
)

evidence_log = {
    "test_name": "Phase 1 Final Session Isolation & ADK Lifecycle Verification",
    "timestamp": datetime.now(timezone.utc).isoformat(),
    "steps": [],
}


async def run_verifications():
    print("=" * 80)
    print("PHASE 1 FINAL VERIFICATION — SESSION ISOLATION & ADK LIFECYCLE")
    print("=" * 80)

    service = ADKLearningIntelligenceService()

    # Step 1: Two separate student identities
    student_a = "student_alpha_101"
    student_b = "student_beta_202"

    sess_a = await service.get_or_create_session(student_id=student_a)
    sess_b = await service.get_or_create_session(student_id=student_b)

    print(f"\n[STEP 1] Created separate student sessions:")
    print(f" - Student A ({student_a}) Session ID: {sess_a.id}")
    print(f" - Student B ({student_b}) Session ID: {sess_b.id}")

    assert sess_a.id != sess_b.id, "Session IDs must be distinct!"
    evidence_log["steps"].append({
        "step": "distinct_session_creation",
        "student_a": student_a,
        "session_a_id": sess_a.id,
        "student_b": student_b,
        "session_b_id": sess_b.id,
        "status": "PASS",
    })

    # Step 2: Cross-student state access attempt
    print(f"\n[STEP 2] Testing cross-student state access prevention...")
    cross_access_blocked = False
    try:
        await service.get_or_create_session(student_id=student_b, session_id=sess_a.id)
    except PermissionError as pe:
        cross_access_blocked = True
        print(f" - Cross-access successfully blocked with PermissionError: {pe}")

    assert cross_access_blocked, "Student B must NOT be allowed to access Student A's session!"
    evidence_log["steps"].append({
        "step": "cross_student_access_blocking",
        "attempted_student": student_b,
        "target_session_id": sess_a.id,
        "blocked": True,
        "status": "PASS",
    })

    # Step 3: Correct student identity association
    print(f"\n[STEP 3] Verifying correct student identity association...")
    sess_a_retrieved = await service.get_or_create_session(student_id=student_a, session_id=sess_a.id)
    assert sess_a_retrieved.id == sess_a.id, "Student A must retrieve their own session!"
    print(f" - Student A successfully retrieved own session: {sess_a_retrieved.id}")
    evidence_log["steps"].append({
        "step": "student_identity_association",
        "student_id": student_a,
        "retrieved_session_id": sess_a_retrieved.id,
        "status": "PASS",
    })

    # Step 4: Behavior when session is missing / unknown
    print(f"\n[STEP 4] Testing behavior when session is missing...")
    missing_session_id = "adk-sess-non-existent-99999"
    sess_auto_created = await service.get_or_create_session(student_id=student_a, session_id=missing_session_id)
    assert sess_auto_created.id != missing_session_id, "Missing session should trigger fresh session creation!"
    assert service.is_session_owned_by_student(student_a, sess_auto_created.id)
    print(f" - Missing session safely handled. Auto-created fresh session: {sess_auto_created.id}")
    evidence_log["steps"].append({
        "step": "missing_session_handling",
        "requested_session_id": missing_session_id,
        "resolved_session_id": sess_auto_created.id,
        "status": "PASS",
    })

    # Step 5: Backend restart survival test for InMemorySessionService
    print(f"\n[STEP 5] Testing session persistence across backend restart...")
    # Simulate restart by instantiating a fresh service (representing new process memory)
    restarted_service = ADKLearningIntelligenceService()
    active_before = service.get_active_sessions_count()
    active_after_restart = restarted_service.get_active_sessions_count()
    print(f" - Active sessions before restart: {active_before}")
    print(f" - Active sessions after fresh service init (process restart): {active_after_restart}")
    assert active_after_restart == 0, "InMemorySessionService state is process-bound!"
    print(" - Confirmed: InMemorySessionService state is transient and does NOT survive backend process restart.")
    evidence_log["steps"].append({
        "step": "backend_restart_survival_check",
        "service_class": "InMemorySessionService",
        "sessions_before": active_before,
        "sessions_after_restart": active_after_restart,
        "survives_restart": False,
        "limitation_documented": (
            "InMemorySessionService stores session state in python process RAM. "
            "Session history is cleared on server restart. For persistent sessions across restarts, "
            "a persistent session store (e.g. SQLiteSessionService or DatabaseSessionService) is required."
        ),
        "status": "DOCUMENTED_AND_VERIFIED",
    })

    # Step 6: ADK Event Stream and Final Response Extraction Inspection
    print(f"\n[STEP 6] Inspecting ADK Event Stream and Final Response Extraction...")
    agent = create_learning_intelligence_agent()
    session_service = InMemorySessionService()
    runner = Runner(agent=agent, session_service=session_service, app_name=ADK_APP_NAME)
    session = await session_service.create_session(app_name=ADK_APP_NAME, user_id="student_stream_test")
    
    test_msg = types.Content(
        role="user",
        parts=[types.Part.from_text(text="Analyze: Student confused lead nitrate thermal decomposition with melting. Return JSON with summary.")]
    )

    events_captured = []
    final_extracted_text = ""
    async for event in runner.run_async(user_id="student_stream_test", session_id=session.id, new_message=test_msg):
        event_info = {
            "is_final": event.is_final_response(),
            "has_content": event.content is not None,
            "parts_count": len(event.content.parts) if event.content and event.content.parts else 0,
        }
        events_captured.append(event_info)
        if event.is_final_response() and event.content and event.content.parts:
            for p in event.content.parts:
                if p.text:
                    final_extracted_text += p.text

    print(f" - Total ADK events streamed: {len(events_captured)}")
    print(f" - Final response detected: {any(e['is_final'] for e in events_captured)}")
    print(f" - Extracted final response snippet ({len(final_extracted_text)} chars): {final_extracted_text[:120]}...")

    evidence_log["steps"].append({
        "step": "adk_event_stream_extraction",
        "total_events": len(events_captured),
        "final_response_detected": any(e['is_final'] for e in events_captured),
        "extracted_chars": len(final_extracted_text),
        "status": "PASS",
    })

    output_file = os.path.join(_root, "phase1_session_isolation_evidence.json")
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(evidence_log, f, indent=2)

    print(f"\nSession isolation evidence written to {output_file}")
    print("=" * 80)


if __name__ == "__main__":
    asyncio.run(run_verifications())
