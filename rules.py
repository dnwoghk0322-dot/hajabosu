"""번호, 기한, 보증 판정 규칙. 업무설명 4, 5, 6번 규칙을 그대로 옮긴 것이다. AI를 부르지 않는다."""
import csv
from datetime import date, datetime, timedelta
from pathlib import Path

공사정보_파일 = Path(__file__).parent / "data" / "공사정보.csv"

# 업무설명 4번: 긴급도별 조치기한(접수일 + n일)
기한_일수 = {"긴급": 1, "높음": 3, "보통": 7}

만료임박_일수 = 30  # 업무설명 5번: 보증만료일까지 30일 이내


def _날짜(값) -> date:
    if isinstance(값, datetime):
        return 값.date()
    if isinstance(값, date):
        return 값
    return datetime.strptime(str(값).strip(), "%Y-%m-%d").date()


def 접수번호(접수일, 순번: int) -> str:
    """HJ-접수일(YYYYMMDD)-순번(01부터). 예) HJ-20261102-01"""
    return f"HJ-{_날짜(접수일):%Y%m%d}-{순번:02d}"


def 접수번호_부여(접수일_목록, 사용중=()) -> list[str]:
    """접수일 목록을 받은 순서대로, 같은 날짜끼리 01부터 번호를 매겨 돌려준다.

    사용중: 이미 대장에 있는 접수번호. 겹치지 않게 건너뛰고 다음 번호를 쓴다.
    """
    사용 = set(사용중)
    세는_중 = {}
    번호들 = []
    for 접수일 in 접수일_목록:
        날짜 = _날짜(접수일)
        순번 = 세는_중.get(날짜, 0)
        while True:
            순번 += 1
            번호 = 접수번호(날짜, 순번)
            if 번호 not in 사용:
                break
        세는_중[날짜] = 순번
        번호들.append(번호)
    return 번호들


def 조치기한(접수일, 긴급도: str) -> str:
    """긴급 +1일, 높음 +3일, 보통 +7일. YYYY-MM-DD 글자로 돌려준다."""
    if 긴급도 not in 기한_일수:
        raise ValueError(f"알 수 없는 긴급도입니다: {긴급도!r} (긴급, 높음, 보통 중 하나)")
    return (_날짜(접수일) + timedelta(days=기한_일수[긴급도])).isoformat()


def 공사정보_읽기() -> list[dict]:
    with open(공사정보_파일, encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def 보증만료일(준공일, 보증기간_년) -> date:
    """보증만료일 = 준공일 + 하자보증기간(년)"""
    준공 = _날짜(준공일)
    try:
        return 준공.replace(year=준공.year + int(보증기간_년))
    except ValueError:  # 2월 29일 준공 + 평년. 업무설명에 규칙이 없어 추측하지 않고 멈춘다.
        raise ValueError(f"준공일 {준공}에 {보증기간_년}년을 더한 날짜가 없습니다. 담당자 확인이 필요합니다.")


def _공사_찾기(공사들, 위치: str, 공종: str) -> list[dict]:
    return [c for c in 공사들 if c["위치"].strip() == 위치.strip() and c["공종"].strip() == 공종.strip()]


def _남은_일수(접수일: date, 만료일: date) -> int:
    return (만료일 - 접수일).days


def 보증판정(접수일, 위치: str, 공종: str, 공사들: list[dict] | None = None) -> dict:
    """접수일 기준으로 보증을 판정한다.

    돌려주는 칸: 공사번호, 시공업체, 준공일, 보증만료일, 보증판정, 책임구분, 상태, 비고
    """
    접수 = _날짜(접수일)
    공사들 = 공사정보_읽기() if 공사들 is None else 공사들

    결과 = {"공사번호": "", "시공업체": "", "준공일": "", "보증만료일": "",
            "보증판정": "확인필요", "책임구분": "확인필요", "상태": "확인필요", "비고": ""}

    # 공종 미정(후보가 여러 개이거나 확인필요)이면 판정하지 않는다. 후보 공사의 만료임박만 알려 준다.
    후보_공종 = [c.strip() for c in 공종.split("/") if c.strip()]
    if len(후보_공종) != 1 or 후보_공종[0] == "확인필요":
        후보_공사 = [c for 종 in 후보_공종 for c in _공사_찾기(공사들, 위치, 종)]
        결과["비고"] = _후보_비고(접수, 후보_공사, "공종 미정")
        return 결과

    맞는_공사 = _공사_찾기(공사들, 위치, 후보_공종[0])

    if len(맞는_공사) != 1:
        사유 = "맞는 공사 없음" if not 맞는_공사 else f"맞는 공사 {len(맞는_공사)}건"
        결과["비고"] = _후보_비고(접수, 맞는_공사, 사유)
        return 결과

    공사 = 맞는_공사[0]
    만료일 = 보증만료일(공사["준공일"], 공사["하자보증기간(년)"])
    보증내 = 접수 <= 만료일  # 만료일 당일까지는 보증내

    결과.update({
        "공사번호": 공사["공사번호"],
        "시공업체": 공사["시공업체"],
        "준공일": 공사["준공일"],
        "보증만료일": 만료일.isoformat(),
        "보증판정": "보증내" if 보증내 else "보증만료",
        "책임구분": "시공업체" if 보증내 else "자체보수",
        "상태": "판정완료",
    })
    if 보증내 and _남은_일수(접수, 만료일) <= 만료임박_일수:
        결과["비고"] = "만료임박"
    return 결과


def _후보_비고(접수: date, 후보_공사: list[dict], 사유: str) -> str:
    """확인필요 건의 비고. 후보 공사가 만료임박이면 함께 적는다."""
    조각 = [사유]
    임박 = []
    for 공사 in 후보_공사:
        만료일 = 보증만료일(공사["준공일"], 공사["하자보증기간(년)"])
        if 접수 <= 만료일 and _남은_일수(접수, 만료일) <= 만료임박_일수:
            임박.append(f"{공사['공사번호']}({만료일.isoformat()})")
    if 후보_공사:
        조각.append("후보 " + ", ".join(공사["공사번호"] for 공사 in 후보_공사))
    if 임박:
        조각.append("만료임박 " + ", ".join(임박))
    return " / ".join(조각)
