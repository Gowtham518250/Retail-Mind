def test_inventory_sync_module_has_audit_and_realtime_hooks():
    from inventory_sync_service import deduct_stock_with_idempotency

    source = deduct_stock_with_idempotency.__code__.co_names
    assert "publish_realtime_event" in source
    assert "AuditService" in source
