import os
import re
import pandas as pd
from apify_client import ApifyClient
from datetime import datetime

APIFY_TOKEN   = os.getenv('APIFY_API_TOKEN')
ACTOR_ID      = "apify/instagram-hashtag-scraper"
OUTPUT_PATH   = "data/latest_monitoring.csv"
COLLECT_MODE  = os.getenv('COLLECT_MODE', 'all')  # 'all' or 'brand'

# ── 브랜드 해시태그 (주 2회 수집) ─────────────────────────────────────────────
BRAND_KEYWORDS = [
    "meitu", "메이투", "뷰티캠", "beautycam",
]

# ── 카테고리 해시태그 (월요일만 수집) ─────────────────────────────────────────
CATEGORY_KEYWORDS = [
    "보정", "사진편집", "ai보정",
]

# ── 브랜디드 콘텐츠 감지 대상 계정 ────────────────────────────────────────────
BRANDED_ACCOUNTS = [
    "meitu.kr", "meitu.app", "meitu.jp", "meitutw",
    "beautycam.kr", "beautycam.app", "beautycam.jp",
]


def is_korean(text: str) -> bool:
    return bool(re.search(r'[가-힣]', str(text)))


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


def detect_branded_content(item: dict) -> bool:
    coauthors = item.get("coauthorProducers", [])
    if not coauthors or not isinstance(coauthors, list):
        return False
    for author in coauthors:
        if isinstance(author, dict):
            username = str(author.get("username", "")).lower()
            if any(acc in username for acc in BRANDED_ACCOUNTS):
                return True
    return False


def normalize(df: pd.DataFrame, raw_items: list) -> pd.DataFrame:
    if "likesCount" not in df.columns:
        df["likesCount"] = df.get("likes", 0)
    for src in ("videoViewCount", "playCount", "videoPlayCount"):
        if src in df.columns:
            df["videoPlayCount"] = df[src]
            break
    if "videoPlayCount" not in df.columns:
        df["videoPlayCount"] = 0

    for col in ("likesCount", "commentsCount", "videoPlayCount"):
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0).astype(int)

    if "caption" in df.columns:
        df["caption"] = (
            df["caption"].astype(str)
            .str.replace(r'\\n', ' ', regex=True)
            .str.replace(r'\n', ' ', regex=True)
            .str.strip()
        )

    df["content_type"] = df.apply(classify_content_type, axis=1)
    df["is_korean"]    = df.get("caption", "").apply(is_korean)
    df["last_updated"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    branded_flags = [detect_branded_content(item) for item in raw_items]
    df["is_branded"] = branded_flags if len(branded_flags) == len(df) else False

    coauthor_names = []
    for item in raw_items:
        coauthors = item.get("coauthorProducers", [])
        if coauthors and isinstance(coauthors, list):
            names = [a.get("username", "") for a in coauthors if isinstance(a, dict)]
            coauthor_names.append(", ".join(names))
        else:
            coauthor_names.append("")
    df["coauthor_accounts"] = coauthor_names if len(coauthor_names) == len(df) else ""

    return df


def append_and_dedup(new_df: pd.DataFrame) -> pd.DataFrame:
    os.makedirs("data", exist_ok=True)
    if os.path.exists(OUTPUT_PATH):
        existing = pd.read_csv(OUTPUT_PATH, dtype=str)
        print(f"📂 기존 레코드: {len(existing):,}건")
        combined = pd.concat([existing, new_df.astype(str)], ignore_index=True)
    else:
        print("📂 신규 파일 생성")
        combined = new_df.astype(str)

    if "content_type" in combined.columns:
        combined = combined[combined["content_type"] != "carousel_item"]

    before = len(combined)
    combined = (
        combined
        .sort_values("last_updated", ascending=False)
        .drop_duplicates(subset=["id"], keep="first")
        .reset_index(drop=True)
    )
    print(f"🗑️  중복 제거 후 최종: {len(combined):,}건 (제거 {before - len(combined):,}건)")
    return combined


def collect(keyword: str, keyword_type: str, results_type: str, client) -> list:
    """단일 키워드 수집"""
    icon = "🏷️ " if keyword_type == "브랜드" else "📂"
    print(f"{icon} [{keyword_type}] #{keyword} [{results_type}] 수집 중...")
    run = client.actor(ACTOR_ID).call(run_input={
        "hashtags":      [keyword],
        "resultsLimit":  25,
        "resultsType":   results_type,
        "keywordSearch": False,
    })
    results = list(client.dataset(run["defaultDatasetId"]).iterate_items())
    for r in results:
        r["search_keyword"] = keyword
        r["keyword_type"]   = keyword_type
    print(f"   → {len(results)}건")
    return results


def fetch_data():
    try:
        client      = ApifyClient(APIFY_TOKEN)
        all_results = []

        print(f"🚀 수집 모드: {COLLECT_MODE.upper()}")
        print(f"   브랜드 키워드:   {BRAND_KEYWORDS}")
        if COLLECT_MODE == "all":
            print(f"   카테고리 키워드: {CATEGORY_KEYWORDS}")

        for results_type in ("posts", "reels"):
            # 브랜드 키워드 — 항상 수집
            for keyword in BRAND_KEYWORDS:
                all_results.extend(collect(keyword, "브랜드", results_type, client))

            # 카테고리 키워드 — 월요일(all 모드)만 수집
            if COLLECT_MODE == "all":
                for keyword in CATEGORY_KEYWORDS:
                    all_results.extend(collect(keyword, "카테고리", results_type, client))

        if not all_results:
            print("⚠️ 수집된 데이터가 없습니다.")
            return

        df = pd.DataFrame(all_results)
        df = normalize(df, all_results)

        t  = df["content_type"].value_counts()
        kt = df["keyword_type"].value_counts() if "keyword_type" in df.columns else {}
        branded_count = (df["is_branded"] == True).sum()

        print(f"\n✅ 수집 완료: {len(df)}건")
        print(f"   브랜드 키워드:   {kt.get('브랜드', 0)}건")
        if COLLECT_MODE == "all":
            print(f"   카테고리 키워드: {kt.get('카테고리', 0)}건")
        print(f"   릴스:            {t.get('reel', 0)}건")
        print(f"   피드:            {t.get('feed', 0)}건")
        print(f"   한국 콘텐츠:     {df['is_korean'].sum()}건")
        print(f"   브랜디드 광고:   {branded_count}건")

        final = append_and_dedup(df)
        final.to_csv(OUTPUT_PATH, index=False, encoding="utf-8-sig")
        print(f"💾 저장 완료: {OUTPUT_PATH} ({len(final):,}건 누적)")

    except Exception as e:
        print(f"❌ 오류: {e}")
        raise


if __name__ == "__main__":
    fetch_data()
