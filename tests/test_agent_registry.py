from agentic.registry import list_capabilities


def test_agent_capabilities_are_fail_closed_by_default():
    capabilities = list_capabilities()
    assert capabilities
    assert all(item["enabled"] is False for item in capabilities)


def test_financial_writes_require_explicit_confirmation():
    capabilities = {item["name"]: item for item in list_capabilities()}
    assert capabilities["billing.create"]["requires_confirmation"] is True
    assert capabilities["khata.record"]["requires_confirmation"] is True
    assert capabilities["billing.create"]["risk"] == "financial_write"
