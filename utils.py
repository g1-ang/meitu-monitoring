import re
import pandas as pd
from datetime import datetime, timedelta, timezone

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

# 불용어 (캡션 키워드 분석 시 제외)
STOPWORDS = {
    "meitu", "메이투", "뷰티캠", "beautycam", "beauty", "cam",
    "fyp", "foryou", "foryoupage", "viral", "reels", "reel",
    "love", "like", "follow", "share", "trending", "explore",
    "instagram", "insta", "photo", "video", "shorts",
    "the", "and", "for", "you", "this", "that", "with",
    "a", "is", "in", "of", "to", "it", "me", "my", "i",
    "좋아요", "팔로우", "댓글", "공유", "구독", "인스타", "인스타그램",
    "shorts", "tiktok", "youtube",
}


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


def classify_content_type(row: pd.Series) -> str:
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


def fmt(n) -> str:
    n = int(n)
    if n >= 10000: return f"{n/10000:.1f}만"
    if n >= 1000:  return f"{n/1000:.1f}천"
    return str(n)


@staticmethod
def load_data() -> pd.DataFrame:
    pass


def load_and_process(path: str = "data/latest_monitoring.csv") -> pd.DataFrame:
    df = pd.read_csv(path, dtype=str)

    for col in ("likesCount", "commentsCount", "videoPlayCount"):
        df[col] = pd.to_numeric(df.get(col, 0), errors="coerce").fillna(0).astype(int)

    df["timestamp"]    = pd.to_datetime(df.get("timestamp", ""), errors="coerce", utc=True)
    df["last_updated"] = pd.to_datetime(df.get("last_updated", ""), errors="coerce")
    df["engagement"]   = df["likesCount"] + df["commentsCount"]
    df["content_type"] = df.apply(classify_content_type, axis=1)
    df = df[~df["content_type"].isin(["carousel_item", "unknown"])].reset_index(drop=True)
    df["type_label"]   = df["content_type"].map(TYPE_LABEL).fillna("기타")

    if "caption" in df.columns:
        df["caption"] = (
            df["caption"].astype(str)
            .str.replace(r'\\n', ' ', regex=True)
            .str.replace(r'\n', ' ', regex=True)
            .str.strip()
        )

    df["country"]    = df.get("caption", "").apply(detect_country)
    df["ad_type"]    = df.get("caption", "").apply(detect_ad)
    df["is_korean"]  = df["country"] == "🇰🇷 한국"

    return df


def get_weekly_df(df: pd.DataFrame, weeks_ago: int = 0) -> pd.DataFrame:
    """weeks_ago=0: 이번 주, weeks_ago=1: 지난 주"""
    now   = datetime.now(timezone.utc)
    end   = now - timedelta(weeks=weeks_ago)
    start = end - timedelta(weeks=1)
    return df[
        (df["timestamp"] >= start) &
        (df["timestamp"] < end)
    ]


def extract_keywords(df: pd.DataFrame, top_n: int = 20) -> pd.DataFrame:
    """캡션에서 자주 등장하는 키워드 추출 (해시태그 포함)"""
    from collections import Counter
    counter = Counter()

    for caption in df["caption"].dropna():
        # 해시태그 추출
        tags = re.findall(r'#(\w+)', str(caption).lower())
        # 일반 단어 추출 (3글자 이상)
        words = re.findall(r'[가-힣a-zA-Z]{2,}', str(caption).lower())
        all_tokens = tags + words
        for token in all_tokens:
            if token not in STOPWORDS and len(token) >= 2:
                counter[token] += 1

    result = pd.DataFrame(counter.most_common(top_n), columns=["키워드", "언급수"])
    return result


def render_card_grid(sub_df: pd.DataFrame, fmt_fn) -> str:
    """HTML 카드 그리드 생성 — 모바일 2열 / PC 4열"""
    if sub_df.empty:
        return "<p style='color:#888;font-size:13px;'>해당 데이터가 없습니다.</p>"

    top = sub_df.nlargest(50, "engagement").reset_index(drop=True)
    type_colors = {"릴스": "#E1306C", "피드": "#405DE6", "피드(동영상)": "#833AB4"}

    html = """
    <style>
    .ig-grid { display:grid; grid-template-columns:repeat(4,1fr); gap:12px; margin-top:8px; }
    @media(max-width:768px){ .ig-grid{ grid-template-columns:repeat(2,1fr); gap:8px; } }
    .ig-card { background:var(--background-color,#fff); border:0.5px solid rgba(128,128,128,0.2); border-radius:10px; overflow:hidden; }
    .ig-card img { width:100%; aspect-ratio:1; object-fit:cover; display:block; }
    .ig-placeholder { width:100%; aspect-ratio:1; background:#f0f0f0; display:flex; align-items:center; justify-content:center; font-size:28px; }
    .ig-body { padding:7px 8px 10px; }
    .ig-badges { display:flex; gap:3px; flex-wrap:wrap; margin-bottom:4px; }
    .ig-badge { font-size:9px; font-weight:500; padding:1px 6px; border-radius:10px; color:white; }
    .ig-meta { font-size:10px; color:#888; margin-bottom:2px; }
    .ig-user { font-size:11px; font-weight:500; margin-bottom:3px; }
    .ig-stats { font-size:11px; margin-bottom:4px; }
    .ig-link { font-size:10px; color:#E1306C; text-decoration:none; }
    </style>
    <div class="ig-grid">
    """

    for _, row in top.iterrows():
        thumb    = str(row.get("displayUrl", ""))
        t_color  = type_colors.get(row["type_label"], "#888")
        ad_color = "#FF6B00" if row["ad_type"] == "📢 광고" else "#2E7D32"
        date_str = row["timestamp"].strftime("%Y-%m-%d") if pd.notna(row["timestamp"]) else "-"
        country  = row.get("country", "")
        username = str(row.get("ownerUsername", "-"))
        metric   = f"▶ {fmt_fn(row['videoPlayCount'])}" if row["content_type"] == "reel" else f"❤ {fmt_fn(row['likesCount'])}"
        comments = fmt_fn(row["commentsCount"])
        url      = str(row.get("url", ""))
        link     = f'<a class="ig-link" href="{url}" target="_blank">📎 보기</a>' if url.startswith("http") else ""

        thumb_html = (
            f'<img src="{thumb}" loading="lazy" onerror="this.parentNode.innerHTML=\'<div class=ig-placeholder>🖼️</div>\'">'
            if thumb and thumb not in ("nan", "")
            else '<div class="ig-placeholder">🖼️</div>'
        )

        html += f"""
        <div class="ig-card">
            {thumb_html}
            <div class="ig-body">
                <div class="ig-badges">
                    <span class="ig-badge" style="background:{t_color};">{row["type_label"]}</span>
                    <span class="ig-badge" style="background:{ad_color};">{row["ad_type"]}</span>
                </div>
                <div class="ig-meta">{date_str} | {country}</div>
                <div class="ig-user">@{username}</div>
                <div class="ig-stats">{metric} &nbsp; 💬 {comments}</div>
                {link}
            </div>
        </div>
        """

    html += "</div>"
    return html
