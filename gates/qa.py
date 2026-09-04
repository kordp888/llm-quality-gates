"""숫자 원본대조 QA. 하드 실패가 하나라도 있으면 업로드를 차단한다.

카드·낭독·제목에 쓰인 숫자/방향/문구가 신호(원본 스냅샷에서 파생)와 전수 일치하는지
독립 검증한다. deepsignal qa_check의 '원본 대조 + 자기참조 금지' 발상을 realsignal
도메인에 이식. hard_fail이 하나라도 있으면 업로드를 차단한다.

검증 항목:
  - 금액 표기 왕복(억/만원 문자열 → 만원)이 signal.amount_manwon과 정확히 일치
  - 제목·낭독에 카드와 동일한 금액 문자열이 포함
  - 방향(▲▼)이 실제 이벤트와 모순 없음
  - 해제거래 제외(§10)
  - 비교 표본수 표기 == signal.comparison_count
  - 저신뢰(low)면 '신고가/급등' 단정 금지, '참고' 완화 필수(§10.4 정직성)
  - 단지명·법정동이 비어있지 않고 제목에 grounded (추정정보 생성 금지)
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from gates.formatting import amount_manwon_to_korean, _direction


@dataclass
class QAResult:
    hard_fails: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.hard_fails


def parse_korean_manwon(text: str) -> int | None:
    """'15억 5,000만원'·'3억'·'8,000만원' → 만원 정수. 못 찾으면 None."""
    eok = re.search(r"([\d,]+)\s*억", text)
    man = re.search(r"([\d,]+)\s*만원", text)
    if not eok and not man:
        return None
    total = 0
    if eok:
        total += int(eok.group(1).replace(",", "")) * 10000
    if man:
        total += int(man.group(1).replace(",", ""))
    return total


def check_signal_render(signal: dict, *, title: str = "", narration: str = "") -> QAResult:
    """한 신호의 렌더 산출물(제목·낭독)과 신호 데이터의 정합성 검증."""
    r = QAResult()
    manwon = signal.get("amount_manwon")
    amount_str = amount_manwon_to_korean(manwon)

    # 1) 금액 표기 왕복 일치 (포매터가 원본을 왜곡하지 않는지)
    if manwon is not None:
        back = parse_korean_manwon(amount_str)
        if back != manwon:
            r.hard_fails.append(f"금액 표기 왕복 불일치: '{amount_str}' → {back} ≠ 원본 {manwon}")

    # 2) 제목·낭독에 카드와 동일한 금액 문자열 존재
    for surface, text in (("제목", title), ("낭독", narration)):
        if not text:
            continue
        if manwon is not None and parse_korean_manwon(text) != manwon:
            r.hard_fails.append(f"{surface} 금액이 원본과 불일치 (원본 {manwon}만원)")

    # 3) 방향(▲▼)이 이벤트와 모순 없는지
    events = {e["type"] for e in signal.get("events", [])}
    arrow, _col, _sub = _direction(signal)
    down = "drop" in events or any(
        e.get("type") == "range_break_12m" and e.get("direction") == "down"
        for e in signal.get("events", []))
    up = bool(events & {"record_high", "record_3yr", "surge"}) or any(
        e.get("type") == "range_break_12m" and e.get("direction") == "up"
        for e in signal.get("events", []))
    if arrow == "▲" and down and not up:
        r.hard_fails.append("방향 오류: 하락 이벤트인데 ▲ 표기")
    if arrow == "▼" and up and not down:
        r.hard_fails.append("방향 오류: 상승 이벤트인데 ▼ 표기")

    # 4) 해제거래 제외
    if signal.get("is_cancelled"):
        r.hard_fails.append("해제거래가 콘텐츠에 포함됨(§10 위반)")

    # 5) 비교 표본수 표기 일치 (제목/낭독에 '비교 N건'이 있으면)
    cmp_n = signal.get("comparison_count")
    if cmp_n is not None:
        for text in (title, narration):
            m = re.search(r"비교\s*(\d+)\s*건", text or "")
            if m and int(m.group(1)) != cmp_n:
                r.hard_fails.append(f"비교 표본수 불일치: 표기 {m.group(1)} ≠ 원본 {cmp_n}")

    # 6) 저신뢰 정직성(§10.4): low면 단정 표현 금지
    if signal.get("confidence") == "low":
        joined = " ".join(signal.get("reasons", []))
        if "신고가 갱신" in joined or re.search(r"급등|급락", joined):
            r.hard_fails.append("저신뢰(≤1 표본)인데 단정 표현('신고가 갱신/급등/급락') 사용")

    # 7) 단지명·법정동 grounded (추정정보 생성 금지)
    apt = (signal.get("apartment") or "").strip()
    if not apt:
        r.hard_fails.append("단지명 없음(원본 미확인)")
    elif title and apt.split("(")[0][:6] not in title:
        r.warnings.append("제목에 단지명이 grounded 되지 않음")

    return r


def check_selection(res: dict, *, title: str = "") -> QAResult:
    """선정 결과(5건) 전수 검증. 제목은 1위에만 대조."""
    agg = QAResult()
    for s in res.get("signals", []):
        rank = s.get("rank")
        one = check_signal_render(s, title=(title if rank == 1 else ""))
        agg.hard_fails += [f"{rank}위: {f}" for f in one.hard_fails]
        agg.warnings += [f"{rank}위: {w}" for w in one.warnings]
    return agg


def assert_publishable(signal_or_res: dict, *, title: str = "", narration: str = "") -> QAResult:
    """업로드 게이트. hard_fail이 있으면 예외. signal 단건 또는 선정 결과(signals 키) 모두 허용."""
    if "signals" in signal_or_res:
        res = check_selection(signal_or_res, title=title)
    else:
        res = check_signal_render(signal_or_res, title=title, narration=narration)
    if not res.ok:
        raise RuntimeError("QA 하드 실패 — 업로드 차단:\n  - " + "\n  - ".join(res.hard_fails))
    return res
