"""QA 게이트 코드 레지스트리 — 사유 문자열과 분류 규칙의 단일 진실 원천.

왜 필요한가:
  QA 결과의 critical_fail 은 한국어 문장 리스트이고, 업로드 게이트의 강등 판정은
  그 문장에 정규식을 걸어 이루어진다(run_once._is_presentation_qa / _is_demoted_qa).
  즉 **게이트 메시지 문구를 한 글자 바꾸면 강등 분류가 조용히 깨진다.**
  이미 false-D 사고 전례가 있다(2026-07-11, 등급 패턴이 인용 본문에 오발화).

  이 모듈은 (코드, 패턴, 분류)를 한곳에 모으고, tests/test_qa_codes.py 가
  '패턴이 실제 qa_check.py 의 메시지와 여전히 대응하는지'를 검사한다.
  문구가 바뀌면 **조용한 오분류 대신 테스트 실패**로 드러난다.

분류(class):
  presentation — 표현/연출 품질. 기사 스킵 사유가 아니다(run_once._is_presentation_qa).
  demoted      — G-3(2026-07-08 승인) 하드페일 → 경고 강등. 업로드 게이트 전용.
  두 분류는 서로 독립이며 같은 게이트가 둘 다 가질 수 있다.

범위 주의: 이 레지스트리는 '분류에 관여하는' 게이트만 담는다. 여기에 없는 사유는
`code_of()` 가 "unmapped" 를 돌려주고 하드 실패로 남는다 — 안전한 방향이다.
등급 판정(classify_publish_grade 의 D/C 패턴)은 게이트 단위가 아니라 카테고리 단위
정규식이라 성격이 달라 이번 범위에서 제외한다.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

PRESENTATION = "presentation"
DEMOTED = "demoted"


@dataclass(frozen=True)
class Gate:
    code: str
    pattern: str            # critical_fail 사유에 대한 매칭 정규식
    classes: frozenset
    example: str            # 이 게이트가 실제로 만들어내는 사유의 예시(드리프트 검사용)
    note: str = ""
    _re: re.Pattern = field(init=False, repr=False, compare=False, default=None)

    def __post_init__(self):
        object.__setattr__(self, "_re", re.compile(self.pattern))

    def matches(self, reason) -> bool:
        return bool(self._re.search(str(reason)))


def _gate(code, pattern, classes, example, note=""):
    return Gate(code=code, pattern=pattern, classes=frozenset(classes),
                example=example, note=note)


# 표현/연출 품질 — 기사 스킵 사유가 아니다(run_once.py 의 _PRESENTATION_QA_PATTERNS 승계).
_PRESENTATION_GATES = (
    _gate("title_length", r"^제목 \d+자 \(>", [PRESENTATION],
          "제목 47자 (>45)"),
    _gate("title_lead_keyword", r"^제목이 핵심", [PRESENTATION],
          "제목이 핵심 종목/지수/테마 키워드로 시작하지 않음"),
    _gate("title_quality", r"^제목 품질 실패", [PRESENTATION],
          "제목 품질 실패: 반복"),
    _gate("generic_asset_title_tail", r"^제목에 반복형 자산", [PRESENTATION],
          "제목에 반복형 자산 영향 꼬리 사용"),
    _gate("strong_opening", r"^첫 2초 훅 약함", [PRESENTATION],
          "첫 2초 훅 약함: 오늘 시장은"),
    _gate("top3_items", r"^Top3 카드 문구 품질", [PRESENTATION],
          "Top3 카드 문구 품질 실패: ['짧음']"),
    _gate("anchor_tone", r"^앵커 톤 미달", [PRESENTATION],
          "앵커 톤 미달: 종결 60%"),
    _gate("background_quality", r"^배경 저품질", [PRESENTATION],
          "배경 저품질/도면류: chart-diagram"),
)

# G-3 강등 — 하드페일에서 경고로 내리되 공개부적합은 유지. 업로드 게이트 전용.
# 하드 유지(강등 금지): 금지어·프롬프트/콜론 아티팩트·구성 시간 라벨·ollama 잔존·
#   영어 잔존·한자/중국어, 그리고 '자막 싱크 QA 실패'(가독성만 강등, 싱크는 불변).
_DEMOTED_GATES = (
    _gate("subtitle_naturalness", r"^자막 문장 조각/잘림", [DEMOTED],
          "자막 문장 조각/잘림: ['조각']"),
    _gate("subtitle_readability", r"^자막 가독성 QA 실패", [DEMOTED],
          "자막 가독성 QA 실패: 평균 0.9초",
          note="싱크(main_end_delta)는 하드 유지 — '자막 싱크 QA 실패'는 여기 없다."),
    _gate("decimal_spacing", r"^소수점 표기 깨짐", [DEMOTED],
          "소수점 표기 깨짐: ['1. 5%']"),
    _gate("particle_gap", r"^조사 앞 단어 누락/공백 오류", [DEMOTED],
          "조사 앞 단어 누락/공백 오류: ['성장률이 에']"),
    _gate("banmal", r"^반말 잔존", [DEMOTED],
          "반말 잔존: ['했다']"),
    _gate("third_person_host", r"^진행자 3인칭 표현 잔존", [DEMOTED],
          "진행자 3인칭 표현 잔존: ['빅윈드는']"),
    _gate("theme_match", r"^주제-배경 불일치", [DEMOTED],
          "주제-배경 불일치: 제목 테마=반도체, 배경 테마=유가"),
    _gate("thumbnail_file", r"^썸네일 파일 없음", [DEMOTED],
          "썸네일 파일 없음: out/thumb.jpg"),
    _gate("safe_area_top", r"^SAFE_TOP<120", [DEMOTED],
          "SAFE_TOP<120: 상단 UI 침범 위험"),
)

GATES = _PRESENTATION_GATES + _DEMOTED_GATES

UNMAPPED = "unmapped"


def matching_gates(reason):
    """사유에 매칭되는 게이트 전부. 정상이라면 0개 또는 1개다."""
    return tuple(g for g in GATES if g.matches(reason))


def code_of(reason) -> str:
    """사유 → 게이트 코드. 레지스트리 밖이면 'unmapped'(하드 실패로 남는다)."""
    hits = matching_gates(reason)
    return hits[0].code if hits else UNMAPPED


def codes_of(reasons):
    return [code_of(r) for r in (reasons or [])]


def has_class(reason, cls) -> bool:
    return any(cls in g.classes for g in matching_gates(reason))


def is_presentation(reason) -> bool:
    """표현/연출 품질 경고인지(기사 스킵 사유 아님)."""
    return has_class(reason, PRESENTATION)


def is_demoted(reason) -> bool:
    """G-3 강등 대상(표현/연출·비치명 품질)인지. 업로드 게이트 전용."""
    return has_class(reason, DEMOTED)
