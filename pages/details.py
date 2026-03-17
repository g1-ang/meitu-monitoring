import pandas as pd
import streamlit as st
from datetime import datetime, timedelta, timezone
from utils import load_and_process, fmt, render_card_grid

st.set_page_config(page_title="IG Details", page_icon="🔍", layout="wide")

COUNTRY_ORDER  = ["🇰🇷 한국", "🇯🇵 일본", "🇨🇳 중국/대만", "🇹🇭 태국", "🌐 영어권", "🇪🇺 유럽", "🌏 기타"]
BRAND_KEYWORDS = ["meitu", "메이투", "뷰티캠", "beautycam"]


@st.cache_data(ttl=300)
def load_data():
    df = load_and_process("data/latest_monitoring.csv")
    if "keyword_type" not in df.columns:
        df["keyword_type"] = df["search_keyword"].apply(
            lambda x: "브랜드" if str(x).lower() in BRAND_KEYWORDS else "카테고리"
        ) if "search_keyword" in df.columns else "브랜드"
    else:
        df["keyword_type"] = df.apply(
            lambda row: row["keyword_type"]
            if str(row.get("keyword_type", "")) in ("브랜드", "카테고리")
            else ("브랜드" if str(row.get("search_keyword", "")).lower() in BRAND_KEYWORDS else "카테고리"),
            axis=1
        )
    return df


def top_nav(current):
    col1, col2, col3, col4 = st.columns([1, 1, 1, 7])
    with col1:
        if current == "summary":
            st.markdown('<span style="display:block;text-align:center;background:#E1306C;color:white;padding:6px 0;border-radius:8px;font-size:14px;font-weight:500;">📊 IG 요약</span>', unsafe_allow_html=True)
        else:
            st.page_link("app.py", label="📊 IG 요약")
    with col2:
        if current == "details":
            st.markdown('<span style="display:block;text-align:center;background:#E1306C;color:white;padding:6px 0;border-radius:8px;font-size:14px;font-weight:500;">🔍 IG 세부</span>', unsafe_allow_html=True)
        else:
            st.page_link("pages/details.py", label="🔍 IG 세부")
    with col3:
        if current == "twitter":
            st.markdown('<span style="display:block;text-align:center;background:#1D9BF0;color:white;padding:6px 0;border-radius:8px;font-size:14px;font-weight:500;">🐦 트위터</span>', unsafe_allow_html=True)
        else:
            st.page_link("pages/twitter.py", label="🐦 트위터")
    st.markdown("<div style='margin-bottom:8px;'></div>", unsafe_allow_html=True)


def apply_filters(df):
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        available     = [c for c in COUNTRY_ORDER if c in df["country"].unique()]
        sel_countries = st.multiselect("🌍 국가", options=available, default=available)
    with col2:
        now      = datetime.now(timezone.utc)
        period   = st.radio("📅 기간", ["최근 7일", "최근 1개월", "최근 3개월", "전체"], index=3, horizontal=False)
        days_map = {"최근 7일": 7, "최근 1개월": 30, "최근 3개월": 90, "전체": None}
        days     = days_map[period]
        if days:
            start_d = (now - timedelta(days=days)).date()
            end_d   = now.date()
        else:
            start_d = df["timestamp"].min().date() if df["timestamp"].notna().any() else None
            end_d   = df["timestamp"].max().date() if df["timestamp"].notna().any() else None
    with col3:
        sel_content = st.radio("📹 콘텐츠 형태", ["전체", "🎬 릴스", "🖼️ 피드"], index=0)
    with col4:
        sel_ad = st.radio("📣 광고 여부", ["전체", "📢 광고", "🌱 오가닉"], index=0)

    filtered = df.copy()
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
    return filtered


def show_keyword_cards(df, keyword_type):
    sub = df[df["keyword_type"] == keyword_type]
    if sub.empty:
        st.info(f"{keyword_type} 키워드 데이터가 없습니다. 다음 수집 후 확인해주세요.")
        return
    keywords   = sorted(sub["search_keyword"].dropna().unique()) if "search_keyword" in sub.columns else []
    tab_labels = ["전체"] + [f"#{k}" for k in keywords]
    tabs       = st.tabs(tab_labels)
    with tabs[0]:
        st.html(render_card_grid(sub, fmt))
    for tab, kw in zip(tabs[1:], keywords):
        with tab:
            st.html(render_card_grid(sub[sub["search_keyword"] == kw], fmt))


# ── 메인 ──────────────────────────────────────────────────────────────────────
df_all = load_data()
top_nav("details")
st.markdown("## 🔍 Meitu 모니터링 — 세부")

if df_all["last_updated"].notna().any():
    last_kst = df_all["last_updated"].max() + pd.Timedelta(hours=9)
    st.caption(f"마지막 수집: **{last_kst.strftime('%Y-%m-%d %H:%M')} KST** | 누적: **{len(df_all):,}건**")

st.divider()
filtered = apply_filters(df_all)
st.divider()

st.subheader("📋 게시물 목록")
st.caption("인게이지먼트 기준 상위 50건 | 링크 클릭 시 인스타그램으로 이동")

tab_brand, tab_category = st.tabs(["🏷️ 브랜드 키워드", "📂 카테고리 키워드"])
with tab_brand:
    st.caption("meitu · 메이투 · 뷰티캠 · beautycam 해시태그 게시물")
    show_keyword_cards(filtered, "브랜드")
with tab_category:
    st.caption("보정 · 사진편집 · ai보정 해시태그 게시물")
    show_keyword_cards(filtered, "카테고리")
