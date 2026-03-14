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
        "resultsLimit": 150, 
    }
    
    print("🚀 Apify 데이터 수집 시작...")
    run = client.actor(ACTOR_ID).call(run_input=run_input)
    
    results = list(client.dataset(run["defaultDatasetId"]).iterate_items())
    raw_df = pd.DataFrame(results)
    
    if not raw_df.empty:
        # 1. 컬럼명 통합
        if 'playCount' in raw_df.columns: raw_df['videoPlayCount'] = raw_df['playCount']
        if 'likes' in raw_df.columns: raw_df['likesCount'] = raw_df['likes']
        
        # 2. 숫자형 변환
        raw_df['videoPlayCount'] = pd.to_numeric(raw_df.get('videoPlayCount', 0), errors='coerce').fillna(0)
        raw_df['likesCount'] = pd.to_numeric(raw_df.get('likesCount', 0), errors='coerce').fillna(0)

        # 3. 릴스 판별
        is_video = (raw_df.get('type') == 'Video') | (raw_df.get('isVideo') == True) | (raw_df['videoPlayCount'] > 0)
        raw_df['is_reels_custom'] = is_video

        # 4. 정렬 및 합치기
        reels_df = raw_df[raw_df['is_reels_custom'] == True].sort_values(by='videoPlayCount', ascending=False)
        feed_df = raw_df[raw_df['is_reels_custom'] == False].sort_values(by='likesCount', ascending=False)
        final_df = pd.concat([reels_df, feed_df])
        
        # [수정] 경로 문제를 피하기 위해 'data' 폴더가 있는지 확인하고 저장
        os.makedirs('data', exist_ok=True)
        final_df.to_csv('data/latest_monitoring.csv', index=False)
        
        print(f"✅ 저장 완료: data/latest_monitoring.csv ({len(final_df)} rows)")
    else:
        print("❌ 수집된 데이터가 없습니다.")

if __name__ == "__main__":
    fetch_data()
