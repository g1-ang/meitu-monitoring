import re
import pandas as pd
import streamlit as st
import plotly.express as px

st.set_page_config(page_title="Meitu 모니터링", page_icon="📊", layout="wide")

TYPE_COLOR = {
    "reel":       "#E1306C",
    "feed":       "#405DE6",
    "video_feed": "#833AB4",
}
TYPE_LABEL = {
    "reel":       "릴스",
    "feed":       "피드",
    "video_feed": "피드(동영상)",
}

AD_KEYWORDS = [
    "광고", "유료광고", "유료_광고", "ad", "sponsored", "collaboration",
    "콜라보", "협찬", "제공", "paid", "promotion"
]


def detect_country(text: str) -> str:
    t = str(text)
    if re.search(r'[가-힣]', t):           return "🇰🇷 한국"
    if re.search(r'[\u3040-\u30FF]', t):   return "🇯🇵 일본"
    if re.search(r'[\u4E00-\u9FFF]', t):   return "🇨🇳 중국/대만"
    if re.search(r'[\u0E00-\u0E7F]', t):   return "🇹🇭 태국"
    if re.search(r'[\u0600-\u06FF]', t):   return "🇸🇦 아랍"
    if re.search(r'[à-öø-ÿÀ-ÖØ-ß]', t):   return "🇪🇺 유럽"
    if re.search(r'[a-zA-Z]', t):          return "🌐 영어권"
    return "🌏 기타"


def detect_ad(text: str) -> str:
    t = str(text).lower()
    for kw in AD_KEYWORDS:
        if f"#{kw.lower()}" in t or f" {kw.lower()} " in t or t.startswith(kw.lower()):
            return "📢 광고"
    return "🌱 오가닉"


@st.cache_data(ttl=300)
def load_data():
    df = pd.read_csv("data/latest_monitoring.csv", dtype=str)

    for col in ("likesCount", "commentsCount", "videoPlayCount"):
        df[col] = pd.to_numeric(df.get(col, 0), errors="coerce").fillna(0).astype(int)

    df["timestamp"]    = pd.to_datetime(df.get("timestamp", ""), errors="coerce", utc=True)
    df["last_updated"] = pd.to_datetime(df.get("last_updated", ""), errors="coerce")
    df["engagement"]   = df["likesCount"] + df["commentsCount"]

    def classify(row):
        product_type = str(row.get("productType", "")).lower().strip()
        media_type   = str(row.get("type", "")).lower().strip()
        url          = str(row.get("url", ""))
        video_url    = str(row.get("videoUrl", ""))

        if product_type == "clips":                         return "reel"
        if product_type == "carousel_item":                 return "carousel_item"
        if product_type in ("feed", "carousel_container"):  return "feed"
        if video_url and video_url not in ("nan", ""):      return "reel"
        if media_type == "video":
            return "reel" if "/reel/" in url else "video_feed"
        if media_type in ("image", "sidecar"):              return "feed"
        return "unknown"

    df["content_type"] = df.apply(classify, axis=1)
    df = df[~df["content_type"].isin(["carousel_item", "unknown"])].reset_index(drop=True)
    df["type_label"]  = df["content_type"].map(TYPE_LABEL).fillna("기타")

    if "caption" in df.columns:
        df["caption"] = (
            df["caption"].astype(str)
            .str.replace(r'\\n', ' ', regex=True)
            .str.replace(r'\n', ' ', regex=True)
            .str.strip()
        )

    df["country"]   = df.get("caption", "").apply(detect_country)
    df["ad_type"]   = df.get("caption", "").apply(detect_ad)
    df["is_korean"] = df["country"] == "🇰🇷 한국"

    return df


def fmt(n):
    n = int(n)
    if n >= 10000: return f"{n/10000:.1f}만"
    if n >= 1000:  return f"{n/1000:.1f}천"
    return str(n)


def render_filters(df):
    """사이드바 대신 페이지 상단 필터 (모바일 친화적)"""
    with st.expander("🔍 필터 열기", expanded=False):
        col1, col2, col3 = st.columns(3)

        with col1:
            ad_options = sorted(df["ad_type"].unique())
            sel_ad = st.multiselect("콘텐츠 성격", ad_options, default=ad_options, key="ad")

            countries = sorted(df["country"].unique())
            sel_country = st.multiselect("국가", countries, default=countries, key="country")

        with col2:
            labels = sorted(df["type_label"].unique())
            sel_type = st.multiselect("콘텐츠 유형", labels, default=labels, key="type")

            if "search_keyword" in df.columns:
                kws = sorted(df["search_keyword"].dropna().unique())
                sel_kw = st.multiselect("수집 키워드", kws, default=kws, key="kw")
            else:
                sel_kw = []

        with col3:
            if df["timestamp"].notna().any():
                min_d = df["timestamp"].min().date()
                max_d = df["timestamp"].max().date()
                d = st.date_input("게시 기간", (min_d, max_d), min_value=min_d, max_value=max_d)
            else:
                d = None

            st.markdown("<br>", unsafe_allow_html=True)
            st.download_button(
                "📥 CSV 다운로드",
                df.to_csv(index=False, encoding="utf-8-sig").encode("utf-8-sig"),
                "meitu_monitoring.csv", "text/csv",
                use_container_width=True,
            )

    # 필터 적용
    df = df[df["ad_type"].isin(sel_ad)]
    df = df[df["country"].isin(sel_country)]
    df = df[df["type_label"].isin(sel_type)]
    if sel_kw:
        df = df[df["search_keyword"].isin(sel_kw)]
    if d and isinstance(d, (list, tuple)) and len(d) == 2:
        df = df[
            (df["timestamp"].dt.date >= d[0]) &
            (df["timestamp"].dt.date <= d[1])
        ]

    st.caption(f"필터 결과: **{len(df):,}건**")
    return df


def show_cards(sub_df):
    if sub_df.empty:
        st.info("해당 데이터가 없습니다.")
        return

    top = sub_df.nlargest(50, "engagement").reset_index(drop=True)

    # PC: 4열 / 모바일: 2열 — st.columns로 4열 고정 후 CSS로 모바일 대응
    cols_per_row = 4
    for i in range(0, len(top), cols_per_row):
        cols = st.columns(cols_per_row)
        for j, col in enumerate(cols):
            idx = i + j
            if idx >= len(top):
                break
            row = top.iloc[idx]

            with col:
                # 썸네일
                thumb = str(row.get("displayUrl", ""))
                if thumb and thumb not in ("nan", ""):
                    try:
                        st.image(thumb, use_container_width=True)
                    except:
                        st.markdown(
                            "<div style='background:#f0f0f0;height:120px;border-radius:8px;"
                            "display:flex;align-items:center;justify-content:center;"
                            "font-size:28px;'>🖼️</div>",
                            unsafe_allow_html=True
                        )
                else:
                    st.markdown(
                        "<div style='background:#f0f0f0;height:120px;border-radius:8px;"
                        "display:flex;align-items:center;justify-content:center;"
                        "font-size:28px;'>🖼️</div>",
                        unsafe_allow_html=True
                    )

                # 유형 + 광고 배지
                type_colors = {"릴스": "#E1306C", "피드": "#405DE6", "피드(동영상)": "#833AB4"}
                t_color   = type_colors.get(row["type_label"], "#888")
                ad_color  = "#FF6B00" if row["ad_type"] == "📢 광고" else "#2E7D32"

                st.markdown(
                    f'<div style="margin-top:5px;display:flex;gap:3px;flex-wrap:wrap;">'
                    f'<span style="background:{t_color};color:white;font-size:10px;'
                    f'padding:1px 6px;border-radius:10px;">{row["type_label"]}</span>'
                    f'<span style="background:{ad_color};color:white;font-size:10px;'
                    f'padding:1px 6px;border-radius:10px;">{row["ad_type"]}</span>'
                    f'</div>',
                    unsafe_allow_html=True
                )

                # 날짜 + 국가
                date_str = row["timestamp"].strftime("%Y-%m-%d") if pd.notna(row["timestamp"]) else "-"
                st.markdown(
                    f'<div style="font-size:11px;color:#888;margin-top:3px;">'
                    f'{date_str}<br>{row.get("country","")}</div>',
                    unsafe_allow_html=True
                )

                # 작성자
                username = str(row.get("ownerUsername", "-"))
                st.markdown(
                    f'<div style="font-size:12px;font-weight:500;margin-top:2px;">'
                    f'@{username}</div>',
                    unsafe_allow_html=True
                )

                # 주요지표 + 댓글
                metric = f"▶ {fmt(row['videoPlayCount'])}" if row["content_type"] == "reel" else f"❤ {fmt(row['likesCount'])}"
                st.markdown(
                    f'<div style="font-size:12px;margin-top:3px;">'
                    f'{metric} &nbsp; 💬 {fmt(row["commentsCount"])}</div>',
                    unsafe_allow_html=True
                )

                # 링크
                url = str(row.get("url", ""))
                if url.startswith("http"):
                    st.markdown(
                        f'<a href="{url}" target="_blank" '
                        f'style="font-size:11px;color:#E1306C;text-decoration:none;">'
                        f'📎 보기</a>',
                        unsafe_allow_html=True
                    )

                st.markdown("<div style='margin-bottom:12px;'></div>", unsafe_allow_html=True)


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

    # 필터 (페이지 상단 expander)
    df = render_filters(df)

    if df.empty:
        st.info("필터 조건에 맞는 데이터가 없습니다.")
        return

    st.divider()

    # KPI
    c1, c2, c3, c4, c5, c6 = st.columns(6)
    c1.metric("📋 전체",         fmt(len(df)))
    c2.metric("🎬 릴스",         fmt((df["content_type"] == "reel").sum()))
    c3.metric("🖼️ 피드",         fmt(df["content_type"].isin(["feed","video_feed"]).sum()))
    c4.metric("🇰🇷 한국",        fmt(df["is_korean"].sum()))
    c5.metric("📢 광고",         fmt((df["ad_type"] == "📢 광고").sum()))
    c6.metric("🌱 오가닉",       fmt((df["ad_type"] == "🌱 오가닉").sum()))

    st.divider()

    # 차트
    cmap = {v: TYPE_COLOR.get(k, "#888") for k, v in TYPE_LABEL.items()}
    col1, col2, col3 = st.columns(3)

    with col1:
        st.subheader("콘텐츠 유형")
        counts = df["type_label"].value_counts().reset_index()
        counts.columns = ["유형", "건수"]
        fig = px.pie(counts, names="유형", values="건수", hole=0.4,
                     color="유형", color_discrete_map=cmap)
        fig.update_traces(textposition="outside", textinfo="percent+label")
        fig.update_layout(showlegend=False, margin=dict(t=20, b=0, l=0, r=0))
        st.plotly_chart(fig, use_container_width=True)

    with col2:
        st.subheader("광고 vs 오가닉")
        ad_counts = df["ad_type"].value_counts().reset_index()
        ad_counts.columns = ["유형", "건수"]
        fig2 = px.pie(ad_counts, names="유형", values="건수", hole=0.4,
                      color="유형",
                      color_discrete_map={"📢 광고": "#FF6B00", "🌱 오가닉": "#2E7D32"})
        fig2.update_traces(textposition="outside", textinfo="percent+label")
        fig2.update_layout(showlegend=False, margin=dict(t=20, b=0, l=0, r=0))
        st.plotly_chart(fig2, use_container_width=True)

    with col3:
        st.subheader("국가별 분포")
        country_counts = df["country"].value_counts().reset_index()
        country_counts.columns = ["국가", "건수"]
        fig3 = px.bar(country_counts, x="국가", y="건수",
                      labels={"국가": "", "건수": "건수"})
        fig3.update_layout(showlegend=False, margin=dict(t=20, b=0))
        st.plotly_chart(fig3, use_container_width=True)

    st.divider()

    # 게시물 카드
    st.subheader("📋 게시물 목록")
    st.caption("인게이지먼트 기준 상위 50건 | 링크 클릭 시 인스타그램으로 이동")

    tab_all, tab_reel, tab_feed, tab_kr, tab_ad, tab_organic = st.tabs([
        "전체", "🎬 릴스", "🖼️ 피드", "🇰🇷 한국", "📢 광고", "🌱 오가닉"
    ])
    with tab_all:     show_cards(df)
    with tab_reel:    show_cards(df[df["content_type"] == "reel"])
    with tab_feed:    show_cards(df[df["content_type"].isin(["feed", "video_feed"])])
    with tab_kr:      show_cards(df[df["is_korean"]])
    with tab_ad:      show_cards(df[df["ad_type"] == "📢 광고"])
    with tab_organic: show_cards(df[df["ad_type"] == "🌱 오가닉"])


if __name__ == "__main__":
    main()
