import os
import pandas as pd
from apify_client import ApifyClient

# 설정
APIFY_TOKEN = os.getenv('APIFY_API_TOKEN')
ACTOR_ID = "apify/instagram-hashtag-scraper"
KEYWORDS = ["메이투", "뷰티캠", "meitu", "beautycam"]

def fetch_data():
    client = ApifyClient(APIFY_TOKEN)
    
    run_input = {
        "hashtags": KEYWORDS,
        "resultsLimit": 200, 
    }
    
    print("🚀 Apify 데이터 수집 및 구조 최적화 시작...")
    run = client.actor(ACTOR_ID).call(run_input=run_input)
    
    results = list(client.dataset(run["defaultDatasetId"]).iterate_items())
    raw_df = pd.DataFrame(results)
    
    if not raw_df.empty:
        # 1. 컬럼명 통일 작업 (매우 중요!)
        # 조회수 관련 컬럼을 모두 'videoPlayCount'로 통일
        if 'playCount' in raw_df.columns:
            raw_df['videoPlayCount'] = raw_df['playCount']
        
        # 좋아요 관련 컬럼 통일
        if 'likes' in raw_df.columns:
            raw_df['likesCount'] = raw_df['likes']

        # 2. 숫자형 변환
        raw_df['videoPlayCount'] = pd.to_numeric(raw_df.get('videoPlayCount', 0), errors='coerce').fillna(0)
        raw_df['likesCount'] = pd.to_numeric(raw_df.get('likesCount', 0), errors='coerce').fillna(0)

        # 3. 릴스 판별 (조회수가 0보다 크거나 비디오 타입인 경우)
        # Apify 데이터에서 비디오를 판별하는 여러 필드를 체크
        is_video = (raw_df.get('type') == 'Video') | (raw_df.get('isVideo') == True) | (raw_df['videoPlayCount'] > 0)
        raw_df['is_reels_custom'] = is_video

        # 4. 정렬 및 필터링
        reels_df = raw_df[raw_df['is_reels_custom'] == True].sort_values(by='videoPlayCount', ascending=False).head(100)
        feed_df = raw_df[raw_df['is_reels_custom'] == False].sort_values(by='likesCount', ascending=False).head(100)

        # 합쳐서 저장
        final_df = pd.concat([reels_df, feed_df])
        
        os.makedirs('data', exist_ok=True)
        final_df.to_csv('data/latest_monitoring.csv', index=False)
        print(f"✅ 동기화 완료: 릴스 {len(reels_df)}개 / 피드 {len(feed_df)}개")
    else:
        print("❌ 수집된 데이터가 없습니다.")

if __name__ == "__main__":
    fetch_data()
