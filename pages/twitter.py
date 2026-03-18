import re
import ast
import pandas as pd
import streamlit as st
from datetime import datetime, timedelta, timezone

st.set_page_config(page_title="Twitter (KR)", page_icon="🐦", layout="wide")

KEYWORDS = ["meitu", "메이투", "뷰티캠"]


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


def render_kpi(df):
    meitu_cnt  = len(df[df["search_keyword"].isin(["meitu", "메이투"])])
    beauty_cnt = len(df[df["search_keyword"] == "뷰티캠"])
    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("🐦 전체 트윗",      fmt(len(df)))
    c2.metric("📌 meitu + 메이투", fmt(meitu_cnt))
    c3.metric("📌 뷰티캠",         fmt(beauty_cnt))
    c4.metric("❤️ 평균 좋아요",    f"{df['like_count'].mean():.1f}")
    c5.metric("👁️ 평균 조회수",    fmt(int(df['view_count'].mean())))


def get_first_image(row) -> str:
    for field in ("media_url", "images"):
        val = str(row.get(field, ""))
        if val and val not in ("nan", "[]", ""):
            if val.startswith("http"):
                return val
            try:
                lst = ast.literal_eval(val)
                if lst and isinstance(lst, list):
                    return lst[0]
            except:
                pass
    return ""


def render_tweet_cards(sub_df):
    if sub_df.empty:
        st.info("해당 데이터가 없습니다.")
        return

    top = sub_df.nlargest(50, "engagement").reset_index(drop=True)

    cards_html = """
    <style>
    .tw-grid { display:grid; grid-template-columns:repeat(4,1fr); gap:12px; margin-top:8px; }
    @media(max-width:768px){ .tw-grid{ grid-template-columns:repeat(2,1fr); gap:8px; } }
    .tw-card { background:var(--background-color,#fff); border:0.5px solid rgba(128,128,128,0.2); border-radius:12px; overflow:hidden; display:flex; flex-direction:column; }
    .tw-thumb-link { display:block; cursor:pointer; }
    .tw-thumb-link img { width:100%; aspect-ratio:16/9; object-fit:cover; display:block; transition:opacity 0.15s; }
    .tw-thumb-link:hover img { opacity:0.85; }
    .tw-body { padding:10px 12px 12px; display:flex; flex-direction:column; gap:5px; }
    .tw-kw { display:inline-block; background:#E8F5FE; color:#1D9BF0; font-size:9px; font-weight:500; padding:1px 7px; border-radius:10px; }
    .tw-text { font-size:11px; line-height:1.6; color:var(--color-text-primary,#000); }
    .tw-handle { font-size:10px; color:#888; }
    .tw-date { font-size:10px; color:#aaa; }
    .tw-stats { display:flex; gap:10px; font-size:11px; color:#666; flex-wrap:wrap; }
    </style>
    <div class="tw-grid">
    """

    for _, row in top.iterrows():
        keyword  = str(row.get("search_keyword", ""))
        text     = re.sub(r'https?://\S+', '', str(row.get("text", ""))).strip()
        if len(text) > 120:
            text = text[:120] + "..."
        handle   = str(row.get("author_handle", "-"))
        date_str = row["created_at"].strftime("%Y-%m-%d %H:%M") if pd.notna(row["created_at"]) else "-"
        url      = str(row.get("url", ""))
        img_url  = get_first_image(row)

        # 썸네일 — 이미지 있으면 클릭 시 트위터로 이동, 없으면 텍스트 카드
        if img_url and url.startswith("http"):
            thumb_html = f'<a class="tw-thumb-link" href="{url}" target="_blank"><img src="{img_url}" onerror="this.parentNode.style.display=\'none\'"></a>'
        else:
            thumb_html = ""

        # 텍스트 클릭 시 트위터로 이동
        if url.startswith("http"):
            text_html = f'<a href="{url}" target="_blank" style="text-decoration:none;color:inherit;"><div class="tw-text">{text}</div></a>'
        else:
            text_html = f'<div class="tw-text">{text}</div>'

        cards_html += f"""
        <div class="tw-card">
            {thumb_html}
            <div class="tw-body">
                <div><span class="tw-kw">#{keyword}</span></div>
                {text_html}
                <div class="tw-handle">@{handle}</div>
                <div class="tw-date">{date_str}</div>
                <div class="tw-stats">
                    <span>❤️ {fmt(row['like_count'])}</span>
                    <span>🔁 {fmt(row['retweet_count'])}</span>
                    <span>💬 {fmt(row['reply_count'])}</span>
                    <span>👁️ {fmt(row['view_count'])}</span>
                </div>
            </div>
        </div>
        """

    cards_html += "</div>"
    st.html(cards_html)


# ── 메인 ──────────────────────────────────────────────────────────────────────
top_nav("twitter")
st.markdown("## 🐦 트위터 모니터링")

try:
    df = load_data()
except FileNotFoundError:
    st.warning("트위터 데이터가 없습니다. GitHub Actions를 먼저 실행해주세요.", icon="⚠️")
    st.stop()

if df["last_updated"].notna().any():
    last_kst = df["last_updated"].max() + pd.Timedelta(hours=9)
    st.caption(f"마지막 수집: **{last_kst.strftime('%Y-%m-%d %H:%M')} KST** | 누적: **{len(df):,}건**")

st.divider()

col1, col2 = st.columns(2)
with col1:
    now      = datetime.now(timezone.utc)
    period   = st.radio("📅 기간", ["최근 7일", "최근 1개월", "최근 3개월", "전체"], index=3, horizontal=True)
    days_map = {"최근 7일": 7, "최근 1개월": 30, "최근 3개월": 90, "전체": None}
    days     = days_map[period]
    if days:
        start_d = (now - timedelta(days=days)).date()
        end_d   = now.date()
    else:
        start_d = df["created_at"].min().date() if df["created_at"].notna().any() else None
        end_d   = df["created_at"].max().date() if df["created_at"].notna().any() else None
with col2:
    sel_keywords = st.multiselect("🔍 키워드", options=KEYWORDS, default=KEYWORDS)

filtered = df.copy()
if start_d and end_d:
    filtered = filtered[
        (filtered["created_at"].dt.date >= start_d) &
        (filtered["created_at"].dt.date <= end_d)
    ]
if sel_keywords:
    filtered = filtered[filtered["search_keyword"].isin(sel_keywords)]

st.caption(f"필터 결과: **{len(filtered):,}건**")
st.divider()

render_kpi(filtered)
st.divider()

st.subheader("📋 트윗 목록")
st.caption("인게이지먼트(좋아요+리트윗+댓글) 기준 상위 50건 | 썸네일/텍스트 클릭 시 트위터로 이동")

tab_all, tab_meitu, tab_beautycam = st.tabs(["전체", "meitu / 메이투", "뷰티캠"])
with tab_all:
    render_tweet_cards(filtered)
with tab_meitu:
    render_tweet_cards(filtered[filtered["search_keyword"].isin(["meitu", "메이투"])])
with tab_beautycam:
    render_tweet_cards(filtered[filtered["search_keyword"] == "뷰티캠"])
