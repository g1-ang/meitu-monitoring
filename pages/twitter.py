import pandas as pd
import streamlit as st
from datetime import datetime, timedelta, timezone

st.set_page_config(page_title="트위터 모니터링", page_icon="🐦", layout="wide")

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
    """KPI — 메이투 건수 / 뷰티캠 건수 / 평균 지표"""
    meitu_df   = df[df["search_keyword"].isin(["meitu", "메이투"])]
    beautycam_df = df[df["search_keyword"] == "뷰티캠"]

    total      = len(df)
    meitu_cnt  = len(meitu_df)
    beauty_cnt = len(beautycam_df)
    avg_like   = df["like_count"].mean()
    avg_rt     = df["retweet_count"].mean()
    avg_view   = df["view_count"].mean()

    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("🐦 전체 트윗",        fmt(total))
    c2.metric("📌 meitu + 메이투",   fmt(meitu_cnt))
    c3.metric("📌 뷰티캠",           fmt(beauty_cnt))
    c4.metric("❤️ 평균 좋아요",      f"{avg_like:.1f}")
    c5.metric("👁️ 평균 조회수",      fmt(avg_view))


def render_tweet_cards(df):
    if df.empty:
        st.info("해당 데이터가 없습니다.")
        return

    top = df.nlargest(50, "engagement").reset_index(drop=True)

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
                text     = str(row.get("text", ""))
                handle   = str(row.get("author_handle", "-"))
                keyword  = str(row.get("search_keyword", ""))
                link     = f'<a href="{url}" target="_blank" style="font-size:10px;color:#1D9BF0;text-decoration:none;">🔗 원문 보기</a>' if url.startswith("http") else ""

                # 트윗 이미지 추출 (URL에서 pic.twitter.com 또는 t.co 이미지)
                media_url = str(row.get("media_url", "")) if "media_url" in row else ""
                images    = str(row.get("images", ""))    if "images" in row else ""

                # 텍스트에서 URL 제거 (깔끔하게)
                import re
                clean_text = re.sub(r'https?://\S+', '', text).strip()
                if len(clean_text) > 120:
                    clean_text = clean_text[:120] + "..."

                # 이미지 표시
                img_html = ""
                if media_url and media_url not in ("nan", ""):
                    img_html = f'<img src="{media_url}" style="width:100%;border-radius:8px;margin-bottom:6px;aspect-ratio:16/9;object-fit:cover;" onerror="this.style.display=\'none\'">'
                elif images and images not in ("nan", "[]", ""):
                    # images 컬럼에서 첫 번째 URL 추출
                    import ast
                    try:
                        img_list = ast.literal_eval(images)
                        if img_list:
                            img_html = f'<img src="{img_list[0]}" style="width:100%;border-radius:8px;margin-bottom:6px;aspect-ratio:16/9;object-fit:cover;" onerror="this.style.display=\'none\'">'
                    except:
                        pass

                st.markdown(
                    f"""
                    <div style="background:var(--background-color,#fff);
                                border:0.5px solid rgba(128,128,128,0.2);
                                border-radius:12px;padding:12px;margin-bottom:4px;">
                        {img_html}
                        <div style="display:flex;justify-content:space-between;
                                    align-items:center;margin-bottom:6px;">
                            <span style="background:#E8F5FE;color:#1D9BF0;font-size:9px;
                                         font-weight:500;padding:1px 7px;border-radius:10px;">
                                #{keyword}
                            </span>
                            <span style="font-size:10px;color:#888;">{date_str}</span>
                        </div>
                        <div style="font-size:11px;color:var(--color-text-primary,#000);
                                    line-height:1.5;margin-bottom:8px;">{clean_text}</div>
                        <div style="font-size:10px;color:#888;margin-bottom:6px;">
                            @{handle}
                        </div>
                        <div style="display:flex;gap:10px;font-size:11px;
                                    color:#666;margin-bottom:6px;">
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

# 필터 — 기간 + 키워드만
col1, col2 = st.columns(2)

with col1:
    now      = datetime.now(timezone.utc)
    period   = st.radio("📅 기간",
                        ["최근 7일", "최근 1개월", "최근 3개월", "전체"],
                        index=3, horizontal=True)
    days_map = {"최근 7일": 7, "최근 1개월": 30, "최근 3개월": 90, "전체": None}
    days     = days_map[period]
    if days:
        start_d = (now - timedelta(days=days)).date()
        end_d   = now.date()
    else:
        start_d = df["created_at"].min().date() if df["created_at"].notna().any() else None
        end_d   = df["created_at"].max().date() if df["created_at"].notna().any() else None

with col2:
    sel_keywords = st.multiselect(
        "🔍 키워드",
        options=KEYWORDS,
        default=KEYWORDS
    )

# 필터 적용
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

# KPI
render_kpi(filtered)
st.divider()

# 트윗 목록
st.subheader("📋 트윗 목록")
st.caption("인게이지먼트(좋아요+리트윗+댓글) 기준 상위 50건 | 원문 보기 클릭 시 트위터로 이동")

tab_all, tab_meitu, tab_beautycam = st.tabs([
    "전체",
    "meitu / 메이투",
    "뷰티캠",
])

with tab_all:
    render_tweet_cards(filtered)

with tab_meitu:
    render_tweet_cards(filtered[filtered["search_keyword"].isin(["meitu", "메이투"])])

with tab_beautycam:
    render_tweet_cards(filtered[filtered["search_keyword"] == "뷰티캠"])
