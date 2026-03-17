import pandas as pd
import streamlit as st
from datetime import datetime, timedelta, timezone
from utils import load_and_process, fmt, render_card_grid

st.set_page_config(page_title="Meitu 세부", page_icon="🔍", layout="wide")

COUNTRY_ORDER = ["🇰🇷 한국", "🇯🇵 일본", "🇨🇳 중국/대만", "🇹🇭 태국", "🌐 영어권", "🇪🇺 유럽", "🌏 기타"]


@st.cache_data(ttl=300)
def load_data():
    return load_and_process("data/latest_monitoring.csv")


def top_nav(current: str):
    col1, col2, col3 = st.columns([1, 1, 8])
    with col1:
        if current == "summary":
            st.markdown('<div style="background:#E1306C;color:white;text-align:center;padding:6px 0;border-radius:20px;font-size:14px;font-weight:500;">📊 요약</div>', unsafe_allow_html=True)
        else:
            st.page_link("app.py", label="📊 요약")
    with col2:
        if current == "details":
            st.markdown('<div style="background:#E1306C;color:white;text-align:center;padding:6px 0;border-radius:20px;font-size:14px;font-weight:500;">🔍 세부</div>', unsafe_allow_html=True)
        else:
            st.page_link("pages/details.py", label="🔍 세부")


# ── 메인 ──────────────────────────────────────────────────────────────────────
df_all = load_data()

top_nav("details")

st.markdown("## 🔍 Meitu 모니터링 — 세부")

if df_all["last_updated"].notna().any():
    last_kst = df_all["last_updated"].max() + pd.Timedelta(hours=9)
    st.caption(
        f"마지막 수집: **{last_kst.strftime('%Y-%m-%d %H:%M')} KST** "
        f"| 누적: **{len(df_all):,}건**"
    )

st.divider()

# ── 필터 ──────────────────────────────────────────────────────────────────────
col1, col2, col3, col4 = st.columns(4)

with col1:
    available_countries = [c for c in COUNTRY_ORDER if c in df_all["country"].unique()]
    sel_countries = st.multiselect(
        "🌍 국가 (복수 선택 가능)",
        options=available_countries,
        default=available_countries,
    )

with col2:
    now      = datetime.now(timezone.utc)
    period   = st.radio("📅 기간", ["최근 7일", "최근 1개월", "최근 3개월", "전체"],
                        index=3, horizontal=False)
    days_map = {"최근 7일": 7, "최근 1개월": 30, "최근 3개월": 90, "전체": None}
    days     = days_map[period]
    if days:
        start_d = (now - timedelta(days=days)).date()
        end_d   = now.date()
    else:
        start_d = df_all["timestamp"].min().date() if df_all["timestamp"].notna().any() else None
        end_d   = df_all["timestamp"].max().date() if df_all["timestamp"].notna().any() else None

with col3:
    sel_content = st.radio("📹 콘텐츠 형태", ["전체", "🎬 릴스", "🖼️ 피드"], index=0)

with col4:
    sel_ad = st.radio("📣 광고 여부", ["전체", "📢 광고", "🌱 오가닉"], index=0)

# 필터 적용
filtered = df_all.copy()

if sel_countries:
    filtered = filtered[filtered["country"].isin(sel_countries)]

if start_d and end_d:
    filtered = filtered[
        (filtered["timestamp"].dt.date >= start_d) &
        (filtered["timestamp"].dt.date <= end_d)
    ]

if sel_content == "🎬 릴스":
    filtered = filtered[filtered["content_type"] == "reel"]
elif sel_content == "🖼️ 피드":
    filtered = filtered[filtered["content_type"].isin(["feed", "video_feed"])]

if sel_ad != "전체":
    filtered = filtered[filtered["ad_type"] == sel_ad]

st.caption(f"필터 결과: **{len(filtered):,}건**")
st.divider()

st.subheader("📋 게시물 목록")
st.caption("인게이지먼트 기준 상위 50건 | 링크 클릭 시 인스타그램으로 이동")

if filtered.empty:
    st.info("필터 조건에 맞는 데이터가 없습니다.")
else:
    st.html(render_card_grid(filtered, fmt))
