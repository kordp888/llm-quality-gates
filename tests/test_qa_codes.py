"""QA 게이트 코드 레지스트리 — 동치성 + 문구 드리프트 검출.

이 파일의 존재 이유: 강등 판정이 한국어 사유 문자열에 정규식을 거는 구조라서,
qa_check.py 의 메시지 문구를 바꾸면 **조용히 오분류**된다. 여기서 두 가지를 고정한다.
  1) 리팩터 전후 판정이 완전히 같다(아래 _LEGACY_* 스냅샷과 대조).
  2) 레지스트리 패턴이 실제 qa_check.py 의 메시지와 여전히 대응한다.
"""
import re
from pathlib import Path

import pytest

from gates import qa_codes

QA_CHECK_SRC = Path(__file__).resolve().parents[1] / "qa_check.py"


# 리팩터 이전 run_once.py 에 있던 원본 튜플의 동결 스냅샷. 손대지 말 것 —
# 이게 바뀌면 '동치 리팩터'라는 주장 자체가 무의미해진다.
_LEGACY_PRESENTATION = (
    r"^제목 \d+자 \(>", r"^제목이 핵심", r"^제목 품질 실패", r"^제목에 반복형 자산",
    r"^첫 2초 훅 약함", r"^Top3 카드 문구 품질", r"^앵커 톤 미달", r"^배경 저품질",
)
_LEGACY_DEMOTED = (
    r"^자막 문장 조각/잘림", r"^자막 가독성 QA 실패", r"^소수점 표기 깨짐",
    r"^조사 앞 단어 누락/공백 오류", r"^반말 잔존", r"^진행자 3인칭 표현 잔존",
    r"^주제-배경 불일치", r"^썸네일 파일 없음", r"^SAFE_TOP<120",
)


def _legacy_presentation(reason):
    return any(re.compile(p).search(str(reason)) for p in _LEGACY_PRESENTATION)


def _legacy_demoted(reason):
    return any(re.compile(p).search(str(reason)) for p in _LEGACY_DEMOTED)


# 실제로 나올 법한 사유 코퍼스 — 강등 대상과 '절대 강등하면 안 되는' 하드 사유를 섞는다.
CORPUS = [
    g.example for g in qa_codes.GATES
] + [
    # 하드 유지 — 하나라도 강등되면 사고다.
    "금지어 잔존: ['추천']",
    "프롬프트/콜론 아티팩트 잔존: ['숏츠 대본:']",
    "구성 시간 라벨 잔존: ['2초:']",
    "ollama 모델 잔존: ['exaone']",
    "영어 잔존: ['rally']",
    "한자/중국어 잔존: ['株']",
    "TTS 숫자 읽기가 화면 텍스트로 샘: ['삼 점 육팔']",
    "자막 싱크 QA 실패: main_end_delta=1.2",   # 가독성만 강등, 싱크는 하드
    "영상 파일 없음",
    "제목 핵심 키워드가 기사 원문에 없음: 반도체",
    "표면 간 수치 불일치: 코스피 3.6%",
    "동일 엔티티 방향 카드/대본 불일치: 삼성전자",
    "투자권유 표현: 매수하세요",
    "",
]


@pytest.mark.parametrize("reason", CORPUS)
def test_presentation_judgement_is_unchanged(reason):
    assert qa_codes.is_presentation(reason) == _legacy_presentation(reason), reason


@pytest.mark.parametrize("reason", CORPUS)
def test_demoted_judgement_is_unchanged(reason):
    assert qa_codes.is_demoted(reason) == _legacy_demoted(reason), reason


def test_subtitle_sync_is_never_demoted():
    """싱크는 강등 금지 — 가독성만 강등한다. 이 경계가 무너지면 싱크 불량이 통과한다."""
    assert not qa_codes.is_demoted("자막 싱크 QA 실패: main_end_delta=1.2")
    assert qa_codes.is_demoted("자막 가독성 QA 실패")


def test_codes_are_unique():
    codes = [g.code for g in qa_codes.GATES]
    assert len(codes) == len(set(codes))


def test_no_reason_matches_two_gates():
    """한 사유가 두 게이트에 걸리면 code_of 가 임의로 하나를 고르게 된다."""
    for gate in qa_codes.GATES:
        hits = qa_codes.matching_gates(gate.example)
        assert [g.code for g in hits] == [gate.code], gate.example


def test_every_gate_pattern_matches_its_example():
    for gate in qa_codes.GATES:
        assert gate.matches(gate.example), gate.code


def test_unknown_reason_is_unmapped_and_not_demoted():
    assert qa_codes.code_of("듣도 보도 못한 새 사유") == qa_codes.UNMAPPED
    assert not qa_codes.is_demoted("듣도 보도 못한 새 사유")
    assert not qa_codes.is_presentation("듣도 보도 못한 새 사유")


def _append_message_prefixes(source):
    """qa_check.py 의 critical_fail.append(...) 에서 f-string 치환 앞의 고정 접두를 뽑는다."""
    out = []
    for m in re.finditer(r'critical_fail\.append\(\s*\n?\s*f?"([^"]*)"', source):
        literal = m.group(1)
        out.append(literal.split("{")[0])
    return [p for p in out if p]


@pytest.mark.skipif(
    not (Path(__file__).resolve().parents[1] / "gates" / "qa_check.py").exists(),
    reason="qa_check.py 는 운영 저장소에만 있다. 공개본에서는 드리프트 검사를 건너뛴다.",
)
def test_registry_examples_still_correspond_to_qa_check_messages():
    """★드리프트 검출★ — qa_check.py 의 메시지 문구가 바뀌면 여기서 터진다.

    각 게이트의 example 이 qa_check.py 안 어떤 append 문구로 시작해야 한다.
    문구를 리워딩하면 대응이 끊기고, 조용한 오분류 대신 이 테스트가 실패한다.
    """
    prefixes = _append_message_prefixes(QA_CHECK_SRC.read_text(encoding="utf-8"))
    assert prefixes, "qa_check.py 에서 critical_fail.append 문구를 하나도 못 찾았다"
    orphaned = [g.code for g in qa_codes.GATES
                if not any(g.example.startswith(p) for p in prefixes)]
    assert orphaned == [], (
        "레지스트리 게이트가 qa_check.py 의 어떤 메시지와도 대응하지 않는다: "
        + ", ".join(orphaned)
        + " — 메시지 문구가 바뀌었다면 qa_codes.py 의 pattern/example 을 함께 갱신할 것."
    )


def test_run_qa_result_exposes_codes():
    """critical_fail_codes 는 critical_fail 과 같은 순서·길이여야 한다."""
    reasons = ["앵커 톤 미달", "반말 잔존", "금지어 잔존: ['추천']"]
    assert qa_codes.codes_of(reasons) == ["anchor_tone", "banmal", qa_codes.UNMAPPED]
