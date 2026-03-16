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
    with st.expander("🔍 필터 열기", expanded=False):
        col1, col2, col3 = st.columns(3)

        with col1:
            ad_options  = sorted(df["ad_type"].unique())
            sel_ad      = st.multiselect("콘텐츠 성격", ad_options, default=ad_options, key="ad")
            countries   = sorted(df["country"].unique())
            sel_country = st.multiselect("국가", countries, default=countries, key="country")

        with col2:
            labels   = sorted(df["type_label"].unique())
            sel_type = st.multiselect("콘텐츠 유형", labels, default=labels, key="type")
            if "search_keyword" in df.columns:
                kws    = sorted(df["search_keyword"].dropna().unique())
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


def render_kpi_bar(df):
    total   = len(df)
    reels   = (df["content_type"] == "reel").sum()
    feeds   = df["content_type"].isin(["feed","video_feed"]).sum()
    korean  = df["is_korean"].sum()
    ads     = (df["ad_type"] == "📢 광고").sum()
    organic = (df["ad_type"] == "🌱 오가닉").sum()

    st.markdown(
        f"""
        <div style="display:flex;flex-wrap:nowrap;overflow-x:auto;gap:0;
            background:var(--color-background-secondary);border-radius:10px;
            padding:10px 4px;margin-bottom:8px;white-space:nowrap;">
            <div style="flex:1;min-width:55px;text-align:center;padding:0 4px;
                border-right:1px solid var(--color-border-tertiary);">
                <div style="font-size:10px;color:var(--color-text-secondary);">📋 전체</div>
                <div style="font-size:17px;font-weight:500;color:var(--color-text-primary);">{fmt(total)}</div>
            </div>
            <div style="flex:1;min-width:55px;text-align:center;padding:0 4px;
                border-right:1px solid var(--color-border-tertiary);">
                <div style="font-size:10px;color:var(--color-text-secondary);">🎬 릴스</div>
                <div style="font-size:17px;font-weight:500;color:#E1306C;">{fmt(reels)}</div>
            </div>
            <div style="flex:1;min-width:55px;text-align:center;padding:0 4px;
                border-right:1px solid var(--color-border-tertiary);">
                <div style="font-size:10px;color:var(--color-text-secondary);">🖼️ 피드</div>
                <div style="font-size:17px;font-weight:500;color:#405DE6;">{fmt(feeds)}</div>
            </div>
            <div style="flex:1;min-width:55px;text-align:center;padding:0 4px;
                border-right:1px solid var(--color-border-tertiary);">
                <div style="font-size:10px;color:var(--color-text-secondary);">🇰🇷 한국</div>
                <div style="font-size:17px;font-weight:500;color:var(--color-text-primary);">{fmt(korean)}</div>
            </div>
            <div style="flex:1;min-width:55px;text-align:center;padding:0 4px;
                border-right:1px solid var(--color-border-tertiary);">
                <div style="font-size:10px;color:var(--color-text-secondary);">📢 광고</div>
                <div style="font-size:17px;font-weight:500;color:#FF6B00;">{fmt(ads)}</div>
            </div>
            <div style="flex:1;min-width:55px;text-align:center;padding:0 4px;">
                <div style="font-size:10px;color:var(--color-text-secondary);">🌱 오가닉</div>
                <div style="font-size:17px;font-weight:500;color:#2E7D32;">{fmt(organic)}</div>
            </div>
        </div>
        """,
        unsafe_allow_html=True
    )


def render_charts_small(df):
    cmap = {v: TYPE_COLOR.get(k, "#888") for k, v in TYPE_LABEL.items()}
    col1, col2, col3 = st.columns(3)

    with col1:
        st.markdown("**콘텐츠 유형**")
        counts = df["type_label"].value_counts().reset_index()
        counts.columns = ["유형", "건수"]
        fig = px.pie(counts, names="유형", values="건수", hole=0.45,
                     color="유형", color_discrete_map=cmap)
        fig.update_traces(textposition="none")
        fig.update_layout(
            showlegend=True,
            legend=dict(orientation="h", yanchor="bottom", y=-0.35,
                        xanchor="center", x=0.5, font=dict(size=9)),
            margin=dict(t=5, b=40, l=5, r=5), height=180,
        )
        st.plotly_chart(fig, use_container_width=True)

    with col2:
        st.markdown("**광고 vs 오가닉**")
        ad_counts = df["ad_type"].value_counts().reset_index()
        ad_counts.columns = ["유형", "건수"]
        fig2 = px.pie(ad_counts, names="유형", values="건수", hole=0.45,
                      color="유형",
                      color_discrete_map={"📢 광고": "#FF6B00", "🌱 오가닉": "#2E7D32"})
        fig2.update_traces(textposition="none")
        fig2.update_layout(
            showlegend=True,
            legend=dict(orientation="h", yanchor="bottom", y=-0.35,
                        xanchor="center", x=0.5, font=dict(size=9)),
            margin=dict(t=5, b=40, l=5, r=5), height=180,
        )
        st.plotly_chart(fig2, use_container_width=True)

    with col3:
        st.markdown("**국가별 분포**")
        country_counts = df["country"].value_counts().reset_index()
        country_counts.columns = ["국가", "건수"]
        fig3 = px.bar(country_counts, x="국가", y="건수",
                      labels={"국가": "", "건수": ""})
        fig3.update_layout(
            showlegend=False,
            margin=dict(t=5, b=5, l=5, r=5), height=180,
            xaxis=dict(tickfont=dict(size=9)),
            yaxis=dict(tickfont=dict(size=9)),
        )
        st.plotly_chart(fig3, use_container_width=True)


def show_cards(sub_df):
    if sub_df.empty:
        st.info("해당 데이터가 없습니다.")
        return

    top = sub_df.nlargest(50, "engagement").reset_index(drop=True)

    type_colors = {"릴스": "#E1306C", "피드": "#405DE6", "피드(동영상)": "#833AB4"}

    # HTML 그리드로 직접 구성 — 모바일 2열 / PC 4열
    cards_html = """
    <style>
    .ig-grid {
        display: grid;
        grid-template-columns: repeat(4, 1fr);
        gap: 12px;
        margin-top: 8px;
    }
    @media (max-width: 768px) {
        .ig-grid { grid-template-columns: repeat(2, 1fr); gap: 8px; }
    }
    .ig-card {
        background: var(--background-color, #fff);
        border: 0.5px solid rgba(128,128,128,0.2);
        border-radius: 10px;
        overflow: hidden;
    }
    .ig-card img {
        width: 100%; aspect-ratio: 1; object-fit: cover; display: block;
    }
    .ig-card-placeholder {
        width: 100%; aspect-ratio: 1;
        background: #f0f0f0;
        display: flex; align-items: center; justify-content: center;
        font-size: 28px;
    }
    .ig-card-body { padding: 7px 8px 10px; }
    .ig-badges { display: flex; gap: 3px; flex-wrap: wrap; margin-bottom: 4px; }
    .ig-badge {
        font-size: 9px; font-weight: 500;
        padding: 1px 6px; border-radius: 10px; color: white;
    }
    .ig-meta { font-size: 10px; color: #888; margin-bottom: 2px; }
    .ig-user { font-size: 11px; font-weight: 500; margin-bottom: 3px; }
    .ig-stats { font-size: 11px; margin-bottom: 4px; }
    .ig-link { font-size: 10px; color: #E1306C; text-decoration: none; }
    </style>
    <div class="ig-grid">
    """

    for _, row in top.iterrows():
        thumb      = str(row.get("displayUrl", ""))
        t_color    = type_colors.get(row["type_label"], "#888")
        ad_color   = "#FF6B00" if row["ad_type"] == "📢 광고" else "#2E7D32"
        date_str   = row["timestamp"].strftime("%Y-%m-%d") if pd.notna(row["timestamp"]) else "-"
        country    = row.get("country", "")
        username   = str(row.get("ownerUsername", "-"))
        metric     = f"▶ {fmt(row['videoPlayCount'])}" if row["content_type"] == "reel" else f"❤ {fmt(row['likesCount'])}"
        comments   = fmt(row["commentsCount"])
        url        = str(row.get("url", ""))
        link_html  = f'<a class="ig-link" href="{url}" target="_blank">📎 보기</a>' if url.startswith("http") else ""

        if thumb and thumb not in ("nan", ""):
            thumb_html = f'<img src="{thumb}" loading="lazy" onerror="this.parentNode.innerHTML=\'<div class=ig-card-placeholder>🖼️</div>\'">'
        else:
            thumb_html = '<div class="ig-card-placeholder">🖼️</div>'

        cards_html += f"""
        <div class="ig-card">
            {thumb_html}
            <div class="ig-card-body">
                <div class="ig-badges">
                    <span class="ig-badge" style="background:{t_color};">{row["type_label"]}</span>
                    <span class="ig-badge" style="background:{ad_color};">{row["ad_type"]}</span>
                </div>
                <div class="ig-meta">{date_str} | {country}</div>
                <div class="ig-user">@{username}</div>
                <div class="ig-stats">{metric} &nbsp; 💬 {comments}</div>
                {link_html}
            </div>
        </div>
        """

    cards_html += "</div>"
    st.html(cards_html)


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

    df = render_filters(df)

    if df.empty:
        st.info("필터 조건에 맞는 데이터가 없습니다.")
        return

    render_kpi_bar(df)
    st.divider()
    render_charts_small(df)
    st.divider()

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
