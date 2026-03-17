import pandas as pd
import streamlit as st
import plotly.express as px
from utils import load_and_process, extract_keywords, fmt, TYPE_COLOR, TYPE_LABEL, render_card_grid

st.set_page_config(page_title="Meitu 세부", page_icon="🔍", layout="wide")


@st.cache_data(ttl=300)
def load_data():
    return load_and_process("data/latest_monitoring.csv")


def render_keyword_chart(df):
    """캡션 키워드 빈도 TOP 20 바차트"""
    st.subheader("🔤 캡션 키워드 빈도 TOP 20")
    st.caption("수집 키워드(meitu, 메이투 등) 및 의미없는 태그는 자동 제외")

    keywords_df = extract_keywords(df, top_n=20)

    if keywords_df.empty:
        st.info("키워드 데이터가 없습니다.")
        return

    fig = px.bar(
        keywords_df,
        x="언급수",
        y="키워드",
        orientation="h",
        color="언급수",
        color_continuous_scale=["#E8F4FD", "#E1306C"],
        labels={"언급수": "언급 횟수", "키워드": ""},
    )
    fig.update_layout(
        showlegend=False,
        coloraxis_showscale=False,
        margin=dict(t=10, b=10, l=10, r=10),
        height=420,
        yaxis=dict(autorange="reversed"),
    )
    st.plotly_chart(fig, use_container_width=True)


def render_filters(df):
    """상단 필터 — 국가 + 날짜"""
    col1, col2, col3 = st.columns([1, 1, 2])

    with col1:
        countries   = ["전체"] + sorted(df["country"].unique())
        sel_country = st.selectbox("🌍 국가", countries, index=0)

    with col2:
        ad_options = ["전체"] + sorted(df["ad_type"].unique())
        sel_ad     = st.selectbox("📣 콘텐츠 성격", ad_options, index=0)

    with col3:
        if df["timestamp"].notna().any():
            from datetime import datetime, timedelta, timezone
            now   = datetime.now(timezone.utc)
            quick = st.radio(
                "게시 기간",
                ["최근 7일", "최근 1개월", "최근 3개월", "전체"],
                index=3, horizontal=True
            )
            days_map = {"최근 7일": 7, "최근 1개월": 30, "최근 3개월": 90, "전체": None}
            days = days_map[quick]
            if days:
                start_d = (now - timedelta(days=days)).date()
                end_d   = now.date()
            else:
                start_d = df["timestamp"].min().date()
                end_d   = df["timestamp"].max().date()
        else:
            start_d = end_d = None

    # 필터 적용
    filtered = df.copy()
    if sel_country != "전체":
        filtered = filtered[filtered["country"] == sel_country]
    if sel_ad != "전체":
        filtered = filtered[filtered["ad_type"] == sel_ad]
    if start_d and end_d:
        filtered = filtered[
            (filtered["timestamp"].dt.date >= start_d) &
            (filtered["timestamp"].dt.date <= end_d)
        ]

    st.caption(f"필터 결과: **{len(filtered):,}건**")
    return filtered


def render_cards_by_tab(df):
    """키워드별 탭 + 릴스/피드 탭"""
    st.subheader("📋 게시물 목록")

    # 키워드별 탭
    keywords = ["전체"]
    if "search_keyword" in df.columns:
        keywords += sorted(df["search_keyword"].dropna().unique())

    kw_tabs = st.tabs([f"# {k}" if k != "전체" else "전체" for k in keywords])

    for kw_tab, kw in zip(kw_tabs, keywords):
        with kw_tab:
            kw_df = df if kw == "전체" else df[df["search_keyword"] == kw]

            # 릴스 / 피드 탭
            t_all, t_reel, t_feed, t_kr, t_ad, t_organic = st.tabs([
                "전체", "🎬 릴스", "🖼️ 피드", "🇰🇷 한국", "📢 광고", "🌱 오가닉"
            ])

            with t_all:
                st.html(render_card_grid(kw_df, fmt))
            with t_reel:
                st.html(render_card_grid(kw_df[kw_df["content_type"] == "reel"], fmt))
            with t_feed:
                st.html(render_card_grid(kw_df[kw_df["content_type"].isin(["feed", "video_feed"])], fmt))
            with t_kr:
                st.html(render_card_grid(kw_df[kw_df["is_korean"]], fmt))
            with t_ad:
                st.html(render_card_grid(kw_df[kw_df["ad_type"] == "📢 광고"], fmt))
            with t_organic:
                st.html(render_card_grid(kw_df[kw_df["ad_type"] == "🌱 오가닉"], fmt))


def main():
    st.markdown("## 🔍 Meitu 모니터링 — 세부")

    try:
        df = load_data()
    except FileNotFoundError:
        st.warning("데이터 파일이 없습니다. GitHub Actions를 먼저 실행해주세요.", icon="⚠️")
        return

    if df["last_updated"].notna().any():
        last_kst = df["last_updated"].max() + pd.Timedelta(hours=9)
        st.caption(f"마지막 수집: **{last_kst.strftime('%Y-%m-%d %H:%M')} KST** | 누적: **{len(df):,}건**")

    st.divider()

    # 필터
    df = render_filters(df)

    if df.empty:
        st.info("필터 조건에 맞는 데이터가 없습니다.")
        return

    st.divider()

    # 캡션 키워드 분석
    render_keyword_chart(df)

    st.divider()

    # 게시물 목록
    render_cards_by_tab(df)


if __name__ == "__main__":
    main()
