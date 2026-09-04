"""숫자 원본대조 QA 테스트 (§10·§14)."""

from __future__ import annotations

from gates import qa


def _sig(**kw):
    base = {
        "apartment": "선사현대아파트", "dong": "암사동", "lawd_cd": "11740",
        "amount_manwon": 155000, "area_m2": 83.18, "floor": 25, "deal_day": 22,
        "comparison_count": 3, "confidence": "medium",
        "events": [{"type": "record_high", "prior_max_manwon": 125000, "delta_manwon": 30000}],
        "reasons": ["신고가 갱신 (직전 최고가 12.5억 → 15.5억)"],
    }
    base.update(kw)
    return base


def test_parse_korean_manwon():
    assert qa.parse_korean_manwon("15억 5,000만원") == 155000
    assert qa.parse_korean_manwon("3억") == 30000
    assert qa.parse_korean_manwon("8,000만원") == 8000
    assert qa.parse_korean_manwon("12억 6,200만원") == 126200
    assert qa.parse_korean_manwon("금액 미공개") is None


def test_valid_signal_passes():
    s = _sig()
    title = "[샘플] 강동구 선사현대아파트 15억 5,000만원 신고가"
    narr = "1위. 강동구 선사현대아파트. 15억 5,000만원에 거래됐습니다."
    res = qa.check_signal_render(s, title=title, narration=narr)
    assert res.ok, res.hard_fails


def test_title_amount_mismatch_hard_fails():
    s = _sig()
    title = "강동구 선사현대아파트 14억 신고가"  # 원본 15.5억과 불일치
    res = qa.check_signal_render(s, title=title)
    assert not res.ok
    assert any("제목 금액" in f for f in res.hard_fails)


def test_cancelled_hard_fails():
    s = _sig(is_cancelled=True)
    res = qa.check_signal_render(s, title="강동구 선사현대아파트 15억 5,000만원")
    assert any("해제거래" in f for f in res.hard_fails)


def test_comparison_count_mismatch_hard_fails():
    s = _sig(comparison_count=4)
    narr = "동일 면적 비교 7건 기준입니다"  # 원본 4건과 불일치
    res = qa.check_signal_render(s, narration=narr)
    assert any("비교 표본수" in f for f in res.hard_fails)


def test_low_confidence_absolute_wording_hard_fails():
    s = _sig(confidence="low", reasons=["신고가 갱신 (직전 최고가 12.5억 → 15.5억)"])
    res = qa.check_signal_render(s, title="강동구 선사현대아파트 15억 5,000만원")
    assert any("저신뢰" in f for f in res.hard_fails)


def test_low_confidence_softened_passes():
    s = _sig(confidence="low", reasons=["관측 구간 내 최고가 (참고, 직전 12.5억 → 15.5억)"])
    res = qa.check_signal_render(s, title="강동구 선사현대아파트 15억 5,000만원")
    assert res.ok, res.hard_fails


def test_check_selection_labels_rank():
    res = {"signals": [
        _sig(rank=1, amount_manwon=155000),
        _sig(rank=2, amount_manwon=38000, comparison_count=4, is_cancelled=True),  # 해제→fail
    ]}
    r = qa.check_selection(res, title="강동구 선사현대아파트 15억 5,000만원")
    assert not r.ok
    assert any(f.startswith("2위:") and "해제거래" in f for f in r.hard_fails)


def test_assert_publishable_accepts_selection():
    res = {"signals": [_sig(rank=1)]}
    qa.assert_publishable(res, title="강동구 선사현대아파트 15억 5,000만원")  # 통과 = 예외 없음


def test_assert_publishable_raises_on_fail():
    s = _sig()
    try:
        qa.assert_publishable(s, title="강동구 선사현대아파트 14억")  # 금액 불일치
    except RuntimeError as e:
        assert "QA 하드 실패" in str(e)
    else:
        raise AssertionError("업로드 차단 예외가 발생해야 함")
