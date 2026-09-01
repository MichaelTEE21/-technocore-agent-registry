from tar.a2a import A2AEnvelope, A2AMessageType


def test_envelope_types_exist():
    for name in ("REQUEST", "ACCEPT", "REJECT", "PROGRESS", "RESULT", "VERIFY"):
        assert hasattr(A2AMessageType, name)
    env = A2AEnvelope(
        type=A2AMessageType.REQUEST,
        from_agent="test-research",
        to_agent="test-developer",
        capability="python",
    )
    assert "FUTURE" in env.note
