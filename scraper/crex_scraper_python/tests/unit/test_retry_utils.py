import pytest

from src.core.retry_utils import RetryConfig, RetryError, retryable


def test_retry_succeeds_after_failures():
    attempts = []
    delays = []

    def flaky() -> str:
        attempts.append("x")
        if len(attempts) < 3:
            raise ValueError("boom")
        return "ok"

    def fake_sleep(duration: float) -> None:
        delays.append(round(duration, 2))

    decorated = retryable(
        config=RetryConfig(
            max_attempts=5,
            base_delay=1,
            max_delay=8,
            jitter=0,
            retry_exceptions=(ValueError,),
        ),
        sleep=fake_sleep,
    )(flaky)

    assert decorated() == "ok"
    assert len(attempts) == 3
    assert delays == [1.0, 2.0]


def test_retry_raises_after_exhausting_attempts():
    attempts = []
    delays = []

    def always_fail() -> None:
        attempts.append("x")
        raise RuntimeError("nope")

    def fake_sleep(duration: float) -> None:
        delays.append(round(duration, 2))

    decorated = retryable(
        config=RetryConfig(
            max_attempts=3,
            base_delay=1,
            max_delay=2,
            jitter=0,
            retry_exceptions=(RuntimeError,),
        ),
        sleep=fake_sleep,
    )(always_fail)

    with pytest.raises(RetryError):
        decorated()

    assert len(attempts) == 3
    assert delays == [1.0, 2.0]


def test_retry_applies_jitter():
    attempts = []
    delays = []

    def flaky() -> str:
        attempts.append("x")
        if len(attempts) < 2:
            raise ValueError("boom")
        return "done"

    def fake_sleep(duration: float) -> None:
        delays.append(round(duration, 2))

    def fake_rng() -> float:
        return 0.5  # deterministic jitter

    decorated = retryable(
        config=RetryConfig(
            max_attempts=3,
            base_delay=2,
            max_delay=2,
            jitter=1.0,
            retry_exceptions=(ValueError,),
        ),
        sleep=fake_sleep,
        rng=fake_rng,
    )(flaky)

    assert decorated() == "done"
    # Base delay 2 + jitter (0.5 * 1.0)
    assert delays == [2.5]
