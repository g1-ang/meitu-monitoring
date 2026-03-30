import os
import re
import json
import pandas as pd
import urllib.request
from collections import Counter
from datetime import datetime, timedelta, timezone

SLACK_WEBHOOK_URL = os.getenv("SLACK_WEBHOOK_URL")

KEYWORD_THRESHOLD = 5
REEL_VIEW_MIN = 5000
FEED_LIKE_MIN = 100

BRAND_KEYWORDS = ["meitu", "메이투", "뷰티캠", "beautycam"]
AD_PATTERNS = ["광고", "협찬", "유료광고", "제공", "콜라보", "파트너십",
               "ad", "sponsored", "collaboration", "paid", "pr", "promotion"]

DASHBOARD_URL = "https://meitu-monitoring.streamlit.app"
DETAILS_URL = "https://meitu-monitoring.streamlit.app/details"

TW_STOPWORDS = {
    "meitu", "메이투", "뷰티캠", "beautycam", "beauty", "cam",
    "fyp", "foryou", "viral", "reels", "reel",
    "광고",
}

IG_STOPWORDS = {
    "meitu", "메이투", "뷰티캠", "beautycam", "beauty", "cam",
    "fyp", "foryou", "viral", "reels", "reel", "love", "like",
    "follow", "share", "instagram", "insta", "photo", "video",
    "좋아요", "팔로우", "댓글", "공유", "인스타", "인스타그램",
}


# ── 유틸 ──────────────────────────────────────────────────────────────────────

def send_slack(blocks: list):
    payload = json.dumps({"blocks": blocks}).encode("utf-8")
    req = urllib.request.Request(
        SLACK_WEBHOOK_URL,
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST"
    )
    with urllib.request.urlopen(req) as res:
        print(f"슬랙 전송 완료: {res.status}")


def load_instagram() -> pd.DataFrame:
    df = pd.read_csv("data/latest_monitoring.csv", dtype=str)
    for col in ("likesCount", "commentsCount", "videoPlayCount"):
        df[col] = pd.to_numeric(df.get(col, 0), errors="coerce").fillna(0).astype(int)
    df["timestamp"] = pd.to_datetime(df.get("timestamp", ""), errors="coerce", utc=True)
    if "caption" in df.columns:
        df["caption"] = df["caption"].apply(
            lambda x: "" if "비공개" in str(x) else x
        )
    if "content_type" not in df.columns:
        df["content_type"] = df.apply(classify_content_type, axis=1)
    return df


def load_twitter() -> pd.DataFrame:
    try:
        df = pd.read_csv("data/latest_twitter.csv", dtype=str)
        for col in ("like_count", "retweet_count", "reply_count", "view_count"):
            df[col] = pd.to_numeric(df.get(col, 0), errors="coerce").fillna(0).astype(int)
        df["created_at"] = pd.to_datetime(df.get("created_at", ""), errors="coerce", utc=True)
        return df
    except FileNotFoundError:
        return pd.DataFrame()


def classify_content_type(row) -> str:
    product_type = str(row.get("productType", "")).lower().strip()
    media_type = str(row.get("type", "")).lower().strip()
    url = str(row.get("url", ""))
    video_url = str(row.get("videoUrl", ""))
    if product_type == "clips": return "reel"
    if product_type == "carousel_item": return "carousel_item"
    if product_type in ("feed", "carousel_container"): return "feed"
    if video_url and video_url not in ("nan", ""): return "reel"
    if media_type == "video":
        return "reel" if "/reel/" in url else "video_feed"
    if media_type in ("image", "sidecar"): return "feed"
    return "unknown"


def is_korean(text: str) -> bool:
    return bool(re.search(r'[가-힣]', str(text)))


def is_ad(text: str) -> bool:
    t = str(text).lower()
    return any(p in t for p in AD_PATTERNS)


def fmt(n) -> str:
    n = int(n)
    if n >= 10000: return f"{n/10000:.1f}만"
    if n >= 1000:  return f"{n/1000:.1f}천"
    return str(n)


def delta_str(cur: int, prev: int) -> str:
    diff = cur - prev
    if diff > 0: return f"+{diff}건"
    if diff < 0: return f"{diff}건"
    return "±0건"


# ── 기간 계산 ─────────────────────────────────────────────────────────────────

def get_rolling_7days():
    now = datetime.now(timezone.utc)
    return now - timedelta(days=7), now


def get_prev_7days():
    now = datetime.now(timezone.utc)
    return now - timedelta(days=14), now - timedelta(days=7)


def get_report_label() -> str:
    now = datetime.now(timezone.utc)
    weekday = now.weekday()
    start = now - timedelta(days=7)
    base = f"최근 7일 ({start.strftime('%m/%d')} ~ {now.strftime('%m/%d %H:%M')})"
    if weekday != 0:
        this_monday = (now - timedelta(days=weekday)).replace(hour=0, minute=0, second=0, microsecond=0)
        base += f"  ·  이번주 누적 ({this_monday.strftime('%m/%d')} ~ 현재)"
    return base


def get_day_label() -> str:
    labels = {0: "월요일", 1: "화요일", 2: "수요일", 3: "목요일",
              4: "금요일", 5: "토요일", 6: "일요일"}
    return labels.get(datetime.now(timezone.utc).weekday(), "")


def filter_range(df: pd.DataFrame, date_col: str, start, end) -> pd.DataFrame:
    return df[(df[date_col] >= start) & (df[date_col] < end)].copy()


# ── 인스타 TOP3 블록 ──────────────────────────────────────────────────────────

def format_caption_ig(text: str, max_len: int = 55) -> str:
    if not text or str(text) in ("nan", ""):
        return ""
    first_line = str(text).replace("\n", " ").strip()
    return first_line[:max_len] + "…" if len(first_line) > max_len else first_line


def build_ig_top3_blocks(df_kr: pd.DataFrame) -> list:
    blocks = []
    df_brand = df_kr[df_kr["search_keyword"].isin(BRAND_KEYWORDS)] if "search_keyword" in df_kr.columns else df_kr

    # 릴스 TOP3
    reels = df_brand[df_brand["content_type"] == "reel"].copy()
    reels_filtered = reels[reels["videoPlayCount"] >= REEL_VIEW_MIN].nlargest(3, "videoPlayCount")
    if reels_filtered.empty:
        reels_filtered = reels.nlargest(3, "videoPlayCount")
        reel_header = "*릴스 TOP 3* (최근 7일 · 조건 완화 적용)"
    else:
        reel_header = f"*릴스 TOP 3* (조회수 {fmt(REEL_VIEW_MIN)} 이상 · 최근 7일)"

    reel_lines = []
    for i, (_, row) in enumerate(reels_filtered.iterrows(), 1):
        caption = format_caption_ig(str(row.get("caption", "")))
        caption_line = f"\n> _{caption}_" if caption else ""
        reel_lines.append(
            f"*{i}위* @{row.get('ownerUsername', '-')} | 조회수 {fmt(row['videoPlayCount'])}{caption_line}\n{row.get('url', '')}"
        )

    blocks.append({"type": "section", "text": {"type": "mrkdwn",
        "text": reel_header + "\n" + ("\n".join(reel_lines) if reel_lines else "_해당 콘텐츠 없음_")}})

    # 피드 TOP3
    feeds = df_brand[df_brand["content_type"].isin(["feed", "video_feed"])].copy()
    feeds_filtered = feeds[feeds["likesCount"] >= FEED_LIKE_MIN].nlargest(3, "likesCount")
    if feeds_filtered.empty:
        feeds_filtered = feeds.nlargest(3, "likesCount")
        feed_header = "*피드 TOP 3* (최근 7일 · 조건 완화 적용)"
    else:
        feed_header = f"*피드 TOP 3* (좋아요 {fmt(FEED_LIKE_MIN)} 이상 · 최근 7일)"

    feed_lines = []
    for i, (_, row) in enumerate(feeds_filtered.iterrows(), 1):
        caption = format_caption_ig(str(row.get("caption", "")))
        caption_line = f"\n> _{caption}_" if caption else ""
        feed_lines.append(
            f"*{i}위* @{row.get('ownerUsername', '-')} | 좋아요 {fmt(row['likesCount'])}{caption_line}\n{row.get('url', '')}"
        )

    blocks.append({"type": "section", "text": {"type": "mrkdwn",
        "text": feed_header + "\n" + ("\n".join(feed_lines) if feed_lines else "_해당 콘텐츠 없음_")}})

    return blocks


# ── 트위터 TOP 블록 ───────────────────────────────────────────────────────────

def format_caption_tw(text: str, max_len: int = 60) -> str:
    if not text or str(text) in ("nan", ""):
        return ""
    first_line = str(text).replace("\n", " ").strip()
    return first_line[:max_len] + "…" if len(first_line) > max_len else first_line


def build_tw_top_blocks(df_tw: pd.DataFrame) -> list:
    if df_tw.empty:
        return [{"type": "section", "text": {"type": "mrkdwn", "text": "_데이터 없음_"}}]

    df_brand = df_tw[df_tw["search_keyword"].isin(BRAND_KEYWORDS)] if "search_keyword" in df_tw.columns else df_tw

    if df_brand.empty:
        return [{"type": "section", "text": {"type": "mrkdwn", "text": "_해당 키워드 트윗 없음_"}}]

    def build_top3_lines(df_sorted, metric_col, metric_label):
        lines = []
        for i, (_, row) in enumerate(df_sorted.head(3).iterrows(), 1):
            caption = format_caption_tw(str(row.get("text", "")))
            caption_line = f"\n> _{caption}_" if caption else ""
            lines.append(
                f"*{i}위* @{row.get('author_handle', '-')} | {metric_label} {fmt(row[metric_col])}{caption_line}\n{row.get('url', '')}"
            )
        return lines

    blocks = []

    like_lines = build_top3_lines(df_brand.nlargest(3, "like_count"), "like_count", "좋아요")
    blocks.append({"type": "section", "text": {"type": "mrkdwn",
        "text": "*좋아요 TOP 3* (최근 7일)\n" + ("\n".join(like_lines) if like_lines else "_해당 없음_")}})

    rt_lines = build_top3_lines(df_brand.nlargest(3, "retweet_count"), "retweet_count", "리트윗")
    blocks.append({"type": "section", "text": {"type": "mrkdwn",
        "text": "*리트윗 TOP 3* (최근 7일)\n" + ("\n".join(rt_lines) if rt_lines else "_해당 없음_")}})

    ad_tweets = df_brand[df_brand["text"].apply(is_ad)] if "text" in df_brand.columns else pd.DataFrame()
    if not ad_tweets.empty:
        ad_lines = []
        for _, row in ad_tweets.nlargest(3, "like_count").iterrows():
            caption = format_caption_tw(str(row.get("text", "")))
            caption_line = f"\n> _{caption}_" if caption else ""
            ad_lines.append(
                f"@{row.get('author_handle', '-')} | 좋아요 {fmt(row['like_count'])} · 리트윗 {fmt(row['retweet_count'])}{caption_line}\n{row.get('url', '')}"
            )
        blocks.append({"type": "section", "text": {"type": "mrkdwn",
            "text": "*광고 언급 트윗* (광고·협찬·sponsored 표현 포함)\n" + "\n".join(ad_lines)}})

    return blocks


# ── 주간 리포트 ───────────────────────────────────────────────────────────────

def notify_weekly_report(ig_df: pd.DataFrame, tw_df: pd.DataFrame):
    now_kst = datetime.now(timezone.utc) + timedelta(hours=9)
    start, end = get_rolling_7days()
    prev_start, prev_end = get_prev_7days()

    ig_cur = filter_range(ig_df, "timestamp", start, end)
    ig_prev = filter_range(ig_df, "timestamp", prev_start, prev_end)

    ig_cur_kr = ig_cur[ig_cur["caption"].apply(is_korean)] if "caption" in ig_cur.columns else ig_cur
    ig_prev_kr = ig_prev[ig_prev["caption"].apply(is_korean)] if "caption" in ig_prev.columns else ig_prev

    ig_cur_brand = ig_cur_kr[ig_cur_kr["search_keyword"].isin(BRAND_KEYWORDS)] if "search_keyword" in ig_cur_kr.columns else ig_cur_kr
    ig_prev_brand = ig_prev_kr[ig_prev_kr["search_keyword"].isin(BRAND_KEYWORDS)] if "search_keyword" in ig_prev_kr.columns else ig_prev_kr

    cur_reel  = (ig_cur_brand["content_type"] == "reel").sum()
    prev_reel = (ig_prev_brand["content_type"] == "reel").sum()
    cur_feed  = ig_cur_brand["content_type"].isin(["feed", "video_feed"]).sum()
    prev_feed = ig_prev_brand["content_type"].isin(["feed", "video_feed"]).sum()

    tw_cur  = filter_range(tw_df, "created_at", start, end) if not tw_df.empty else pd.DataFrame()
    tw_prev = filter_range(tw_df, "created_at", prev_start, prev_end) if not tw_df.empty else pd.DataFrame()

    def tw_cnt(df, kws):
        return len(df[df["search_keyword"].isin(kws)]) if not df.empty and "search_keyword" in df.columns else 0

    cur_meitu   = tw_cnt(tw_cur,  ["meitu", "메이투"])
    prev_meitu  = tw_cnt(tw_prev, ["meitu", "메이투"])
    cur_beauty  = tw_cnt(tw_cur,  ["뷰티캠"])
    prev_beauty = tw_cnt(tw_prev, ["뷰티캠"])

    blocks = [
        {"type": "header", "text": {"type": "plain_text", "text": f"Meitu 주간 리포트 ({get_day_label()})", "emoji": True}},
        {"type": "context", "elements": [{"type": "mrkdwn",
            "text": f"발송: *{now_kst.strftime('%Y-%m-%d %H:%M')} KST* | 기간: {get_report_label()} | 한국 · 경쟁사 키워드 기준"}]},
        {"type": "divider"},
        {"type": "section", "text": {"type": "mrkdwn", "text": (
            f"*인스타그램 (한국 · 경쟁사)*\n"
            f"릴스: *{cur_reel}건* ({delta_str(cur_reel, prev_reel)}) | "
            f"피드: *{cur_feed}건* ({delta_str(cur_feed, prev_feed)})"
        )}},
    ]
    blocks += build_ig_top3_blocks(ig_cur_kr)
    blocks.append({"type": "divider"})
    blocks.append({"type": "section", "text": {"type": "mrkdwn", "text": (
        f"*트위터 (한국 · 경쟁사)*\n"
        f"meitu+메이투: *{cur_meitu}건* ({delta_str(cur_meitu, prev_meitu)}) | "
        f"뷰티캠: *{cur_beauty}건* ({delta_str(cur_beauty, prev_beauty)})"
    )}})
    blocks += build_tw_top_blocks(tw_cur)
    blocks += [
        {"type": "divider"},
        {"type": "actions", "elements": [{"type": "button",
            "text": {"type": "plain_text", "text": "대시보드 보기", "emoji": True},
            "url": DASHBOARD_URL, "style": "primary"}]}
    ]

    send_slack(blocks)
    print(f"주간 리포트 전송 완료 ({get_day_label()})")


# ── 키워드 급증 알람 ──────────────────────────────────────────────────────────

def notify_keyword_spike(ig_df: pd.DataFrame, tw_df: pd.DataFrame):
    start, end = get_rolling_7days()
    ig_cur = filter_range(ig_df, "timestamp", start, end)
    tw_cur = filter_range(tw_df, "created_at", start, end) if not tw_df.empty else pd.DataFrame()

    # 인스타: 브랜드 키워드 수집분만 + 한국어 캡션
    counter_ig = Counter()
    if "caption" in ig_cur.columns:
        ig_brand_kr = ig_cur[
            ig_cur["caption"].apply(is_korean) &
            (ig_cur["search_keyword"].isin(BRAND_KEYWORDS) if "search_keyword" in ig_cur.columns else True)
        ]
        for caption in ig_brand_kr["caption"].dropna():
            for tag in re.findall(r'#(\w+)', str(caption).lower()):
                if tag in IG_STOPWORDS or len(tag) < 2:
                    continue
                if re.fullmatch(r'\d+', tag):
                    continue
                counter_ig[tag] += 1

    # 트위터: 브랜드 키워드 수집분만 + 해시태그만
    counter_tw = Counter()
    if not tw_cur.empty and "text" in tw_cur.columns:
        tw_brand = tw_cur[tw_cur["search_keyword"].isin(BRAND_KEYWORDS)] if "search_keyword" in tw_cur.columns else tw_cur
        for text in tw_brand["text"].dropna():
            for tag in re.findall(r'#(\w+)', str(text).lower()):
                if tag not in TW_STOPWORDS and len(tag) >= 2:
                    counter_tw[tag] += 1

    ig_top5 = [(k, v) for k, v in sorted(counter_ig.items(), key=lambda x: -x[1]) if v >= KEYWORD_THRESHOLD][:5]
    tw_top5 = [(k, v) for k, v in sorted(counter_tw.items(), key=lambda x: -x[1]) if v >= KEYWORD_THRESHOLD][:5]

    if not ig_top5 and not tw_top5:
        print("키워드 급증 없음")
        return

    now_kst   = datetime.now(timezone.utc) + timedelta(hours=9)
    start_kst = start + timedelta(hours=9)

    ig_text = "  ".join([f"`#{k}` {v}건" for k, v in ig_top5]) if ig_top5 else "_해당 없음_"
    tw_text = "  ".join([f"`#{k}` {v}건" for k, v in tw_top5]) if tw_top5 else "_해당 없음_"

    blocks = [
        {"type": "header", "text": {"type": "plain_text", "text": "키워드 급증 감지!", "emoji": True}},
        {"type": "context", "elements": [{"type": "mrkdwn",
            "text": f"기준: 한국 · *경쟁사 브랜드 키워드* 캡션 | {KEYWORD_THRESHOLD}건 이상 | 최근 7일 ({start_kst.strftime('%m/%d')} ~ {now_kst.strftime('%m/%d %H:%M')} KST)"}]},
        {"type": "divider"},
        {"type": "section", "text": {"type": "mrkdwn", "text": f"*인스타그램*\n{ig_text}"}},
        {"type": "section", "text": {"type": "mrkdwn", "text": f"*트위터* _(해시태그 기준)_\n{tw_text}"}},
        {"type": "divider"},
        {"type": "actions", "elements": [{"type": "button",
            "text": {"type": "plain_text", "text": "세부 페이지 보기", "emoji": True},
            "url": DETAILS_URL, "style": "primary"}]}
    ]

    send_slack(blocks)
    print("키워드 급증 알람 전송 완료")


# ── 메인 ─────────────────────────────────────────────────────────────────────

def main():
    print("슬랙 알람 전송 시작...")
    ig_df = load_instagram()
    tw_df = load_twitter()
    notify_weekly_report(ig_df, tw_df)
    notify_keyword_spike(ig_df, tw_df)
    print("슬랙 알람 완료!")


if __name__ == "__main__":
    main()
```

키워드 알람이 이렇게 바뀌어요:
```
키워드 급증 감지!
기준: 한국 · 경쟁사 브랜드 키워드 캡션 | 5건 이상 | 최근 7일

인스타그램
`#보정` 29건  `#ai보정` 11건  `#벚꽃` 17건  `#벚꽃사진` 7건  `#사진편집` 6건

트위터 (해시태그 기준)
`#행인제거` 7건  `#벚꽃사진` 7건
