import re
import pandas as pd
import streamlit as st
import plotly.express as px

st.set_page_config(page_title="Meitu 모니터링", page_icon="📊", layout="wide")

TYPE_COLOR = {
    "reel":       "#E1306C",
    "feed":       "#405DE6",
    "video_feed": "#833AB4",
    "unknown":    "#AAAAAA",
}
TYPE_LABEL = {
    "reel":       "릴스",
    "feed":       "피드",
    "video_feed": "피드(동영상)",
    "unknown":    "미분류",
}


@st.cache_data(ttl=300)
def load_data():
    df = pd.read_csv("data/latest_monitoring.csv", dtype=str)

    for col in ("likesCount", "commentsCount", "videoPlayCount"):
        df[col] = pd.to_numeric(df.get(col, 0), errors="coerce").fillna(0).astype(int)

    df["timestamp"]    = pd.to_datetime(df.get("timestamp", ""), errors="coerce", utc=True)
    df["last_updated"] = pd.to_datetime(df.get("last_updated", ""), errors="coerce")
    df["engagement"]   = df["likesCount"] + df["commentsCount"]
    df["type_label"]   = df["content_type"].map(TYPE_LABEL).fillna("미분류")

    # 한국 콘텐츠 감지
    if "is_korean" not in df.columns:
        df["is_korean"] = df.get("caption", "").apply(
            lambda x: bool(re.search(r'[가-힣]', str(x)))
        )
    df["is_korean"] = df["is_korean"].astype(str).str.lower() == "true"

    # 슬라이드 자식 row 제거
    df = df[df.get("content_type", "") != "carousel_item"].reset_index(drop=True)
    return df


def fmt(n):
    n = int(n)
    if n >= 10000: return f"{n/10000:.1f}만"
    if n >= 1000:  return f"{n/1000:.1f}천"
    return str(n)


# ── 사이드바 필터 ──────────────────────────────────────────────────────────────
def sidebar(df):
    with st.sidebar:
        st.header("🔍 필터")

        # 한국 콘텐츠 토글
        korean_only = st.toggle("🇰🇷 한국 콘텐츠만 보기", value=False)
        if korean_only:
            df = df[df["is_korean"]]

        # 콘텐츠 유형
        labels = sorted(df["type_label"].unique())
        sel_type = st.multiselect("콘텐츠 유형", labels, default=labels)
        df = df[df["type_label"].isin(sel_type)]

        # 날짜 범위
        if df["timestamp"].notna().any():
            min_d = df["timestamp"].min().date()
            max_d = df["timestamp"].max().date()
            d = st.date_input("게시 기간", (min_d, max_d), min_value=min_d, max_value=max_d)
            if isinstance(d, (list, tuple)) and len(d) == 2:
                df = df[
                    (df["timestamp"].dt.date >= d[0]) &
                    (df["timestamp"].dt.date <= d[1])
                ]

        # 수집 키워드
        if "search_keyword" in df.columns:
            kws = sorted(df["search_keyword"].dropna().unique())
            sel_kw = st.multiselect("수집 키워드", kws, default=kws)
            df = df[df["search_keyword"].isin(sel_kw)]

        st.divider()
        st.caption(f"필터 결과: **{len(df):,}건**")
        st.download_button(
            "📥 CSV 다운로드",
            df.to_csv(index=False, encoding="utf-8-sig").encode("utf-8-sig"),
            "meitu_monitoring.csv", "text/csv",
            use_container_width=True,
        )
    return df


# ── 게시물 테이블 ──────────────────────────────────────────────────────────────
def show_table(sub_df):
    if sub_df.empty:
        st.info("해당 데이터가 없습니다.")
        return

    display = sub_df.copy()
    display["날짜"]   = display["timestamp"].dt.strftime("%Y-%m-%d").fillna("-")
    display["유형"]   = display["type_label"]
    display["🇰🇷"]    = display["is_korean"].apply(lambda x: "🇰🇷" if x else "")
    display["작성자"] = display.get("ownerUsername", "-").fillna("-")
    display["캡션"]   = display.get("caption", "").fillna("").str[:60] + "..."

    # 릴스는 조회수, 피드는 좋아요를 메인 지표로 표시
    def main_metric(row):
        if row["content_type"] == "reel":
            v = row["videoPlayCount"]
            return f"▶ {fmt(v)}"
        else:
            v = row["likesCount"]
            return f"❤ {fmt(v)}"

    display["주요지표"] = display.apply(main_metric, axis=1)
    display["댓글"]    = display["commentsCount"].apply(fmt)

    # 인스타 링크 버튼
    display["링크"] = display.get("url", "").apply(
        lambda u: f'<a href="{u}" target="_blank" style="color:#E1306C;">📎 열기</a>'
        if pd.notna(u) and str(u).startswith("http") else "-"
    )

    show_cols = ["날짜", "유형", "🇰🇷", "작성자", "캡션", "주요지표", "댓글", "링크"]
    show_cols = [c for c in show_cols if c in display.columns]

    st.write(
        display.nlargest(50, "engagement")[show_cols]
        .reset_index(drop=True)
        .to_html(escape=False, index=False),
        unsafe_allow_html=True,
    )


# ── 메인 ──────────────────────────────────────────────────────────────────────
def main():
    st.markdown("## 📱 Meitu 인스타그램 모니터링")

    try:
        df = load_data()
    except FileNotFoundError:
        st.warning("데이터 파일이 없습니다. GitHub Actions를 먼저 실행해주세요.", icon="⚠️")
        return

    if df["last_updated"].notna().any():
        st.caption(
            f"마지막 수집: **{df['last_updated'].max().strftime('%Y-%m-%d %H:%M')}** "
            f"| 누적: **{len(df):,}건**"
        )

    df = sidebar(df)

    if df.empty:
        st.info("필터 조건에 맞는 데이터가 없습니다.")
        return

    # ── KPI 카드 ────────────────────────────────────────────────────────────
    total  = len(df)
    reels  = (df["content_type"] == "reel").sum()
    feeds  = df["content_type"].isin(["feed", "video_feed"]).sum()
    korean = df["is_korean"].sum()
    avg_likes = df["likesCount"].mean()

    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("📋 전체",          fmt(total))
    c2.metric("🎬 릴스",          fmt(reels))
    c3.metric("🖼️ 피드",          fmt(feeds))
    c4.metric("🇰🇷 한국 콘텐츠",  fmt(korean))
    c5.metric("❤️ 평균 좋아요",   f"{avg_likes:.1f}")

    st.divider()

    # ── 차트 ────────────────────────────────────────────────────────────────
    cmap = {v: TYPE_COLOR.get(k, "#888") for k, v in TYPE_LABEL.items()}
    col1, col2 = st.columns(2)

    with col1:
        st.subheader("콘텐츠 유형 비율")
        counts = df["type_label"].value_counts().reset_index()
        counts.columns = ["유형", "건수"]
        fig = px.pie(
            counts, names="유형", values="건수", hole=0.4,
            color="유형", color_discrete_map=cmap,
        )
        fig.update_traces(textposition="outside", textinfo="percent+label")
        fig.update_layout(showlegend=False, margin=dict(t=20, b=0, l=0, r=0))
        st.plotly_chart(fig, use_container_width=True)

    with col2:
        st.subheader("키워드별 수집량")
        if "search_keyword" in df.columns:
            kw = (
                df.groupby(["search_keyword", "type_label"])
                .size().reset_index(name="count")
            )
            fig2 = px.bar(
                kw, x="search_keyword", y="count",
                color="type_label", color_discrete_map=cmap,
                barmode="stack",
                labels={"search_keyword": "키워드", "count": "건수", "type_label": "유형"},
            )
            fig2.update_layout(showlegend=True, margin=dict(t=20, b=0))
            st.plotly_chart(fig2, use_container_width=True)

    st.divider()

    # ── 게시물 목록 탭 ───────────────────────────────────────────────────────
    st.subheader("📋 게시물 목록")
    st.caption("릴스는 조회수(▶), 피드는 좋아요(❤) 기준 상위 50건 표시 | 링크 클릭 시 인스타그램으로 이동")

    tab_all, tab_reel, tab_feed, tab_kr = st.tabs(
        ["전체", "🎬 릴스", "🖼️ 피드", "🇰🇷 한국 콘텐츠"]
    )
    with tab_all:  show_table(df)
    with tab_reel: show_table(df[df["content_type"] == "reel"])
    with tab_feed: show_table(df[df["content_type"].isin(["feed", "video_feed"])])
    with tab_kr:   show_table(df[df["is_korean"]])


if __name__ == "__main__":
    main()
