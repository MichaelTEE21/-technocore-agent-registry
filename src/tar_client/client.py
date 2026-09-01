"""HTTP client for protocol tar.a2a 1.0.

Signs outbound task actions only when an optional key-file path is given
(same convention as the CLI). Private keys are never stored, logged, or printed.
Presence of a signature is not treated as proof — verify with tar.crypto.
"""

from __future__ import annotations

import os
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import httpx

DEFAULT_BASE = os.environ.get("REGISTRY_URL", "http://127.0.0.1:8080")


class TarClientError(RuntimeError):
    def __init__(self, status_code: int, body: Any):
        self.status_code = status_code
        self.body = body
        err = body.get("error") if isinstance(body, dict) else None
        if isinstance(err, dict):
            msg = f"{err.get('code', 'error')}: {err.get('message', body)}"
        else:
            msg = str(body)
        super().__init__(f"{status_code} {msg}")


def connect(
    base_url: str = DEFAULT_BASE,
    *,
    token: str | None = None,
    key_file: str | Path | None = None,
    client: Any | None = None,
) -> TarClient:
    """Return a client pointed at base_url."""
    return TarClient(base_url, token=token, key_file=key_file, client=client)


class TarClient:
    """JSON-only tar.a2a client."""

    def __init__(
        self,
        base_url: str = DEFAULT_BASE,
        *,
        token: str | None = None,
        key_file: str | Path | None = None,
        client: Any | None = None,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.token = token if token is not None else os.environ.get("REGISTRY_TOKEN") or None
        self.key_file = Path(key_file) if key_file else None
        self._headers = {"Accept": "application/json"}
        if self.token:
            self._headers["X-Registry-Token"] = self.token
        self._owns_client = client is None
        self._http = client or httpx.Client(
            base_url=self.base_url, headers=self._headers, timeout=15.0
        )

    def connect(self, base_url: str) -> TarClient:
        """Set or replace the registry base URL."""
        self.base_url = base_url.rstrip("/")
        if self._owns_client:
            self._http.close()
            self._http = httpx.Client(
                base_url=self.base_url, headers=self._headers, timeout=15.0
            )
        return self

    def close(self) -> None:
        if self._owns_client:
            self._http.close()

    def _request(self, method: str, path: str, **kwargs: Any) -> Any:
        resp = self._http.request(method, path, **kwargs)
        if resp.status_code >= 400:
            try:
                body = resp.json()
            except Exception:
                body = {"error": {"code": "http_error", "message": resp.text[:400]}}
            raise TarClientError(resp.status_code, body)
        if resp.status_code == 204 or not resp.content:
            return None
        return resp.json()

    def discover(
        self,
        capabilities: str | list[str],
        protocol: str | None = None,
    ) -> dict[str, Any]:
        caps = [capabilities] if isinstance(capabilities, str) else list(capabilities)
        params: list[tuple[str, str]] = [("capability", c) for c in caps]
        if protocol:
            params.append(("protocol", protocol))
        return self._request("GET", "/discover", params=params)

    def create_task(
        self,
        *,
        requester: str,
        requested_capability: str,
        description: str = "",
        assignee: str | None = None,
        protocol: str = "http",
        task_id: str | None = None,
    ) -> dict[str, Any]:
        body: dict[str, Any] = {
            "requester": requester,
            "requested_capability": requested_capability,
            "description": description,
            "protocol": protocol,
        }
        if assignee:
            body["assignee"] = assignee
        if task_id:
            body["task_id"] = task_id
        return self._request("POST", "/tasks", json=body)

    def accept(self, task_id: str, agent_id: str, **kw: Any) -> dict[str, Any]:
        return self._task_action(task_id, "accept", "ACCEPT", agent_id, **kw)

    def reject(self, task_id: str, agent_id: str, **kw: Any) -> dict[str, Any]:
        return self._task_action(task_id, "reject", "REJECT", agent_id, **kw)

    def progress(self, task_id: str, agent_id: str, payload: dict | None = None, **kw: Any) -> dict[str, Any]:
        return self._task_action(task_id, "progress", "PROGRESS", agent_id, payload=payload or {}, **kw)

    def result(
        self,
        task_id: str,
        agent_id: str,
        result: Any = None,
        payload: dict | None = None,
        **kw: Any,
    ) -> dict[str, Any]:
        body_payload = dict(payload or {})
        extra: dict[str, Any] = {}
        if result is not None:
            extra["result"] = result
            body_payload.setdefault("result", result)
        return self._task_action(
            task_id, "result", "RESULT", agent_id, payload=body_payload, extra=extra, **kw
        )

    def get_task(self, task_id: str) -> dict[str, Any]:
        return self._request("GET", f"/tasks/{task_id}")

    def get_message(self, message_id: str) -> dict[str, Any]:
        return self._request("GET", f"/messages/{message_id}")

    def verify_message(
        self,
        message: dict[str, Any] | str,
        public_key: str | None = None,
    ) -> dict[str, Any]:
        """Check Ed25519 over canonical JSON using tar.crypto.

        Never treats presence of a signature as proof.
        Valid signature ≠ correct answer.
        """
        envelope = self.get_message(message) if isinstance(message, str) else dict(message)
        from_agent = envelope.get("from") or envelope.get("from_agent")
        signature = envelope.get("signature")
        note = (
            "Identity check ≠ signature valid ≠ agent verification status ≠ "
            "task complete ≠ result is true. A valid signature does not mean "
            "the result is correct. Presence of a signature is not proof."
        )
        if not signature:
            return {
                "message_id": envelope.get("message_id"),
                "signature_status": "UNSIGNED",
                "valid": False,
                "note": note,
            }
        key_hex = public_key
        if not key_hex and from_agent:
            try:
                agent = self._request("GET", f"/agents/{from_agent}")
                key_hex = agent.get("public_key")
            except TarClientError:
                key_hex = None
        if not key_hex:
            return {
                "message_id": envelope.get("message_id"),
                "signature_status": "INVALID",
                "valid": False,
                "note": note,
            }
        from tar.crypto import (
            canonical_message_bytes,
            parse_public_key_hex,
            verify,
        )

        try:
            raw = parse_public_key_hex(key_hex)
        except Exception:
            return {
                "message_id": envelope.get("message_id"),
                "signature_status": "INVALID",
                "valid": False,
                "note": note,
            }
        msg_bytes = canonical_message_bytes(
            message_id=str(envelope.get("message_id") or ""),
            type=str(envelope.get("type") or ""),
            from_agent=str(from_agent or ""),
            to_agent=str(envelope.get("to") or envelope.get("to_agent") or ""),
            timestamp=str(envelope.get("timestamp") or ""),
            task_id=envelope.get("task_id"),
            payload=envelope.get("payload") or {},
        )
        ok = verify(raw, msg_bytes, signature)
        return {
            "message_id": envelope.get("message_id"),
            "signature_status": "VALID" if ok else "INVALID",
            "valid": ok,
            "note": note,
        }

    def _task_action(
        self,
        task_id: str,
        path_action: str,
        msg_type: str,
        agent_id: str,
        *,
        payload: dict[str, Any] | None = None,
        extra: dict[str, Any] | None = None,
        message_id: str | None = None,
        timestamp: str | None = None,
        signature: str | None = None,
    ) -> dict[str, Any]:
        payload = payload or {}
        message_id = message_id or f"cli-{uuid.uuid4().hex[:12]}"
        timestamp = timestamp or _iso()
        body: dict[str, Any] = {
            "agent_id": agent_id,
            "message_id": message_id,
            "timestamp": timestamp,
            "payload": payload,
        }
        if extra:
            body.update(extra)
        sig = signature
        if sig is None and self.key_file is not None:
            task = self.get_task(task_id)
            to_agent = task.get("requester") or agent_id
            sig = _sign_envelope(
                self.key_file,
                message_id=message_id,
                type=msg_type,
                from_agent=agent_id,
                to_agent=to_agent,
                timestamp=timestamp,
                task_id=task_id,
                payload=payload,
            )
        if sig:
            body["signature"] = sig
        return self._request("POST", f"/tasks/{task_id}/{path_action}", json=body)


def _iso() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _sign_envelope(
    key_file: Path,
    *,
    message_id: str,
    type: str,
    from_agent: str,
    to_agent: str,
    timestamp: str,
    task_id: str | None,
    payload: dict[str, Any],
) -> str:
    raw = key_file.read_bytes()
    if len(raw) == 64:
        try:
            raw = bytes.fromhex(raw.decode().strip())
        except Exception:
            pass
    if len(raw) != 32:
        raise TarClientError(
            400,
            {"error": {"code": "bad_request", "message": "key file must be 32 raw bytes or 64 hex chars"}},
        )
    from tar.crypto import canonical_message_bytes, sign

    msg = canonical_message_bytes(
        message_id=message_id,
        type=type,
        from_agent=from_agent,
        to_agent=to_agent,
        timestamp=timestamp,
        task_id=task_id,
        payload=payload,
    )
    return sign(raw, msg)
