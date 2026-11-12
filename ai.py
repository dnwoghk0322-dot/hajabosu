"""AI 호출은 이 파일에서만 한다. 키와 모델은 .env에서 읽는다."""
import json
import os
from pathlib import Path

from anthropic import Anthropic
from dotenv import load_dotenv

BASE = Path(__file__).parent
load_dotenv(BASE / ".env")

접수정리_칸 = ["접수일", "위치", "공종", "하자내용", "긴급도", "근거"]


def _지침(이름: str) -> str:
    return (BASE / "지침" / f"{이름}.md").read_text(encoding="utf-8")


def _json_꺼내기(글: str) -> dict:
    """AI 답에서 JSON 객체 하나를 꺼낸다. 앞뒤에 다른 글이 붙어도 받아 준다."""
    시작, 끝 = 글.find("{"), 글.rfind("}")
    if 시작 == -1 or 끝 == -1:
        raise ValueError(f"AI 답에서 JSON을 찾지 못했습니다: {글[:200]}")
    return json.loads(글[시작:끝 + 1])


def 접수정리(원문: str) -> dict:
    """접수 원문 한 건을 읽고 접수일, 위치, 공종, 하자내용, 긴급도, 근거를 돌려준다."""
    키 = os.getenv("ANTHROPIC_API_KEY")
    모델 = os.getenv("MODEL")
    if not 키 or not 모델:
        raise RuntimeError(".env에 ANTHROPIC_API_KEY와 MODEL을 채워 주세요.")

    응답 = Anthropic(api_key=키).messages.create(
        model=모델,
        max_tokens=1000,
        system=_지침("접수정리"),
        messages=[{"role": "user", "content": 원문}],
    )
    답글 = "".join(블록.text for 블록 in 응답.content if 블록.type == "text")
    결과 = _json_꺼내기(답글)

    빠진_칸 = [칸 for 칸 in 접수정리_칸 if 칸 not in 결과]
    if 빠진_칸:
        raise ValueError(f"AI 답에 빠진 칸이 있습니다: {빠진_칸}")
    return 결과
