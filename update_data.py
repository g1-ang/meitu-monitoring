import os
import re
import pandas as pd
from apify_client import ApifyClient
from datetime import datetime

APIFY_TOKEN = os.getenv('APIFY_API_TOKEN')
ACTOR_ID    = "apify/instagram-hashtag-scraper"
OUTPUT_PATH = "data/latest_monitoring.csv"

# 수집할 해시태그 목록
KEYWORDS = ["meitu", "메이투", "뷰티캠", "beautycam"]


def is_korean(text: str) -> bool:
    """캡션에 한글이 포함되어 있으면 한국 콘텐츠로 분류"""
    return bool(re.search(r'[가-힣]', str(text)))


def classify_content_type(row: pd.Series) -> str:
    """productType / type 필드 기반 콘텐츠 유형 분류"""
    product_type = str(row.get("productType", "")).lower().strip()
    media_type   = str(row.get("type", "")).lower().strip()
    url          = str(row.get("url", ""))

    if product_type == "clips":                         return "reel"
    if product_type == "carousel_item":                 return "carousel_item"
    if product_type in ("feed", "carousel_container"):  return "feed"
    if media_type == "video":
        return "reel" if "/reel/" in url else "video_feed"
    if media_type in ("image", "sidecar"):              return "feed"
    return "unknown"


def normalize(df: pd.DataFrame) -> pd.DataFrame:
    """컬럼 통일 + 수치 변환 + 유형 분류 + 한국 콘텐츠 감지"""
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

    df["content_type"] = df.apply(classify_content_type, axis=1)
    df["is_korean"]    = df.get("caption", "").apply(is_korean)
    df["last_updated"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    return df


def append_and_dedup(new_df: pd.DataFrame) -> pd.DataFrame:
    """기존 CSV에 추가 + id 기준 중복 제거"""
    os.makedirs("data", exist_ok=True)
    if os.path.exists(OUTPUT_PATH):
        existing = pd.read_csv(OUTPUT_PATH, dtype=str)
        print(f"📂 기존 레코드: {len(existing):,}건")
        combined = pd.concat([existing, new_df.astype(str)], ignore_index=True)
    else:
        print("📂 신규 파일 생성")
        combined = new_df.astype(str)

    # 슬라이드 자식 row 제거
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


def fetch_data():
    try:
        client = ApifyClient(APIFY_TOKEN)
        all_results = []

        for keyword in KEYWORDS:
            print(f"🔍 #{keyword} 수집 중...")
            run = client.actor(ACTOR_ID).call(run_input={
                "hashtags":    [keyword],
                "resultsLimit": 50,
                "contentType": "both",  # 릴스 + 피드 동시 수집
            })
            results = list(client.dataset(run["defaultDatasetId"]).iterate_items())
            for r in results:
                r["search_keyword"] = keyword
            all_results.extend(results)
            print(f"   → {len(results)}건 수집")

        if not all_results:
            print("⚠️ 수집된 데이터가 없습니다.")
            return

        df = normalize(pd.DataFrame(all_results))

        t = df["content_type"].value_counts()
        print(f"\n✅ 수집 완료: {len(df)}건")
        print(f"   릴스:         {t.get('reel', 0)}건")
        print(f"   피드:         {t.get('feed', 0)}건")
        print(f"   한국 콘텐츠:  {df['is_korean'].sum()}건")

        final = append_and_dedup(df)
        final.to_csv(OUTPUT_PATH, index=False, encoding="utf-8-sig")
        print(f"💾 저장 완료: {OUTPUT_PATH} ({len(final):,}건 누적)")

    except Exception as e:
        print(f"❌ 오류: {e}")
        raise


if __name__ == "__main__":
    fetch_data()
