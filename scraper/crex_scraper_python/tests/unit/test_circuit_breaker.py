import pytest

from src.core.circuit_breaker import (
    CircuitBreaker,
    CircuitBreakerOpenError,
    CircuitBreakerState,
)


def _raise_runtime() -> None:
    raise RuntimeError("boom")


def test_circuit_breaker_opens_after_failures():
    breaker = CircuitBreaker(name="test", failure_threshold=2, timeout_seconds=5, success_threshold=1)

    with pytest.raises(RuntimeError):
        breaker.call(_raise_runtime)
    assert breaker.state == CircuitBreakerState.CLOSED

    with pytest.raises(RuntimeError):
        breaker.call(_raise_runtime)

    assert breaker.state == CircuitBreakerState.OPEN


def test_circuit_breaker_half_open_then_close():
    breaker = CircuitBreaker(name="test", failure_threshold=1, timeout_seconds=0, success_threshold=2)

    with pytest.raises(RuntimeError):
        breaker.call(_raise_runtime)

    assert breaker.state == CircuitBreakerState.HALF_OPEN

    # First success leaves it half-open
    breaker.call(lambda: "ok")
    assert breaker.state == CircuitBreakerState.HALF_OPEN

    # Second success closes it
    breaker.call(lambda: "ok")
    assert breaker.state == CircuitBreakerState.CLOSED


def test_circuit_breaker_rejects_when_open():
    breaker = CircuitBreaker(name="test", failure_threshold=1, timeout_seconds=10, success_threshold=1)

    with pytest.raises(RuntimeError):
        breaker.call(_raise_runtime)

    with pytest.raises(CircuitBreakerOpenError):
        breaker.call(lambda: "ok")

    assert breaker.total_rejections == 1
