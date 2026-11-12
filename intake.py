"""접수 화면 (매장·현장용, 웹에 배포). 하자를 입력하면 DB 접수 테이블에 저장한다.

실행: streamlit run intake.py
AI와 규칙은 부르지 않는다. 정리와 판정은 담당자 화면(app.py, run.py)에서 한다.
"""
import datetime as dt
import traceback

import streamlit as st

import db

st.set_page_config(page_title="하자 접수", layout="centered")

st.title("하자 접수")
st.caption("매장·현장에서 발견한 하자를 남겨 주세요. 시설관리팀이 확인합니다.")

# 접수를 마친 직후에는 완료 안내만 보여 준다. (새로고침해도 같은 글이 두 번 저장되지 않게)
if "완료_id" in st.session_state:
    st.success(f"접수되었습니다. (접수 번호 {st.session_state['완료_id']})")
    if st.button("새 접수 쓰기"):
        del st.session_state["완료_id"]
        st.rerun()
    st.stop()

오늘 = dt.date.today()

with st.form("접수"):
    발견일 = st.date_input("발견일", value=오늘, max_value=오늘)
    접수자 = st.text_input("접수자 이름", max_chars=30)
    부서 = st.text_input("부서 / 매장", max_chars=40, placeholder="예: 3F 패션관 운영파트, 4F ○○매장")
    위치 = st.text_input("위치", max_chars=60, placeholder="예: 3F 패션관 에스컬레이터 앞 통로")
    내용 = st.text_area("하자 내용", max_chars=1000, height=160,
                      placeholder="무엇이 어떻게 되어 있는지 적어 주세요. (예: 타일 2~3장이 들떠 있고 고객이 넘어질 뻔했습니다)")
    보냄 = st.form_submit_button("접수하기", type="primary")

if 보냄:
    비어_있는_칸 = [이름 for 이름, 값 in {"접수자 이름": 접수자, "부서 / 매장": 부서, "위치": 위치, "하자 내용": 내용}.items()
                if not 값.strip()]
    if 비어_있는_칸:
        st.error("다음 칸을 채워 주세요: " + ", ".join(비어_있는_칸))
    else:
        try:
            접수_id = db.접수_저장(발견일.isoformat(), 접수자.strip(), 부서.strip(), 위치.strip(), 내용.strip())
        except Exception:
            traceback.print_exc()  # 자세한 오류는 서버 로그에만 남기고 화면에는 내지 않는다.
            st.error("접수를 저장하지 못했습니다. 잠시 뒤 다시 시도해 주세요.")
        else:
            st.session_state["완료_id"] = 접수_id
            st.rerun()
