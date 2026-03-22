from src.strategy.entry_score.score_thresholds import (
    score_to_scale,
    score_to_quality,
    SCORE_TO_SCALE,
    SCORE_TO_QUALITY,
)


def test_scale_90_plus():
    assert score_to_scale(90.0) == 1.0
    assert score_to_scale(95.0) == 1.0
    assert score_to_scale(100.0) == 1.0


def test_scale_80_89():
    assert score_to_scale(80.0) == 0.7
    assert score_to_scale(85.0) == 0.7
    assert score_to_scale(89.9) == 0.7


def test_scale_70_79():
    assert score_to_scale(70.0) == 0.4
    assert score_to_scale(75.0) == 0.4
    assert score_to_scale(79.9) == 0.4


def test_scale_below_70():
    assert score_to_scale(69.9) == 0.0
    assert score_to_scale(0.0) == 0.0
    assert score_to_scale(50.0) == 0.0


def test_quality_a_plus():
    assert score_to_quality(90.0) == "A+"
    assert score_to_quality(100.0) == "A+"


def test_quality_a():
    assert score_to_quality(80.0) == "A"
    assert score_to_quality(89.0) == "A"


def test_quality_b():
    assert score_to_quality(70.0) == "B"
    assert score_to_quality(79.0) == "B"


def test_quality_reject():
    assert score_to_quality(69.0) == "REJECT"
    assert score_to_quality(0.0) == "REJECT"


def test_score_to_scale_dict_has_4_entries():
    assert len(SCORE_TO_SCALE) == 4


def test_score_to_quality_dict_has_4_entries():
    assert len(SCORE_TO_QUALITY) == 4

