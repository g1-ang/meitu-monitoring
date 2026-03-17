import pandas as pd
import streamlit as st
import plotly.express as px
from utils import load_and_process, get_weekly_df, get_week_range, extract_keywords, fmt, TYPE_COLOR, TYPE_LABEL

st.set_page_config(page_title="Meitu 모니터링", page_icon="📊", layout="wide")


@st.cache_data(ttl=300)
def load_data():
    return load_and_process("data/latest_monitoring.csv")


def render_kpi_bar(this_week, last_week):
    metrics = [
        ("📋 전체",   len(this_week),                                               len(last_week)),
        ("🎬 릴스",   (this_week["content_type"]=="reel").sum(),                    (last_week["content_type"]=="reel").sum()),
        ("🖼️ 피드",   this_week["content_type"].isin(["feed","video_feed"]).sum(),  last_week["content_type"].isin(["feed","video_feed"]).sum()),
        ("🇰🇷 한국",  this_week["is_korean"].sum(),                                 last_week["is_korean"].sum()),
        ("📢 광고",   (this_week["ad_type"]=="📢 광고").sum(),                      (last_week["ad_type"]=="📢 광고").sum()),
        ("🌱 오가닉", (this_week["ad_type"]=="🌱 오가닉").sum(),                    (last_week["ad_type"]=="🌱 오가닉").sum()),
    ]
    cols = st.columns(len(metrics))
    for col, (label, cur, prev) in zip(cols, metrics):
        diff        = int(cur) - int(prev)
        delta_str   = f"▲ {diff}" if diff > 0 else (f"▼ {abs(diff)}" if diff < 0 else "변화없음")
        delta_color = "normal" if diff > 0 else ("inverse" if diff < 0 else "off")
        col.metric(label=label, value=fmt(cur), delta=delta_str, delta_color=delta_color)


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
                      color="유형",
                      color_discrete_map={"📢 광고": "#FF6B00", "🌱 오가닉": "#2E7D32"})
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
            xaxis=dict(tickfont=dict(size=9)),
            yaxis=dict(tickfont=dict(size=9)))
        st.plotly_chart(fig3, use_container_width=True)


def render_keywords(df):
    """캡션 키워드 빈도 TOP 15 바차트"""
    st.subheader("🔤 캡션 키워드 TOP 15")
    st.caption("수집 키워드(meitu, 뷰티캠 등) 및 의미없는 태그 자동 제외 — 경쟁사 마케팅 주제 파악용")

    kw_df = extract_keywords(df, top_n=15)
    if kw_df.empty:
        st.info("키워드 데이터가 없습니다.")
        return

    fig = px.bar(
        kw_df,
        x="언급수",
        y="키워드",
        orientation="h",
        color="언급수",
        color_continuous_scale=["#E8F4FD", "#E1306C"],
        labels={"언급수": "언급 횟수", "키워드": ""},
        text="언급수",
    )
    fig.update_traces(textposition="outside")
    fig.update_layout(
        showlegend=False,
        coloraxis_showscale=False,
        margin=dict(t=10, b=10, l=10, r=60),
        height=420,
        yaxis=dict(autorange="reversed"),
    )
    st.plotly_chart(fig, use_container_width=True)


def render_top5(df):
    st.subheader("🏆 이번 주 TOP 5")
    st.caption("릴스: 조회수 기준 / 피드: 좋아요 기준")

    tab_reel, tab_feed = st.tabs(["🎬 릴스 TOP 5", "🖼️ 피드 TOP 5"])

    def top5_cards(sub_df, metric_col):
        top = sub_df.nlargest(5, metric_col).reset_index(drop=True)
        if top.empty:
            st.info("해당 기간 데이터가 없습니다.")
            return

        type_colors = {"릴스": "#E1306C", "피드": "#405DE6", "피드(동영상)": "#833AB4"}
        cols = st.columns(5)

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
                        st.markdown("<div style='background:#f0f0f0;height:100px;border-radius:6px;display:flex;align-items:center;justify-content:center;font-size:20px;'>🖼️</div>", unsafe_allow_html=True)
                else:
                    st.markdown("<div style='background:#f0f0f0;height:100px;border-radius:6px;display:flex;align-items:center;justify-content:center;font-size:20px;'>🖼️</div>", unsafe_allow_html=True)

                t_color  = type_colors.get(row["type_label"], "#888")
                ad_color = "#FF6B00" if row["ad_type"] == "📢 광고" else "#2E7D32"
                metric   = f"▶ {fmt(row['videoPlayCount'])}" if row["content_type"] == "reel" else f"❤ {fmt(row['likesCount'])}"
                url      = str(row.get("url", ""))
                link     = f'<a href="{url}" target="_blank" style="font-size:10px;color:#E1306C;text-decoration:none;">📎 보기</a>' if url.startswith("http") else ""
                date_str = row["timestamp"].strftime("%m/%d") if pd.notna(row["timestamp"]) else "-"

                st.markdown(
                    f'<div style="margin-top:5px;">'
                    f'<span style="background:{t_color};color:white;font-size:9px;padding:1px 5px;border-radius:8px;">{row["type_label"]}</span>'
                    f'<span style="background:{ad_color};color:white;font-size:9px;padding:1px 5px;border-radius:8px;margin-left:3px;">{row["ad_type"]}</span>'
                    f'<div style="font-size:10px;color:#888;margin-top:3px;">{date_str} | {row.get("country","")}</div>'
                    f'<div style="font-size:11px;font-weight:500;">@{str(row.get("ownerUsername","-"))}</div>'
                    f'<div style="font-size:12px;">{metric}</div>'
                    f'{link}'
                    f'</div>',
                    unsafe_allow_html=True)

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
        st.caption(
            f"마지막 수집: **{last_kst.strftime('%Y-%m-%d %H:%M')} KST** "
            f"| 누적: **{len(df):,}건**"
        )

    # 국가 필터
    countries   = ["전체"] + sorted(df["country"].unique())
    sel_country = st.selectbox("🌍 국가 필터", countries, index=0)
    filtered_df = df if sel_country == "전체" else df[df["country"] == sel_country]

    st.divider()

    # 주차 계산
    this_start, this_end = get_week_range(weeks_ago=0)
    last_start, last_end = get_week_range(weeks_ago=1)
    this_week = get_weekly_df(filtered_df, weeks_ago=0)
    last_week = get_weekly_df(filtered_df, weeks_ago=1)

    st.markdown(
        f"**이번 주** {this_start.strftime('%m/%d')} ~ {(this_end - pd.Timedelta(days=1)).strftime('%m/%d')}"
        f" &nbsp;vs&nbsp; "
        f"**지난 주** {last_start.strftime('%m/%d')} ~ {(last_end - pd.Timedelta(days=1)).strftime('%m/%d')}"
    )

    display_df = this_week if not this_week.empty else filtered_df
    render_kpi_bar(display_df, last_week)

    st.divider()
    render_charts(filtered_df)

    st.divider()
    render_keywords(filtered_df)

    st.divider()
    render_top5(display_df if not this_week.empty else filtered_df)


if __name__ == "__main__":
    main()
