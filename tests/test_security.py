from agent_factory.core.security import SecurityGate


def test_security_gate_rejects_missing_or_wrong_token():
    gate = SecurityGate("local-token")

    assert gate.is_authorized(None) is False
    assert gate.is_authorized("") is False
    assert gate.is_authorized("wrong") is False
    assert gate.is_authorized("local-token") is True


def test_security_gate_requires_confirmation_for_destructive_actions():
    gate = SecurityGate("local-token")

    assert gate.action_allowed("delegate") is True
    assert gate.action_allowed("delete_artifact") is False
    assert gate.action_allowed("delete_artifact", confirmed=False) is False
    assert gate.action_allowed("delete_artifact", confirmed=True) is True
    assert gate.action_allowed("restart", confirmed=True) is True
