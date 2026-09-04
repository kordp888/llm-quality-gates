"""qa 모듈이 쓰는 표기·방향 헬퍼.

원 저장소에서는 카드 렌더러가 이 함수들을 함께 소유한다. 여기서는 QA가
독립적으로 돌 수 있도록 필요한 것만 떼어 왔다. 색상값은 표시용이라
QA 판정에 쓰이지 않으므로 자리표시자로 둔다.
"""
from __future__ import annotations

UP = ("up",)
DOWN = ("down",)
NEUTRAL = ("neutral",)


def amount_manwon_to_korean(manwon: int | None) -> str:
    """13억 5,000만원 형태. 만원 단위 입력."""
    if manwon is None:
        return "금액 미공개"
    eok, rest = divmod(int(manwon), 10000)
    if eok and rest:
        return f"{eok}억 {rest:,}만원"
    if eok:
        return f"{eok}억"
    return f"{rest:,}만원"


def _direction(signal: dict) -> tuple[str, tuple, str]:
    """(화살표, 색, 보조문구). QA 방향 검증 호환용."""
    events = {e["type"]: e for e in signal.get("events", [])}
    if events.keys() & {"record_high", "record_3yr", "surge"} or \
            events.get("range_break_12m", {}).get("direction") == "up":
        return "▲", UP, "상승"
    if "drop" in events or events.get("range_break_12m", {}).get("direction") == "down":
        return "▼", DOWN, "하락"
    return "·", NEUTRAL, "중립"
