"""담당자 화면 (내 PC). 접수 원문이 하자대장이 되기까지의 과정을 단계별로 보여 준다.

실행: streamlit run app.py
"""
import pandas as pd
import streamlit as st

import db
import rules
import run

st.set_page_config(page_title="하자보수 접수 정리", layout="wide")

st.title("하자보수 접수 정리")
st.caption("① 코드가 원문을 읽고 → ② AI가 정리하고 → ③ 코드가 규칙으로 번호·기한·보증을 판정하면 → ④ 사람이 확인합니다.")

접수_파일수 = len(list(run.입력_폴더.glob("*.txt")))

with st.sidebar:
    st.subheader("접수함")
    st.write(f"처리할 접수 **{접수_파일수}건**")
    시작 = st.button("접수함 처리하고 대장 저장", type="primary", width="stretch", disabled=접수_파일수 == 0)
    st.caption("AI를 건마다 한 번씩 부르고, 결과를 하자대장 DB에 저장합니다. (같은 접수번호는 덮어씀)")

if 시작:
    with st.status("접수함을 처리하는 중...", expanded=True) as 상태창:
        try:
            결과 = run.처리_상세(진행=st.write)
            run.저장([건["행"] for 건 in 결과])
        except Exception as e:  # 키 누락, 네트워크, AI 답 형식 오류 등
            상태창.update(label="처리하지 못했습니다", state="error")
            st.error(f"{type(e).__name__}: {e}")
            st.stop()
        st.session_state["결과"] = 결과
        상태창.update(label=f"{len(결과)}건 처리하고 하자대장 DB에 저장했습니다", state="complete", expanded=False)

결과 = st.session_state.get("결과")


def _배지(상태: str, 판정: str) -> str:
    if 상태 == "확인필요":
        return "🟡 확인필요"
    return {"보증내": "🟢 보증내", "보증만료": "🔴 보증만료"}.get(판정, 판정)


def _공사_찾기(공사번호: str) -> dict | None:
    return next((c for c in rules.공사정보_읽기() if c["공사번호"] == 공사번호), None)


# ---------- 처리 전: 저장된 대장만 보여 준다 ----------
if not 결과:
    저장본 = db.대장_읽기()
    if 저장본:
        st.info("왼쪽에서 처리를 시작하면 건마다 거친 단계가 여기에 보입니다. 아래는 마지막으로 저장된 하자대장입니다.")
        st.dataframe(pd.DataFrame(저장본, columns=db.대장_칸), width="stretch", hide_index=True)
    else:
        st.info("왼쪽에서 접수함 처리를 시작하세요.")
    st.stop()

행들 = [건["행"] for 건 in 결과]
df = pd.DataFrame(행들, columns=run.대장_칸)

# ---------- 요약 ----------
c1, c2, c3, c4, c5 = st.columns(5)
c1.metric("접수", f"{len(df)}건")
c2.metric("긴급", f"{(df['긴급도'] == '긴급').sum()}건")
c3.metric("업체 요청 (보증내)", f"{(df['책임구분'] == '시공업체').sum()}건")
c4.metric("자체보수", f"{(df['책임구분'] == '자체보수').sum()}건")
c5.metric("확인필요", f"{(df['상태'] == '확인필요').sum()}건")

# ---------- 사람이 할 일 ----------
할_일 = []
for 건 in 결과:
    행 = 건["행"]
    if 행["상태"] == "확인필요":
        할_일.append(f"**{행['접수번호']} {행['위치']}** — 공종·책임을 현장에서 정해 주세요. ({행['비고']})")
    for 경고 in 건["경고"]:
        할_일.append(f"**{행['접수번호']} {행['위치']}** — {경고}")
if 할_일:
    st.warning("**④ 사람이 할 일**\n\n" + "\n".join(f"- {줄}" for 줄 in 할_일))
else:
    st.success("확인필요 건이 없습니다. AI가 정한 긴급도와 공종만 검수해 주세요.")

탭_과정, 탭_대장 = st.tabs(["건별 처리 과정", "하자대장"])

# ---------- 건별 처리 과정 ----------
with 탭_과정:
    for 건 in 결과:
        행, 정리, 판정 = 건["행"], 건["정리"], 건["판정"]
        제목 = f"{행['접수번호']} · {행['위치']} · {행['공종']} · {행['긴급도']} · {_배지(행['상태'], 행['보증판정'])}"
        with st.expander(제목, expanded=행["상태"] == "확인필요"):
            열1, 열2, 열3 = st.columns(3)

            with 열1:
                st.markdown("**① 원문** · 코드가 읽음")
                st.caption(행["원문파일"])
                st.code(건["원문"], language=None, wrap_lines=True)

            with 열2:
                st.markdown("**② AI 정리** · AI가 판단")
                st.table(pd.Series({
                    "접수일(원문)": 정리["접수일"] or "(원문에 없음)",
                    "위치": 정리["위치"],
                    "공종": 정리["공종"],
                    "하자내용": f"{정리['하자내용']} ({len(정리['하자내용'])}자)",
                    "긴급도": 정리["긴급도"],
                    "근거": 정리["근거"],
                }, name="AI 답"))

            with 열3:
                st.markdown("**③ 규칙 적용** · 코드가 계산")
                공사 = _공사_찾기(행["공사번호"]) if 행["공사번호"] else None
                줄들 = {
                    "접수번호": 행["접수번호"],
                    "접수일": 행["접수일"],
                    "조치기한": f"{행['조치기한']}  (접수일 + {rules.기한_일수[행['긴급도']]}일, {행['긴급도']})",
                }
                if 공사:
                    줄들["맞는 공사"] = f"{공사['공사번호']} {공사['공사명']} ({공사['시공업체']})"
                    줄들["보증만료일"] = f"{행['보증만료일']}  (준공 {행['준공일']} + {공사['하자보증기간(년)']}년)"
                    줄들["판정"] = f"접수일 {행['접수일']} → {행['보증판정']} → 책임 {행['책임구분']}"
                else:
                    줄들["맞는 공사"] = "정하지 못함"
                    줄들["판정"] = f"{행['보증판정']} → 사람이 확인"
                if 행["비고"]:
                    줄들["비고"] = 행["비고"]
                st.table(pd.Series(줄들, name="코드 결과"))

# ---------- 하자대장 ----------
with 탭_대장:
    st.caption("하자대장 DB에 저장된 내용입니다. 노란 줄은 사람이 확인할 건입니다.")
    st.dataframe(
        df.style.apply(
            lambda r: ["background-color: rgba(255, 193, 7, 0.25)"] * len(r) if r["상태"] == "확인필요" else [""] * len(r),
            axis=1,
        ),
        width="stretch",
        hide_index=True,
    )
