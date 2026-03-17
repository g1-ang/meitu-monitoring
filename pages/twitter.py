import pandas as pd
import streamlit as st
from datetime import datetime, timedelta, timezone

st.set_page_config(page_title="트위터 모니터링", page_icon="🐦", layout="wide")

COUNTRY_ORDER = ["🇰🇷 한국", "🇯🇵 일본", "🇨🇳 중국/대만", "🇹🇭 태국", "🌐 영어권", "🇪🇺 유럽", "🌏 기타"]
KEYWORDS      = ["meitu", "메이투", "뷰티캠"]


@st.cache_data(ttl=300)
def load_data():
    df = pd.read_csv("data/latest_twitter.csv", dtype=str)

    for col in ("view_count", "like_count", "retweet_count", "reply_count"):
        df[col] = pd.to_numeric(df.get(col, 0), errors="coerce").fillna(0).astype(int)

    df["created_at"]   = pd.to_datetime(df.get("created_at", ""), errors="coerce", utc=True)
    df["last_updated"] = pd.to_datetime(df.get("last_updated", ""), errors="coerce")
    df["engagement"]   = df["like_count"] + df["retweet_count"] + df["reply_count"]

    return df


def fmt(n) -> str:
    n = int(n)
    if n >= 10000: return f"{n/10000:.1f}만"
    if n >= 1000:  return f"{n/1000:.1f}천"
    return str(n)


def top_nav():
    col1, col2, col3, col4 = st.columns([1, 1, 1, 7])
    with col1:
        st.page_link("app.py", label="📊 요약")
    with col2:
        st.page_link("pages/details.py", label="🔍 세부")
    with col3:
        st.markdown('<span style="display:block;text-align:center;background:#1D9BF0;color:white;padding:6px 0;border-radius:8px;font-size:14px;font-weight:500;">🐦 트위터</span>', unsafe_allow_html=True)
    st.markdown("<div style='margin-bottom:8px;'></div>", unsafe_allow_html=True)


def render_kpi(df):
    total    = len(df)
    korean   = (df["country"] == "🇰🇷 한국").sum()
    avg_like = df["like_count"].mean()
    avg_rt   = df["retweet_count"].mean()
    avg_view = df["view_count"].mean()

    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("🐦 전체 트윗",    fmt(total))
    c2.metric("🇰🇷 한국",        fmt(korean))
    c3.metric("❤️ 평균 좋아요",  f"{avg_like:.1f}")
    c4.metric("🔁 평균 리트윗",  f"{avg_rt:.1f}")
    c5.metric("👁️ 평균 조회수",  fmt(avg_view))


def render_tweet_cards(df):
    if df.empty:
        st.info("해당 데이터가 없습니다.")
        return

    top = df.nlargest(50, "engagement").reset_index(drop=True)

    # 4열 그리드
    cols_per_row = 4
    for i in range(0, len(top), cols_per_row):
        cols = st.columns(cols_per_row)
        for j, col in enumerate(cols):
            idx = i + j
            if idx >= len(top):
                break
            row = top.iloc[idx]

            with col:
                date_str = row["created_at"].strftime("%Y-%m-%d %H:%M") if pd.notna(row["created_at"]) else "-"
                url      = str(row.get("url", ""))
                text     = str(row.get("text", ""))[:120] + ("..." if len(str(row.get("text", ""))) > 120 else "")
                handle   = str(row.get("author_handle", "-"))
                name     = str(row.get("author_name", "-"))
                country  = str(row.get("country", ""))
                keyword  = str(row.get("search_keyword", ""))
                link     = f'<a href="{url}" target="_blank" style="font-size:10px;color:#1D9BF0;text-decoration:none;">🔗 원문 보기</a>' if url.startswith("http") else ""

                st.markdown(
                    f"""
                    <div style="background:var(--background-color,#fff);border:0.5px solid rgba(128,128,128,0.2);
                                border-radius:12px;padding:12px;margin-bottom:4px;min-height:180px;">
                        <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:6px;">
                            <span style="background:#E8F5FE;color:#1D9BF0;font-size:9px;font-weight:500;
                                         padding:1px 7px;border-radius:10px;">#{keyword}</span>
                            <span style="font-size:10px;color:#888;">{country}</span>
                        </div>
                        <div style="font-size:11px;color:var(--color-text-primary,#000);
                                    line-height:1.5;margin-bottom:8px;">{text}</div>
                        <div style="font-size:10px;color:#888;margin-bottom:4px;">
                            @{handle} · {date_str}
                        </div>
                        <div style="display:flex;gap:10px;font-size:11px;color:#666;margin-bottom:6px;">
                            <span>❤️ {fmt(row['like_count'])}</span>
                            <span>🔁 {fmt(row['retweet_count'])}</span>
                            <span>💬 {fmt(row['reply_count'])}</span>
                            <span>👁️ {fmt(row['view_count'])}</span>
                        </div>
                        {link}
                    </div>
                    """,
                    unsafe_allow_html=True
                )


# ── 메인 ──────────────────────────────────────────────────────────────────────
top_nav()

st.markdown("## 🐦 트위터 모니터링")

try:
    df = load_data()
except FileNotFoundError:
    st.warning("트위터 데이터가 없습니다. GitHub Actions를 먼저 실행해주세요.", icon="⚠️")
    st.stop()

if df["last_updated"].notna().any():
    last_kst = df["last_updated"].max() + pd.Timedelta(hours=9)
    st.caption(
        f"마지막 수집: **{last_kst.strftime('%Y-%m-%d %H:%M')} KST** "
        f"| 누적: **{len(df):,}건**"
    )

st.divider()

# 필터
col1, col2, col3 = st.columns(3)

with col1:
    available = [c for c in COUNTRY_ORDER if c in df["country"].unique()]
    sel_countries = st.multiselect("🌍 국가", options=available, default=available)

with col2:
    now      = datetime.now(timezone.utc)
    period   = st.radio("📅 기간", ["최근 7일", "최근 1개월", "최근 3개월", "전체"],
                        index=3, horizontal=True)
    days_map = {"최근 7일": 7, "최근 1개월": 30, "최근 3개월": 90, "전체": None}
    days     = days_map[period]
    if days:
        start_d = (now - timedelta(days=days)).date()
        end_d   = now.date()
    else:
        start_d = df["created_at"].min().date() if df["created_at"].notna().any() else None
        end_d   = df["created_at"].max().date() if df["created_at"].notna().any() else None

with col3:
    sel_keywords = st.multiselect("🔍 키워드", options=KEYWORDS, default=KEYWORDS)

# 필터 적용
filtered = df.copy()
if sel_countries:
    filtered = filtered[filtered["country"].isin(sel_countries)]
if start_d and end_d:
    filtered = filtered[
        (filtered["created_at"].dt.date >= start_d) &
        (filtered["created_at"].dt.date <= end_d)
    ]
if sel_keywords:
    filtered = filtered[filtered["search_keyword"].isin(sel_keywords)]

st.caption(f"필터 결과: **{len(filtered):,}건**")
st.divider()

# KPI
render_kpi(filtered)
st.divider()

# 키워드별 탭
st.subheader("📋 트윗 목록")
st.caption("인게이지먼트(좋아요+리트윗+댓글) 기준 상위 50건 | 원문 보기 클릭 시 트위터로 이동")

tab_all, tab_meitu, tab_korean, tab_japanese = st.tabs([
    "전체",
    "meitu / 메이투 / 뷰티캠",
    "🇰🇷 한국",
    "🇯🇵 일본",
])

with tab_all:
    render_tweet_cards(filtered)

with tab_meitu:
    render_tweet_cards(filtered[filtered["search_keyword"].isin(["meitu", "메이투", "뷰티캠"])])

with tab_korean:
    render_tweet_cards(filtered[filtered["country"] == "🇰🇷 한국"])

with tab_japanese:
    render_tweet_cards(filtered[filtered["country"] == "🇯🇵 일본"])
