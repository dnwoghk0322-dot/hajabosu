"""저장은 이 파일에서만 한다. 연결 정보는 .env의 DATABASE_URL(웹 배포는 Secrets)에서 읽는다.

처음 연결할 때 테이블 2개(접수, 하자대장)를 만들고 둘 다 RLS를 켠다.
- 접수: 매장·현장에서 들어오는 접수 (7, 8단계 접수 화면용)
- 하자대장: data/하자대장.csv와 같은 16칸, 접수번호가 기본키
RLS만 켜고 정책(policy)은 만들지 않는다. Supabase의 공개 API(anon 키)로는 읽거나 쓸 수 없고,
테이블 소유자인 DATABASE_URL 연결만 쓸 수 있다.
"""
import os
from pathlib import Path

from dotenv import load_dotenv
from sqlalchemy import (CheckConstraint, Column, DateTime, Integer, MetaData, Table, Text,
                        create_engine, func, select, text)
from sqlalchemy.dialects.postgresql import insert

load_dotenv(Path(__file__).parent / ".env")

대장_칸 = ["접수번호", "접수일", "원문파일", "위치", "공종", "하자내용", "긴급도", "조치기한",
          "공사번호", "시공업체", "준공일", "보증만료일", "보증판정", "책임구분", "상태", "비고"]

# 날짜 칸도 CSV와 같은 YYYY-MM-DD 글자(Text)로 둔다. DB에 이미 있는 테이블이 이 모양이다.
_메타 = MetaData()

접수 = Table(
    "접수", _메타,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("접수일시", DateTime(timezone=True), nullable=False, server_default=func.now()),
    Column("발견일", Text),
    Column("접수자", Text),
    Column("부서", Text),
    Column("위치", Text),
    Column("내용", Text),
    Column("처리상태", Text, nullable=False, server_default="미처리"),
    Column("접수번호", Text),
    CheckConstraint("\"처리상태\" in ('미처리', '처리완료')", name="접수_처리상태_확인"),
)

하자대장 = Table(
    "하자대장", _메타,
    *[Column(칸, Text, primary_key=(칸 == "접수번호")) for 칸 in 대장_칸],
)

_엔진 = None


def _주소() -> str:
    주소 = (os.getenv("DATABASE_URL") or "").strip()
    if not 주소:
        raise RuntimeError(".env에 DATABASE_URL을 채워 주세요.")
    # 설치된 드라이버(psycopg 3)로 연결하도록 주소 앞부분을 맞춘다.
    for 앞 in ("postgresql://", "postgres://"):
        if 주소.startswith(앞):
            return "postgresql+psycopg://" + 주소[len(앞):]
    return 주소


def 엔진():
    """연결을 처음 만들 때 테이블을 준비한다. 이후에는 같은 연결을 쓴다."""
    global _엔진
    if _엔진 is None:
        엔 = create_engine(_주소(), pool_pre_ping=True)
        _메타.create_all(엔)  # 이미 있으면 건너뛴다
        with 엔.begin() as 연결:
            for 이름 in (접수.name, 하자대장.name):  # 여러 번 실행해도 안전하다
                연결.execute(text(f'ALTER TABLE "{이름}" ENABLE ROW LEVEL SECURITY'))
        _엔진 = 엔
    return _엔진


def _행_변환(행: dict) -> dict:
    return {칸: "" if 행.get(칸) is None else str(행[칸]) for 칸 in 대장_칸}


def 접수_저장(발견일: str, 접수자: str, 부서: str, 위치: str, 내용: str) -> int:
    """접수 화면에서 들어온 한 건을 저장하고 id(자동 번호)를 돌려준다. 처리상태는 미처리로 시작한다."""
    문장 = insert(접수).values(발견일=발견일, 접수자=접수자, 부서=부서, 위치=위치, 내용=내용).returning(접수.c.id)
    with 엔진().begin() as 연결:
        return 연결.execute(문장).scalar_one()


def 접수_미처리_읽기() -> list[dict]:
    """처리상태가 미처리인 접수를 id 순으로 돌려준다."""
    칸들 = ["id", "접수일시", "발견일", "접수자", "부서", "위치", "내용", "처리상태", "접수번호"]
    with 엔진().connect() as 연결:
        읽은 = 연결.execute(select(접수).where(접수.c.처리상태 == "미처리").order_by(접수.c.id)).mappings().all()
    return [{칸: 행[칸] for 칸 in 칸들} for 행 in 읽은]


def 접수_처리완료(접수_id: int, 접수번호: str) -> None:
    """하자대장에 옮긴 접수를 처리완료로 바꾸고 접수번호를 적는다."""
    with 엔진().begin() as 연결:
        연결.execute(접수.update().where(접수.c.id == 접수_id).values(처리상태="처리완료", 접수번호=접수번호))


def 대장_저장(행들: list[dict]) -> int:
    """하자대장에 넣는다. 같은 접수번호가 있으면 덮어쓴다. 넣은 건수를 돌려준다."""
    if not 행들:
        return 0
    문장 = insert(하자대장).values([_행_변환(행) for 행 in 행들])
    문장 = 문장.on_conflict_do_update(
        index_elements=["접수번호"],
        set_={칸: 문장.excluded[칸] for 칸 in 대장_칸 if 칸 != "접수번호"},
    )
    with 엔진().begin() as 연결:
        연결.execute(문장)
    return len(행들)


def 대장_읽기() -> list[dict]:
    """하자대장 전체를 접수번호 순으로 돌려준다. 비어 있는 칸은 빈 글자."""
    with 엔진().connect() as 연결:
        읽은 = 연결.execute(select(하자대장).order_by(하자대장.c.접수번호)).mappings().all()
    return [{칸: 행[칸] or "" for 칸 in 대장_칸} for 행 in 읽은]


def 건수() -> dict[str, int]:
    """테이블별 건수"""
    with 엔진().connect() as 연결:
        return {표.name: 연결.execute(select(func.count()).select_from(표)).scalar_one() for 표 in (접수, 하자대장)}
