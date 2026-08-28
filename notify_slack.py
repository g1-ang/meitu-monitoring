import os
import re
import json
import pandas as pd
import urllib.request
from collections import Counter
from datetime import datetime, timedelta, timezone

SLACK_WEBHOOK_URL = os.getenv("SLACK_WEBHOOK_URL")

KEYWORD_THRESHOLD = 5
REEL_VIEW_MIN = 10000
FEED_LIKE_MIN = 500

BRAND_KEYWORDS = ["meitu", "메이투", "뷰티캠", "beautycam"]
MEITU_BRAND = ["meitu", "메이투"]
BEAUTYCAM_BRAND = ["뷰티캠", "beautycam"]

AD_PATTERNS = ["광고", "협찬", "유료광고", "제공", "콜라보", "파트너십",
               "ad", "sponsored", "collaboration", "paid", "pr", "promotion"]

# 메이투 앱 기능 사전 — 캡션/트윗에 등장하면 매칭
MEITU_FEATURES = [
    "중안부", "오토윤곽", "리터치", "슬림", "인중", "비율",
    "헤어보정", "헤어", "염색", "메이크업", "필터",
    "AI효과", "AI아트", "AI보정", "얼굴보정",
]

# 뷰티캠 콘텐츠/기능 사전
BEAUTYCAM_CONTENTS = [
    "AI영상효과", "길거리인터뷰", "잠금화면꾸미기", "굿즈만들기",
    "마그넷", "AI효과", "AI아트", "AI보정",
    "셀카", "필터", "스티커",
]

DASHBOARD_URL = "https://meitu-monitoring.streamlit.app"
DETAILS_URL = "https://meitu-monitoring.streamlit.app/details"

TW_STOPWORDS = {
    "meitu", "메이투", "뷰티캠", "beautycam", "beauty", "cam",
    "fyp", "foryou", "viral", "reels", "reel",
    "광고", "협찬", "진짜", "너무", "그냥", "사진", "이거",
    "ㅋㅋ", "ㅠㅠ", "ㅎㅎ", "rt", "팔로우", "좋아요",
    "그리고", "그래서", "그래도", "오늘", "어제", "내일", "지금", "이번",
    "써요", "있어", "없어", "하는", "있는", "되는", "라는", "라고", "라며",
    "이런", "저런", "그런", "거든요", "위해", "통해", "한국", "사람",
    "정말", "엄청", "완전", "최고", "이게", "저게", "그게",
    "죽은", "사진도", "사진은",
    "보정", "보정꿀팁", "효과", "유료", "메이투보정", "기본",
}

IG_STOPWORDS = {
    "meitu", "메이투", "뷰티캠", "beautycam", "beauty", "cam",
    "fyp", "foryou", "viral", "reels", "reel", "love", "like",
    "follow", "share", "instagram", "insta", "photo", "video",
    "좋아요", "팔로우", "댓글", "공유", "인스타", "인스타그램",
    "보정", "보정꿀팁", "효과", "유료", "메이투보정", "기본",
}


def send_slack(blocks: list) -> bool:
    payload = json.dumps({"blocks": blocks}).encode("utf-8")
    req = urllib.request.Request(
        SLACK_WEBHOOK_URL,
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST"
    )
    try:
        with urllib.request.urlopen(req) as res:
            print(f"슬랙 전송 완료: {res.status}")
            return True
    except Exception as e:
        # 데이터 수집은 끝난 시점이라 슬랙 실패로 워크플로우를 fail 시키지 않음
        print(f"슬랙 전송 실패 (무시하고 계속): {type(e).__name__}: {e}")
        return False


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
    return "0건"


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
        base += f" - 이번주 누적 ({this_monday.strftime('%m/%d')} ~ 현재)"
    return base


def get_day_label() -> str:
    labels = {0: "월요일", 1: "화요일", 2: "수요일", 3: "목요일",
              4: "금요일", 5: "토요일", 6: "일요일"}
    return labels.get(datetime.now(timezone.utc).weekday(), "")


def filter_range(df: pd.DataFrame, date_col: str, start, end) -> pd.DataFrame:
    return df[(df[date_col] >= start) & (df[date_col] < end)].copy()


def extract_top_terms(texts, dictionary, stopwords, top_n: int = 5) -> list:
    """사전 매칭 우선, 부족하면 해시태그/한글 명사로 보충."""
    text_lower = [str(t).lower() for t in texts if t and str(t) != "nan"]
    if not text_lower:
        return []

    counter = Counter()
    for term in dictionary:
        c = sum(1 for t in text_lower if term.lower() in t)
        if c:
            counter[term] = c

    if len(counter) < top_n:
        used = {k.lower() for k in counter}
        for t in text_lower:
            for tag in re.findall(r'#([가-힣a-zA-Z0-9_]+)', t):
                if (tag in stopwords or len(tag) < 2 or
                    re.fullmatch(r'\d+', tag) or tag.lower() in used):
                    continue
                counter[tag] += 1
            for word in re.findall(r'[가-힣]{2,}', t):
                if word in stopwords or word.lower() in used:
                    continue
                counter[word] += 1

    return [k for k, _ in counter.most_common(top_n)]


def fmt_terms(terms: list, min_sample: int = 0, sample_size: int = 0) -> str:
    # 샘플이 너무 적으면 노이즈 추출되므로 생략
    if min_sample and sample_size < min_sample:
        return f"_데이터 부족 (트윗 {sample_size}건)_"
    return " ".join(f"`{t}`" for t in terms) if terms else "_해당 없음_"


def format_caption_ig(text: str, max_len: int = 55) -> str:
    if not text or str(text) in ("nan", ""):
        return ""
    first_line = str(text).replace("\n", " ").strip()
    return first_line[:max_len] + "..." if len(first_line) > max_len else first_line


def build_ig_top3_blocks(df_kr: pd.DataFrame) -> list:
    blocks = []
    df_brand = df_kr[df_kr["search_keyword"].isin(BRAND_KEYWORDS)] if "search_keyword" in df_kr.columns else df_kr

    reels = df_brand[df_brand["content_type"] == "reel"].copy()
    reels_filtered = reels[reels["videoPlayCount"] >= REEL_VIEW_MIN].nlargest(3, "videoPlayCount")
    if reels_filtered.empty:
        reels_filtered = reels.nlargest(3, "videoPlayCount")
        reel_header = "*릴스 TOP 3* (최근 7일 - 조건 완화 적용)"
    else:
        reel_header = f"*릴스 TOP 3* (조회수 {fmt(REEL_VIEW_MIN)} 이상 - 최근 7일)"

    reel_lines = []
    for i, (_, row) in enumerate(reels_filtered.iterrows(), 1):
        caption = format_caption_ig(str(row.get("caption", "")))
        caption_line = f"\n> _{caption}_" if caption else ""
        reel_lines.append(
            f"*{i}위* @{row.get('ownerUsername', '-')} | 조회수 {fmt(row['videoPlayCount'])}{caption_line}\n{row.get('url', '')}"
        )
    blocks.append({"type": "section", "text": {"type": "mrkdwn",
        "text": reel_header + "\n" + ("\n".join(reel_lines) if reel_lines else "_해당 콘텐츠 없음_")}})

    feeds = df_brand[df_brand["content_type"].isin(["feed", "video_feed"])].copy()
    feeds_filtered = feeds[feeds["likesCount"] >= FEED_LIKE_MIN].nlargest(3, "likesCount")
    if feeds_filtered.empty:
        feeds_filtered = feeds.nlargest(3, "likesCount")
        feed_header = "*피드 TOP 3* (최근 7일 - 조건 완화 적용)"
    else:
        feed_header = f"*피드 TOP 3* (좋아요 {fmt(FEED_LIKE_MIN)} 이상 - 최근 7일)"

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


def format_caption_tw(text: str, max_len: int = 60) -> str:
    if not text or str(text) in ("nan", ""):
        return ""
    first_line = str(text).replace("\n", " ").strip()
    return first_line[:max_len] + "..." if len(first_line) > max_len else first_line


def build_tw_top_blocks(df_tw: pd.DataFrame) -> list:
    if df_tw.empty:
        return [{"type": "section", "text": {"type": "mrkdwn", "text": "_데이터 없음_"}}]

    df_brand = df_tw[df_tw["search_keyword"].isin(BRAND_KEYWORDS)] if "search_keyword" in df_tw.columns else df_tw

    if df_brand.empty:
        return [{"type": "section", "text": {"type": "mrkdwn", "text": "_해당 키워드 트윗 없음_"}}]

    def build_lines(df_sorted, metric_col, metric_label, n):
        lines = []
        for i, (_, row) in enumerate(df_sorted.head(n).iterrows(), 1):
            caption = format_caption_tw(str(row.get("text", "")))
            caption_line = f"\n> _{caption}_" if caption else ""
            prefix = f"*{i}위* " if n > 1 else ""
            lines.append(
                f"{prefix}@{row.get('author_handle', '-')} | {metric_label} {fmt(row[metric_col])}{caption_line}\n{row.get('url', '')}"
            )
        return lines

    blocks = []

    like_lines = build_lines(df_brand.nlargest(1, "like_count"), "like_count", "좋아요", 1)
    blocks.append({"type": "section", "text": {"type": "mrkdwn",
        "text": "*좋아요 TOP 1* (최근 7일)\n" + ("\n".join(like_lines) if like_lines else "_해당 없음_")}})

    rt_lines = build_lines(df_brand.nlargest(1, "retweet_count"), "retweet_count", "리트윗", 1)
    blocks.append({"type": "section", "text": {"type": "mrkdwn",
        "text": "*리트윗 TOP 1* (최근 7일)\n" + ("\n".join(rt_lines) if rt_lines else "_해당 없음_")}})

    ad_tweets = df_brand[df_brand["text"].apply(is_ad)] if "text" in df_brand.columns else pd.DataFrame()
    # 좋아요 + 리트윗 = 0인 트윗은 의미 없으므로 제외
    if not ad_tweets.empty:
        ad_tweets = ad_tweets[(ad_tweets["like_count"] + ad_tweets["retweet_count"]) > 0]
    if not ad_tweets.empty:
        ad_lines = []
        for i, (_, row) in enumerate(ad_tweets.nlargest(3, "like_count").iterrows(), 1):
            caption = format_caption_tw(str(row.get("text", "")))
            caption_line = f"\n> _{caption}_" if caption else ""
            ad_lines.append(
                f"*{i}위* @{row.get('author_handle', '-')} | 좋아요 {fmt(row['like_count'])} - 리트윗 {fmt(row['retweet_count'])}{caption_line}\n{row.get('url', '')}"
            )
        blocks.append({"type": "section", "text": {"type": "mrkdwn",
            "text": "*광고 언급 TOP 3* (광고/협찬/sponsored 표현 포함)\n" + "\n".join(ad_lines)}})

    return blocks


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

    ig_meitu_captions = ig_cur_brand[ig_cur_brand["search_keyword"].isin(MEITU_BRAND)]["caption"].dropna().tolist() if "search_keyword" in ig_cur_brand.columns else []
    ig_beauty_captions = ig_cur_brand[ig_cur_brand["search_keyword"].isin(BEAUTYCAM_BRAND)]["caption"].dropna().tolist() if "search_keyword" in ig_cur_brand.columns else []
    meitu_feats = extract_top_terms(ig_meitu_captions, MEITU_FEATURES, IG_STOPWORDS)
    beauty_contents = extract_top_terms(ig_beauty_captions, BEAUTYCAM_CONTENTS, IG_STOPWORDS)

    tw_cur  = filter_range(tw_df, "created_at", start, end) if not tw_df.empty else pd.DataFrame()
    tw_prev = filter_range(tw_df, "created_at", prev_start, prev_end) if not tw_df.empty else pd.DataFrame()

    def tw_cnt(df, kws):
        return len(df[df["search_keyword"].isin(kws)]) if not df.empty and "search_keyword" in df.columns else 0

    cur_meitu   = tw_cnt(tw_cur,  MEITU_BRAND)
    prev_meitu  = tw_cnt(tw_prev, MEITU_BRAND)
    cur_beauty  = tw_cnt(tw_cur,  BEAUTYCAM_BRAND)
    prev_beauty = tw_cnt(tw_prev, BEAUTYCAM_BRAND)

    tw_meitu_texts = tw_cur[tw_cur["search_keyword"].isin(MEITU_BRAND)]["text"].dropna().tolist() if not tw_cur.empty and "search_keyword" in tw_cur.columns else []
    tw_beauty_texts = tw_cur[tw_cur["search_keyword"].isin(BEAUTYCAM_BRAND)]["text"].dropna().tolist() if not tw_cur.empty and "search_keyword" in tw_cur.columns else []
    # 트위터 키워드는 사전 없이 자동 추출 위주 (브랜드별 마케팅 톤 파악용)
    tw_meitu_terms = extract_top_terms(tw_meitu_texts, MEITU_FEATURES, TW_STOPWORDS)
    tw_beauty_terms = extract_top_terms(tw_beauty_texts, BEAUTYCAM_CONTENTS, TW_STOPWORDS)

    blocks = [
        {"type": "header", "text": {"type": "plain_text", "text": f"Meitu 주간 리포트 ({get_day_label()})", "emoji": True}},
        {"type": "context", "elements": [{"type": "mrkdwn",
            "text": f"발송: *{now_kst.strftime('%Y-%m-%d %H:%M')} KST* | 기간: {get_report_label()} | 한국 - 경쟁사 키워드 기준"}]},
        {"type": "divider"},
        {"type": "section", "text": {"type": "mrkdwn", "text": "*[경쟁사 마케팅 요약]*"}},
        {"type": "section", "text": {"type": "mrkdwn", "text": (
            f"*인스타그램*\n"
            f"릴스: *{cur_reel}건* ({delta_str(cur_reel, prev_reel)})  |  "
            f"피드: *{cur_feed}건* ({delta_str(cur_feed, prev_feed)})\n"
            f"메이투: {fmt_terms(meitu_feats)} 기능으로 마케팅 중\n"
            f"뷰티캠: {fmt_terms(beauty_contents)} 콘텐츠로 마케팅 중"
        )}},
        {"type": "section", "text": {"type": "mrkdwn", "text": (
            f"*트위터*\n"
            f"메이투: *{cur_meitu}건* ({delta_str(cur_meitu, prev_meitu)})  |  "
            f"뷰티캠: *{cur_beauty}건* ({delta_str(cur_beauty, prev_beauty)})\n"
            f"메이투: {fmt_terms(tw_meitu_terms, min_sample=5, sample_size=cur_meitu)} 키워드로 마케팅 중\n"
            f"뷰티캠: {fmt_terms(tw_beauty_terms, min_sample=5, sample_size=cur_beauty)} 키워드로 마케팅 중"
        )}},
        {"type": "divider"},
        {"type": "section", "text": {"type": "mrkdwn", "text": "*[콘텐츠 내용]*"}},
    ]
    blocks += build_ig_top3_blocks(ig_cur_kr)
    blocks += build_tw_top_blocks(tw_cur)
    blocks += [
        {"type": "divider"},
        {"type": "actions", "elements": [{"type": "button",
            "text": {"type": "plain_text", "text": "대시보드 보기", "emoji": True},
            "url": DASHBOARD_URL, "style": "primary"}]}
    ]

    send_slack(blocks)
    print(f"주간 리포트 전송 완료 ({get_day_label()})")


def notify_keyword_spike(ig_df: pd.DataFrame, tw_df: pd.DataFrame):
    start, end = get_rolling_7days()
    ig_cur = filter_range(ig_df, "timestamp", start, end)
    tw_cur = filter_range(tw_df, "created_at", start, end) if not tw_df.empty else pd.DataFrame()

    counter_ig = Counter()
    if "caption" in ig_cur.columns and "search_keyword" in ig_cur.columns:
        ig_brand_kr = ig_cur[
            ig_cur["search_keyword"].isin(BRAND_KEYWORDS) &
            ig_cur["caption"].apply(is_korean)
        ]
        for caption in ig_brand_kr["caption"].dropna():
            for tag in re.findall(r'#(\w+)', str(caption).lower()):
                if tag in IG_STOPWORDS or len(tag) < 2:
                    continue
                if re.fullmatch(r'\d+', tag):
                    continue
                counter_ig[tag] += 1

    counter_tw = Counter()
    if not tw_cur.empty and "text" in tw_cur.columns and "search_keyword" in tw_cur.columns:
        tw_brand = tw_cur[tw_cur["search_keyword"].isin(BRAND_KEYWORDS)]
        for text in tw_brand["text"].dropna():
            t = str(text).lower()
            for tag in re.findall(r'#(\w+)', t):
                if tag not in TW_STOPWORDS and len(tag) >= 2:
                    counter_tw[tag] += 1
            for word in re.findall(r'[가-힣]{2,}', t):
                if word not in TW_STOPWORDS and len(word) >= 2:
                    counter_tw[word] += 1

    ig_top5 = [(k, v) for k, v in sorted(counter_ig.items(), key=lambda x: -x[1]) if v >= KEYWORD_THRESHOLD][:5]
    tw_top5 = [(k, v) for k, v in sorted(counter_tw.items(), key=lambda x: -x[1]) if v >= KEYWORD_THRESHOLD][:5]

    if not ig_top5 and not tw_top5:
        print("키워드 급증 없음")
        return

    now_kst   = datetime.now(timezone.utc) + timedelta(hours=9)
    start_kst = start + timedelta(hours=9)

    # 인스타/트위터 모두 # 없이 키워드만 표시
    ig_text = "  ".join([f"`{k}` {v}건" for k, v in ig_top5]) if ig_top5 else "_해당 없음_"
    tw_text = "  ".join([f"`{k}` {v}건" for k, v in tw_top5]) if tw_top5 else "_해당 없음_"

    blocks = [
        {"type": "header", "text": {"type": "plain_text", "text": "키워드 급증 감지!", "emoji": True}},
        {"type": "context", "elements": [{"type": "mrkdwn",
            "text": f"기준: 한국 - 경쟁사 브랜드 키워드 캡션 | {KEYWORD_THRESHOLD}건 이상 | 최근 7일 ({start_kst.strftime('%m/%d')} ~ {now_kst.strftime('%m/%d %H:%M')} KST)"}]},
        {"type": "divider"},
        {"type": "section", "text": {"type": "mrkdwn", "text": f"*인스타그램* _(해시태그 기준)_\n{ig_text}"}},
        {"type": "section", "text": {"type": "mrkdwn", "text": f"*트위터* _(해시태그 + 키워드 기준)_\n{tw_text}"}},
        {"type": "divider"},
        {"type": "actions", "elements": [{"type": "button",
            "text": {"type": "plain_text", "text": "세부 페이지 보기", "emoji": True},
            "url": DETAILS_URL, "style": "primary"}]}
    ]

    send_slack(blocks)
    print("키워드 급증 알람 전송 완료")


def main():
    print("슬랙 알람 전송 시작...")
    ig_df = load_instagram()
    tw_df = load_twitter()
    notify_weekly_report(ig_df, tw_df)
    notify_keyword_spike(ig_df, tw_df)
    print("슬랙 알람 완료!")


if __name__ == "__main__":
    main()
