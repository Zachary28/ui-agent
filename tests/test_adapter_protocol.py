from midscene_ui_agent.platforms.registry import default_registry


def test_registered_adapters_expose_unified_operation_protocol():
    required = (
        "connect",
        "health_check",
        "screenshot",
        "launch",
        "execute",
        "verify",
        "tap_locate",
        "report",
        "disconnect",
        "close",
    )
    for name, adapter in default_registry().items():
        if name == "vitest_e2e":
            continue
        assert all(callable(getattr(adapter, method, None)) for method in required)
