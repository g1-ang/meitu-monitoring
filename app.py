import os
import json
import urllib.request
import pandas as pd
import streamlit as st
import plotly.express as px
from datetime import datetime, timezone
from utils import load_and_process, get_week_range, extract_keywords, fmt, TYPE_COLOR, TYPE_LABEL

st.set_page_config(page_title="IG Summary", page_icon="📊", layout="wide")

COUNTRY_ORDER = ["🇰🇷 한국", "🇯🇵 일본", "🇨🇳 중국/대만", "🇹🇭 태국", "🌐 영어권", "🇪🇺 유럽", "🌏 기타"]
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


@st.cache_data(ttl=3600)
def load_apify_usage():
    try:
        token = st.secrets.get("APIFY_API_TOKEN", "") or os.getenv("APIFY_API_TOKEN", "")
    except Exception:
        token = os.getenv("APIFY_API_TOKEN", "")

    if not token:
        return None
    try:
        now = datetime.now(timezone.utc)

        # Apify 청구 사이클: 매월 18일 기준
        if now.day >= 18:
            cycle_start = now.replace(day=18, hour=0, minute=0, second=0, microsecond=0)
        else:
            if now.month == 1:
                cycle_start = now.replace(year=now.year - 1, month=12, day=18, hour=0, minute=0, second=0, microsecond=0)
            else:
                cycle_start = now.replace(month=now.month - 1, day=18, hour=0, minute=0, second=0, microsecond=0)

        if cycle_start.month == 12:
            cycle_end = cycle_start.replace(year=cycle_start.year + 1, month=1, day=17, hour=23, minute=59, second=59)
        else:
            cycle_end = cycle_start.replace(month=cycle_start.month + 1, day=17, hour=23, minute=59, second=59)

        url = f"https://api.apify.com/v2/actor-runs?token={token}&limit=200&status=SUCCEEDED"
        req = urllib.request.Request(url)
        with urllib.request.urlopen(req, timeout=5) as res:
            data = json.loads(res.read())
        runs = data.get("data", {}).get("items", [])
        monthly_runs = [
            r for r in runs
            if r.get("startedAt", "") >= cycle_start.strftime("%Y-%m-%d")
        ]
        total_usd = sum(r.get("usageTotalUsd", 0) or 0 for r in monthly_runs)
        cycle_label = f"{cycle_start.strftime('%m/%d')} ~ {cycle_end.strftime('%m/%d')}"
        return {"count": len(monthly_runs), "usd": total_usd, "label": cycle_label}
    except Exception:
        return None


def get_comparison_weeks():
    now = datetime.now(timezone.utc)
    weekday = now.weekday()
    if weekday in (0, 1, 2):
        current_start, current_end = get_week_range(weeks_ago=1)
        compare_start, compare_end = get_week_range(weeks_ago=2)
        current_label = f"지난 주 ({current_start.strftime('%m/%d')} ~ {(current_end - pd.Timedelta(days=1)).strftime('%m/%d')})"
        compare_label = f"지지난 주 ({compare_start.strftime('%m/%d')} ~ {(compare_end - pd.Timedelta(days=1)).strftime('%m/%d')})"
    else:
        current_start, current_end = get_week_range(weeks_ago=0)
        compare_start, compare_end = get_week_range(weeks_ago=1)
        current_label = f"이번 주 ({current_start.strftime('%m/%d')} ~ {(current_end - pd.Timedelta(days=1)).strftime('%m/%d')})"
        compare_label = f"지난 주 ({compare_start.strftime('%m/%d')} ~ {(compare_end - pd.Timedelta(days=1)).strftime('%m/%d')})"
    return current_start, current_end, compare_start, compare_end, current_label, compare_label


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


def render_kpi_bar(current_df, compare_df):
    metrics = [
        ("📋 전체", len(current_df), len(compare_df)),
        ("🎬 릴스", (current_df["content_type"]=="reel").sum(), (compare_df["content_type"]=="reel").sum()),
        ("🖼️ 피드", current_df["content_type"].isin(["feed","video_feed"]).sum(), compare_df["content_type"].isin(["feed","video_feed"]).sum()),
        ("🇰🇷 한국", current_df["is_korean"].sum(), compare_df["is_korean"].sum()),
        ("📢 광고", (current_df["ad_type"]=="📢 광고").sum(), (compare_df["ad_type"]=="📢 광고").sum()),
        ("🌱 오가닉", (current_df["ad_type"]=="🌱 오가닉").sum(), (compare_df["ad_type"]=="🌱 오가닉").sum()),
    ]
    cols = st.columns(len(metrics))
    for col, (label, cur, prev) in zip(cols, metrics):
        diff = int(cur) - int(prev)
        delta_str = f"▲ {diff}" if diff > 0 else (f"▼ {abs(diff)}" if diff < 0 else "변화없음")
        delta_color = "normal" if diff > 0 else ("inverse" if diff < 0 else "off")
        col.metric(label=label, value=fmt(cur), delta=delta_str, delta_color=delta_color)


def render_charts(df):
    cmap = {v: TYPE_COLOR.get(k, "#888") for k, v in TYPE_LABEL.items()}
    col1, col2 = st.columns(2)
    with col1:
        st.markdown("**콘텐츠 유형**")
        counts = df["type_label"].value_counts().reset_index()
        counts.columns = ["유형", "건수"]
        fig = px.pie(counts, names="유형", values="건수", hole=0.45,
                     color="유형", color_discrete_map=cmap)
        fig.update_traces(textposition="none")
        fig.update_layout(showlegend=True,
                          legend=dict(orientation="h", yanchor="bottom", y=-0.35, xanchor="center", x=0.5, font=dict(size=9)),
                          margin=dict(t=5, b=40, l=5, r=5), height=200)
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
                           margin=dict(t=5, b=40, l=5, r=5), height=200)
        st.plotly_chart(fig2, use_container_width=True)


def render_keywords(df):
    st.subheader("🔤 캡션 키워드 TOP 15")
    st.caption("수집 키워드(meitu, 뷰티캠 등) 및 의미없는 태그 자동 제외 - 경쟁사 마케팅 주제 파악용")
    kw_df = extract_keywords(df, top_n=15)
    if kw_df.empty:
        st.info("키워드 데이터가 없습니다.")
        return
    fig = px.bar(kw_df, x="언급수", y="키워드", orientation="h",
                 color="언급수", color_continuous_scale=["#E8F4FD", "#E1306C"],
                 labels={"언급수": "언급 횟수", "키워드": ""}, text="언급수")
    fig.update_traces(textposition="outside")
    fig.update_layout(showlegend=False, coloraxis_showscale=False,
                      margin=dict(t=10, b=10, l=10, r=60),
                      height=420, yaxis=dict(autorange="reversed"))
    st.plotly_chart(fig, use_container_width=True)


def render_top5_cards(sub_df, metric_col):
    top = sub_df.nlargest(5, metric_col).reset_index(drop=True)
    if top.empty:
        st.info("해당 기간 데이터가 없습니다. 다음 수집 후 확인해주세요.")
        return
    type_colors = {"릴스": "#E1306C", "피드": "#405DE6", "피드(동영상)": "#833AB4"}
    cols = st.columns(5)
    for i, col in enumerate(cols):
        if i >= len(top):
            break
        row = top.iloc[i]
        with col:
            thumb = str(row.get("displayUrl", ""))
            url = str(row.get("url", ""))
            if thumb and thumb not in ("nan", ""):
                if url.startswith("http"):
                    st.markdown(
                        f'<a href="{url}" target="_blank">'
                        f'<img src="{thumb}" style="width:100%;border-radius:8px;cursor:pointer;">'
                        f'</a>',
                        unsafe_allow_html=True
                    )
                else:
                    st.image(thumb, use_container_width=True)
            else:
                st.markdown("<div style='background:#f0f0f0;height:100px;border-radius:6px;display:flex;align-items:center;justify-content:center;font-size:20px;'>🖼️</div>", unsafe_allow_html=True)
            t_color = type_colors.get(row["type_label"], "#888")
            ad_color = "#FF6B00" if row["ad_type"] == "📢 광고" else "#2E7D32"
            metric = f"▶ {fmt(row['videoPlayCount'])}" if row["content_type"] == "reel" else f"❤ {fmt(row['likesCount'])}"
            date_str = row["timestamp"].strftime("%m/%d") if pd.notna(row["timestamp"]) else "-"
            st.markdown(
                f'<div style="margin-top:5px;">'
                f'<span style="background:{t_color};color:white;font-size:9px;padding:1px 5px;border-radius:8px;">{row["type_label"]}</span>'
                f'<span style="background:{ad_color};color:white;font-size:9px;padding:1px 5px;border-radius:8px;margin-left:3px;">{row["ad_type"]}</span>'
                f'<div style="font-size:10px;color:#888;margin-top:3px;">{date_str} | {row.get("country","")}</div>'
                f'<div style="font-size:11px;font-weight:500;">@{str(row.get("ownerUsername","-"))}</div>'
                f'<div style="font-size:12px;">{metric}</div>'
                f'</div>',
                unsafe_allow_html=True)


def render_top5(current_df, label):
    st.subheader("🏆 TOP 5")
    st.caption(f"{label} 기준 | 릴스: 조회수 / 피드: 좋아요 / 카테고리: 인게이지먼트")
    brand_df = current_df[current_df["keyword_type"] == "브랜드"]
    category_df = current_df[current_df["keyword_type"] == "카테고리"]
    tab_reel, tab_feed, tab_category = st.tabs([
        "🎬 경쟁사 릴스 TOP 5", "🖼️ 경쟁사 피드 TOP 5", "📂 카테고리 TOP 5",
    ])
    with tab_reel:
        render_top5_cards(brand_df[brand_df["content_type"] == "reel"], "videoPlayCount")
    with tab_feed:
        render_top5_cards(brand_df[brand_df["content_type"].isin(["feed", "video_feed"])], "likesCount")
    with tab_category:
        render_top5_cards(category_df, "engagement")


# -- 메인 --

df = load_data()
top_nav("summary")

st.markdown("## 📊 Meitu 모니터링 - 요약")

if df["last_updated"].notna().any():
    last_kst = df["last_updated"].max() + pd.Timedelta(hours=9)
    st.caption(f"마지막 수집: **{last_kst.strftime('%Y-%m-%d %H:%M')} KST** | 누적: **{len(df):,}건**")

usage = load_apify_usage()
if usage:
    st.caption(f"Apify 이번 달 ({usage['label']}): **${usage['usd']:.2f}** | 실행 {usage['count']}회")

available_countries = [c for c in COUNTRY_ORDER if c in df["country"].unique()]
sel_countries = st.multiselect("🌍 국가 필터 (복수 선택 가능)", options=available_countries, default=available_countries)
filtered_df = df[df["country"].isin(sel_countries)] if sel_countries else df

st.divider()

current_start, current_end, compare_start, compare_end, current_label, compare_label = get_comparison_weeks()

current_df = filtered_df[
    (filtered_df["timestamp"] >= current_start) &
    (filtered_df["timestamp"] < current_end)
]
compare_df = filtered_df[
    (filtered_df["timestamp"] >= compare_start) &
    (filtered_df["timestamp"] < compare_end)
]

st.markdown(f"**{current_label}** &nbsp;vs&nbsp; **{compare_label}**")
render_kpi_bar(current_df, compare_df)

st.divider()
render_charts(filtered_df)

st.divider()
render_keywords(filtered_df)

st.divider()
render_top5(current_df if not current_df.empty else filtered_df, current_label)
