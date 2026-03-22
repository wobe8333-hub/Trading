from datetime import datetime, timezone
from src.core.execution_cost_guard.funding_time_guard import FundingTimeGuard

GUARD = FundingTimeGuard()


def utc(h, m=0):
    return datetime(2024, 1, 1, h, m, tzinfo=timezone.utc)


# ── is_entry_allowed ─────────────────────────────────────────

def test_allowed_when_far_from_funding():
    # 04:00 UTC → 다음 펀딩(08:00)까지 240분 → 허용
    ok, reason = GUARD.is_entry_allowed(utc(4, 0))
    assert ok is True
    assert reason == "정상"


def test_blocked_within_15min():
    # 07:50 UTC → 08:00까지 10분 → 차단
    ok, reason = GUARD.is_entry_allowed(utc(7, 50))
    assert ok is False
    assert "분 전" in reason


def test_blocked_exactly_at_buffer():
    # 07:45 UTC → 08:00까지 15분 → 차단(경계 포함)
    ok, reason = GUARD.is_entry_allowed(utc(7, 45))
    assert ok is False


def test_allowed_just_after_buffer():
    # 07:44 UTC → 08:00까지 16분 → 허용
    ok, reason = GUARD.is_entry_allowed(utc(7, 44))
    assert ok is True


# ── is_post_funding_reversal_allowed ─────────────────────────

def test_post_reversal_allowed_all_conditions_met():
    # 00:03 → 마지막 펀딩 후 3분, 극단 rate, score 85
    ok = FundingTimeGuard.is_post_funding_reversal_allowed(
        utc(0, 3), funding_rate=0.002, entry_score=85
    )
    assert ok is True


def test_post_reversal_blocked_low_score():
    ok = FundingTimeGuard.is_post_funding_reversal_allowed(
        utc(0, 3), funding_rate=0.002, entry_score=75
    )
    assert ok is False


def test_post_reversal_blocked_mild_rate():
    ok = FundingTimeGuard.is_post_funding_reversal_allowed(
        utc(0, 3), funding_rate=0.0001, entry_score=85
    )
    assert ok is False


# ── 예외 안전성 ─────────────────────────────────────────────

def test_no_exception_on_naive_datetime():
    naive = datetime(2024, 1, 1, 10, 0)  # tzinfo 없음
    ok, _ = GUARD.is_entry_allowed(naive)
    assert isinstance(ok, bool)

