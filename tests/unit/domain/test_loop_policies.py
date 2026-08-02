from midscene_ui_agent.domain.contracts import ExitReason


def test_retry_policy_retries_transient_failure_until_attempt_limit() -> None:
    from midscene_ui_agent.domain.policies.retry import RetryPolicy

    policy = RetryPolicy()

    assert policy.should_retry(attempt=1, max_attempts=3, reason="command_failed")
    assert not policy.should_retry(attempt=3, max_attempts=3, reason="command_failed")


def test_retry_policy_maps_blocking_reasons_without_retrying() -> None:
    from midscene_ui_agent.domain.policies.retry import RetryPolicy

    policy = RetryPolicy()

    assert policy.exit_reason("LOGIN_REQUIRED") == ExitReason.LOGIN_REQUIRED
    assert policy.exit_reason("purchase required") == ExitReason.PURCHASE_REQUIRED
    assert not policy.should_retry(attempt=1, max_attempts=3, reason="LOGIN_REQUIRED")
