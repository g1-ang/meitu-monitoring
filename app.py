import pandas as pd
import streamlit as st
import plotly.express as px
from datetime import datetime, timedelta, timezone
from utils import load_and_process, get_weekly_df, fmt, TYPE_COLOR, TYPE_LABEL, render_card_grid

st.set_page_config(page_title="Meitu 모니터링", page_icon="📊", layout="wide")


@st.cache_data(ttl=300)
def load_data():
    return load_and_process("data/latest_monitoring.csv")


def render_kpi_bar(this_week, last_week):
    """KPI + 지난주 대비 변화량 한 줄 표시"""
    def delta(a, b):
        diff = a - b
        if diff > 0:  return f'<span style="color:#2E7D32;font-size:10px;">▲ {diff}</span>'
        if diff < 0:  return f'<span style="color:#E1306C;font-size:10px;">▼ {abs(diff)}</span>'
        return '<span style="color:#888;font-size:10px;">- 0</span>'

    metrics = [
        ("📋 전체",    len(this_week),                                          len(last_week),                                          "var(--color-text-primary)"),
        ("🎬 릴스",    (this_week["content_type"]=="reel").sum(),               (last_week["content_type"]=="reel").sum(),               "#E1306C"),
        ("🖼️ 피드",    this_week["content_type"].isin(["feed","video_feed"]).sum(), last_week["content_type"].isin(["feed","video_feed"]).sum(), "#405DE6"),
        ("🇰🇷 한국",   this_week["is_korean"].sum(),                            last_week["is_korean"].sum(),                            "var(--color-text-primary)"),
        ("📢 광고",    (this_week["ad_type"]=="📢 광고").sum(),                 (last_week["ad_type"]=="📢 광고").sum(),                 "#FF6B00"),
        ("🌱 오가닉",  (this_week["ad_type"]=="🌱 오가닉").sum(),               (last_week["ad_type"]=="🌱 오가닉").sum(),               "#2E7D32"),
    ]

    items_html = ""
    for i, (label, cur, prev, color) in enumerate(metrics):
        border = "border-right:1px solid var(--color-border-tertiary);" if i < len(metrics)-1 else ""
        items_html += f"""
        <div style="flex:1;min-width:55px;text-align:center;padding:0 4px;{border}">
            <div style="font-size:10px;color:var(--color-text-secondary);">{label}</div>
            <div style="font-size:17px;font-weight:500;color:{color};">{fmt(cur)}</div>
            {delta(cur, prev)}
        </div>
        """

    st.markdown(
        f'<div style="display:flex;flex-wrap:nowrap;overflow-x:auto;'
        f'background:var(--color-background-secondary);border-radius:10px;'
        f'padding:10px 4px;margin-bottom:8px;">{items_html}</div>',
        unsafe_allow_html=True
    )


def render_charts(df):
    cmap = {v: TYPE_COLOR.get(k, "#888") for k, v in TYPE_LABEL.items()}
    col1, col2, col3 = st.columns(3)

    with col1:
        st.markdown("**콘텐츠 유형**")
        counts = df["type_label"].value_counts().reset_index()
        counts.columns = ["유형", "건수"]
        fig = px.pie(counts, names="유형", values="건수", hole=0.45,
                     color="유형", color_discrete_map=cmap)
        fig.update_traces(textposition="none")
        fig.update_layout(showlegend=True,
            legend=dict(orientation="h", yanchor="bottom", y=-0.35, xanchor="center", x=0.5, font=dict(size=9)),
            margin=dict(t=5, b=40, l=5, r=5), height=180)
        st.plotly_chart(fig, use_container_width=True)

    with col2:
        st.markdown("**광고 vs 오가닉**")
        ad_counts = df["ad_type"].value_counts().reset_index()
        ad_counts.columns = ["유형", "건수"]
        fig2 = px.pie(ad_counts, names="유형", values="건수", hole=0.45,
                      color="유형", color_discrete_map={"📢 광고": "#FF6B00", "🌱 오가닉": "#2E7D32"})
        fig2.update_traces(textposition="none")
        fig2.update_layout(showlegend=True,
            legend=dict(orientation="h", yanchor="bottom", y=-0.35, xanchor="center", x=0.5, font=dict(size=9)),
            margin=dict(t=5, b=40, l=5, r=5), height=180)
        st.plotly_chart(fig2, use_container_width=True)

    with col3:
        st.markdown("**국가별 분포**")
        cc = df["country"].value_counts().reset_index()
        cc.columns = ["국가", "건수"]
        fig3 = px.bar(cc, x="국가", y="건수", labels={"국가": "", "건수": ""})
        fig3.update_layout(showlegend=False,
            margin=dict(t=5, b=5, l=5, r=5), height=180,
            xaxis=dict(tickfont=dict(size=9)), yaxis=dict(tickfont=dict(size=9)))
        st.plotly_chart(fig3, use_container_width=True)


def render_top5(df):
    """TOP 5 — 릴스 / 피드 탭 분리"""
    st.subheader("🏆 이번 주 TOP 5")

    tab_reel, tab_feed = st.tabs(["🎬 릴스 TOP 5", "🖼️ 피드 TOP 5"])

    def top5_cards(sub_df, metric_col):
        top = sub_df.nlargest(5, metric_col).reset_index(drop=True)
        if top.empty:
            st.info("데이터가 없습니다.")
            return

        cols = st.columns(5)
        type_colors = {"릴스": "#E1306C", "피드": "#405DE6", "피드(동영상)": "#833AB4"}

        for i, col in enumerate(cols):
            if i >= len(top):
                break
            row = top.iloc[i]
            with col:
                thumb = str(row.get("displayUrl", ""))
                if thumb and thumb not in ("nan", ""):
                    try:
                        st.image(thumb, use_container_width=True)
                    except:
                        st.markdown("<div style='background:#f0f0f0;height:80px;border-radius:6px;'></div>", unsafe_allow_html=True)
                else:
                    st.markdown("<div style='background:#f0f0f0;height:80px;border-radius:6px;display:flex;align-items:center;justify-content:center;font-size:20px;'>🖼️</div>", unsafe_allow_html=True)

                t_color = type_colors.get(row["type_label"], "#888")
                metric  = f"▶ {fmt(row['videoPlayCount'])}" if row["content_type"] == "reel" else f"❤ {fmt(row['likesCount'])}"
                url     = str(row.get("url", ""))
                link    = f'<a href="{url}" target="_blank" style="font-size:10px;color:#E1306C;">📎 보기</a>' if url.startswith("http") else ""

                st.markdown(
                    f'<span style="background:{t_color};color:white;font-size:9px;padding:1px 5px;border-radius:8px;">{row["type_label"]}</span>'
                    f'<div style="font-size:10px;color:#888;margin-top:2px;">{row.get("country","")}</div>'
                    f'<div style="font-size:11px;font-weight:500;">@{str(row.get("ownerUsername","-"))}</div>'
                    f'<div style="font-size:11px;">{metric}</div>'
                    f'{link}',
                    unsafe_allow_html=True
                )

    with tab_reel:
        top5_cards(df[df["content_type"] == "reel"], "videoPlayCount")
    with tab_feed:
        top5_cards(df[df["content_type"].isin(["feed", "video_feed"])], "likesCount")


def main():
    st.markdown("## 📊 Meitu 모니터링 — 요약")

    try:
        df = load_data()
    except FileNotFoundError:
        st.warning("데이터 파일이 없습니다. GitHub Actions를 먼저 실행해주세요.", icon="⚠️")
        return

    if df["last_updated"].notna().any():
        last_kst = df["last_updated"].max() + pd.Timedelta(hours=9)
        st.caption(f"마지막 수집: **{last_kst.strftime('%Y-%m-%d %H:%M')} KST** | 누적: **{len(df):,}건**")

    # 국가 필터
    countries    = ["전체"] + sorted(df["country"].unique())
    sel_country  = st.selectbox("🌍 국가 필터", countries, index=0)
    filtered_df  = df if sel_country == "전체" else df[df["country"] == sel_country]

    st.divider()

    # 이번 주 / 지난 주
    this_week = get_weekly_df(filtered_df, weeks_ago=0)
    last_week = get_weekly_df(filtered_df, weeks_ago=1)

    st.markdown(f"**이번 주** {this_week['timestamp'].min().strftime('%m/%d') if not this_week.empty else '-'} ~ 오늘 &nbsp;|&nbsp; 지난주 대비 변화")
    render_kpi_bar(this_week, last_week)

    st.divider()
    render_charts(filtered_df)

    st.divider()
    render_top5(this_week if not this_week.empty else filtered_df)


if __name__ == "__main__":
    main()
