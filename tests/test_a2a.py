from tar.a2a import A2AEnvelope, A2AMessageType


def test_envelope_types_exist():
    for name in ("REQUEST", "ACCEPT", "REJECT", "PROGRESS", "RESULT", "VERIFY"):
        assert hasattr(A2AMessageType, name)
    env = A2AEnvelope(
        message_id="m1",
        type=A2AMessageType.REQUEST,
        from_agent="test-research",
        to_agent="test-developer",
        timestamp="2026-09-01T00:00:00Z",
        task_id="task-1",
        payload={"capability": "python"},
    )
    assert env.type is A2AMessageType.REQUEST
    assert "Local" in env.note or "Ed25519" in env.note
