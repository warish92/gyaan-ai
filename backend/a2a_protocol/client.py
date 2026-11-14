"""Gyaan AI - CrewAI A2A Client Integration.

Provides the dedicated Agent-to-Agent (A2A) client allowing CrewAI agents
(particularly the Orchestrator) to discover, authenticate, and communicate
with the Google ADK Learning Intelligence Agent across an HTTP/JSON-RPC boundary.
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
import json
import logging
import time
from typing import Any, Dict, List, Optional
import uuid

import httpx

from backend.a2a_protocol.schemas import (
    A2AErrorResponse,
    A2ATaskMetadata,
    AgentExecutionMetadata,
    LearningAnalysisA2ARequest,
    LearningAnalysisA2AResponse,
    LearningAnalysisArtifact,
)
from backend.a2a_protocol.security import get_internal_a2a_token

logger = logging.getLogger("gyaan_ai.a2a.client")


class A2AClientError(Exception):
    """Base exception for all A2A client communication errors."""
    def __init__(self, message: str, status_code: Optional[int] = None, details: Optional[Dict[str, Any]] = None):
        super().__init__(message)
        self.message = message
        self.status_code = status_code
        self.details = details or {}


class A2ADiscoveryError(A2AClientError):
    """Raised when Agent Card discovery fails or the card is invalid."""
    pass


class A2AAuthenticationError(A2AClientError):
    """Raised when inter-agent authentication is rejected."""
    pass


class A2AValidationError(A2AClientError):
    """Raised when message payload validation fails."""
    pass


class A2ATimeoutError(A2AClientError):
    """Raised when an A2A task or request exceeds its bounded timeout."""
    pass


class A2AServerError(A2AClientError):
    """Raised when the remote A2A agent or server encounters an internal error."""
    pass


class A2AOrchestratorClient:
    """Dedicated A2A Client used by the CrewAI Orchestrator to delegate learning intelligence to Google ADK."""

    def __init__(
        self,
        base_url: str = "http://127.0.0.1:8000/api/v1/a2a",
        internal_secret: Optional[str] = None,
        timeout: float = 60.0,
        max_retries: int = 2,
        httpx_client: Optional[httpx.AsyncClient] = None,
        fallback_on_offline: bool = True,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self._internal_secret = internal_secret
        self.timeout = timeout
        self.max_retries = max_retries
        self._shared_client = httpx_client
        self.fallback_on_offline = fallback_on_offline
        self._cached_agent_card: Optional[Dict[str, Any]] = None

    @property
    def internal_secret(self) -> str:
        if self._internal_secret:
            return self._internal_secret
        return get_internal_a2a_token()

    def _get_headers(self, correlation_id: Optional[str] = None) -> Dict[str, str]:
        headers = {
            "Authorization": f"Bearer {self.internal_secret}",
            "X-A2A-Internal-Token": self.internal_secret,
            "Content-Type": "application/json",
            "Accept": "application/json",
        }
        if self.fallback_on_offline:
            headers["X-A2A-Fallback"] = "true"
        if correlation_id:
            headers["X-Correlation-ID"] = correlation_id
        try:
            from backend.observability import get_current_trace_id, get_current_span_id
            active_tid = get_current_trace_id()
            if active_tid:
                active_sid = get_current_span_id() or uuid.uuid4().hex[:16]
                headers["traceparent"] = f"00-{active_tid}-{active_sid}-01"
                headers["X-Trace-Id"] = active_tid
                headers["X-Parent-Span-Id"] = active_sid
        except Exception:
            pass
        return headers

    async def _get_client(self) -> httpx.AsyncClient:
        if self._shared_client is not None:
            return self._shared_client

        # If targeting localhost and standalone uvicorn is not running, use ASGI in-process transport
        if "127.0.0.1" in self.base_url or "localhost" in self.base_url:
            import socket
            sock = socket.socket()
            sock.settimeout(0.2)
            try:
                port = 8000
                if ":8000" in self.base_url:
                    port = 8000
                sock.connect(("127.0.0.1", port))
                sock.close()
                return httpx.AsyncClient(timeout=self.timeout)
            except Exception:
                try:
                    from backend.app.main import app
                    transport = httpx.ASGITransport(app=app)
                    return httpx.AsyncClient(
                        transport=transport,
                        base_url="http://127.0.0.1:8000",
                        timeout=self.timeout,
                    )
                except Exception:
                    return httpx.AsyncClient(timeout=self.timeout)

        return httpx.AsyncClient(timeout=self.timeout)

    # --------------------------------------------------------------------------
    # Agent Card Discovery
    # --------------------------------------------------------------------------
    async def discover_agent_card(self, force_refresh: bool = False) -> Dict[str, Any]:
        """Discovers and validates the ADK Learning Intelligence Agent Card over HTTP."""
        if self._cached_agent_card and not force_refresh:
            return self._cached_agent_card

        client = await self._get_client()
        discovery_url = f"{self.base_url}/.well-known/agent-card.json"

        try:
            logger.info("Discovering A2A Agent Card from %s", discovery_url)
            response = await client.get(discovery_url, headers=self._get_headers())
            if response.status_code != 200:
                raise A2ADiscoveryError(
                    f"Agent Card discovery failed with status {response.status_code}: {response.text}",
                    status_code=response.status_code,
                )

            card = response.json()
            self._validate_agent_card(card)
            self._cached_agent_card = card
            logger.info("Successfully discovered and verified Agent Card: %s (version %s)", card.get("name"), card.get("version"))
            return card

        except httpx.RequestError as exc:
            raise A2ADiscoveryError(f"Network error during Agent Card discovery: {exc}") from exc
        finally:
            if self._shared_client is None:
                await client.aclose()

    def _validate_agent_card(self, card: Dict[str, Any]) -> None:
        """Validates that the discovered card conforms to the A2A spec and matches expected capabilities."""
        if not isinstance(card, dict):
            raise A2ADiscoveryError("Invalid Agent Card format: expected JSON object")

        name = card.get("name")
        if name != "learning_intelligence_agent":
            raise A2ADiscoveryError(f"Agent Card mismatch: expected 'learning_intelligence_agent', got '{name}'")

        skills = card.get("skills", [])
        if not any(s.get("id") == "learning_intelligence_analysis" for s in skills):
            logger.warning("Agent Card lacks explicit 'learning_intelligence_analysis' skill ID")

    # --------------------------------------------------------------------------
    # Task Execution over A2A Protocol
    # --------------------------------------------------------------------------
    async def submit_learning_analysis(
        self,
        request_payload: LearningAnalysisA2ARequest,
    ) -> LearningAnalysisA2AResponse:
        """Submits an evidence-based learning intelligence task to the ADK Agent over A2A."""
        # Ensure agent card is discoverable
        await self.discover_agent_card()

        correlation_id = request_payload.correlation_id or f"corr_{uuid.uuid4().hex[:10]}"
        headers = self._get_headers(correlation_id=correlation_id)
        task_url = f"{self.base_url}/tasks/learning-analysis"

        attempt = 0
        last_exception: Optional[Exception] = None

        while attempt <= self.max_retries:
            attempt += 1
            client = await self._get_client()
            try:
                logger.info(
                    "Submitting A2A learning analysis task (attempt %d/%d, student=%s, correlation=%s)",
                    attempt,
                    self.max_retries + 1,
                    request_payload.student_id,
                    correlation_id,
                )

                response = await client.post(
                    task_url,
                    headers=headers,
                    json=request_payload.model_dump(),
                    timeout=self.timeout,
                )

                if response.status_code == 200:
                    data = response.json()
                    validated_resp = LearningAnalysisA2AResponse.model_validate(data)
                    logger.info(
                        "Received valid A2A learning analysis response (task_id=%s, artifact_id=%s, duration=%.2fms)",
                        validated_resp.task_id,
                        validated_resp.artifact.artifact_id if validated_resp.artifact else "none",
                        validated_resp.agent_metadata.duration_ms,
                    )
                    return validated_resp

                elif response.status_code in (401, 403):
                    raise A2AAuthenticationError(
                        f"A2A authentication rejected ({response.status_code}): {response.text}",
                        status_code=response.status_code,
                    )
                elif response.status_code == 400:
                    raise A2AValidationError(
                        f"A2A request validation failed (400): {response.text}",
                        status_code=400,
                    )
                elif response.status_code == 504:
                    raise A2ATimeoutError(
                        f"A2A server timed out (504): {response.text}",
                        status_code=504,
                    )
                else:
                    raise A2AServerError(
                        f"A2A server returned error status {response.status_code}: {response.text}",
                        status_code=response.status_code,
                    )

            except (httpx.TimeoutException, A2ATimeoutError) as exc:
                last_exception = A2ATimeoutError(f"A2A request timed out after {self.timeout}s: {exc}")
                logger.warning("A2A request attempt %d timed out: %s", attempt, exc)
            except httpx.RequestError as exc:
                last_exception = A2AServerError(f"A2A transport error: {exc}")
                logger.warning("A2A transport error on attempt %d: %s", attempt, exc)
            except (A2AAuthenticationError, A2AValidationError):
                # Non-retryable errors
                raise
            finally:
                if self._shared_client is None:
                    await client.aclose()

            if attempt <= self.max_retries:
                backoff = 0.5 * (2 ** (attempt - 1))
                await asyncio.sleep(backoff)

        if last_exception:
            raise last_exception
        raise A2AServerError("A2A request failed after all retry attempts")

    # --------------------------------------------------------------------------
    # JSON-RPC 2.0 Task Operations
    # --------------------------------------------------------------------------
    async def get_task_status(self, task_id: str) -> Dict[str, Any]:
        """Queries the status and artifacts of an A2A task via JSON-RPC."""
        client = await self._get_client()
        rpc_url = self.base_url

        payload = {
            "jsonrpc": "2.0",
            "id": f"rpc_{uuid.uuid4().hex[:8]}",
            "method": "tasks/get",
            "params": {"id": task_id},
        }

        try:
            response = await client.post(rpc_url, headers=self._get_headers(), json=payload)
            if response.status_code != 200:
                raise A2AServerError(f"JSON-RPC call failed with HTTP {response.status_code}: {response.text}")
            result = response.json()
            if "error" in result:
                raise A2AServerError(f"JSON-RPC error: {result['error']}")
            return result.get("result", {}).get("task", {})
        finally:
            if self._shared_client is None:
                await client.aclose()

    async def cancel_task(self, task_id: str) -> bool:
        """Requests cancellation of an in-progress A2A task via JSON-RPC."""
        client = await self._get_client()
        rpc_url = self.base_url

        payload = {
            "jsonrpc": "2.0",
            "id": f"rpc_{uuid.uuid4().hex[:8]}",
            "method": "tasks/cancel",
            "params": {"id": task_id},
        }

        try:
            response = await client.post(rpc_url, headers=self._get_headers(), json=payload)
            if response.status_code != 200:
                return False
            result = response.json()
            return result.get("result", {}).get("cancelled", False)
        finally:
            if self._shared_client is None:
                await client.aclose()


# Global default client
a2a_orchestrator_client = A2AOrchestratorClient()
