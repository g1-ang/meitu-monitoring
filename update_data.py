import os
import pandas as pd
from apify_client import ApifyClient
from datetime import datetime

APIFY_TOKEN = os.getenv('APIFY_API_TOKEN')
ACTOR_ID = "apify/instagram-hashtag-scraper"
KEYWORDS = ["메이투", "뷰티캠", "meitu", "beautycam"]

def fetch_data():
    try:
        client = ApifyClient(APIFY_TOKEN)
        run_input = {"hashtags": KEYWORDS, "resultsLimit": 150}
        
        print(f"🚀 수집 시작: {datetime.now()}")
        run = client.actor(ACTOR_ID).call(run_input=run_input)
        
        results = list(client.dataset(run["defaultDatasetId"]).iterate_items())
        raw_df = pd.DataFrame(results)
        
        if not raw_df.empty:
            # 원본 컬럼명이 무엇이든 상관없이 videoPlayCount, likesCount로 통일
            if 'playCount' in raw_df.columns: raw_df['videoPlayCount'] = raw_df['playCount']
            if 'likes' in raw_df.columns: raw_df['likesCount'] = raw_df['likes']
            
            # 숫자 데이터 안전 변환
            raw_df['videoPlayCount'] = pd.to_numeric(raw_df.get('videoPlayCount', 0), errors='coerce').fillna(0)
            raw_df['likesCount'] = pd.to_numeric(raw_df.get('likesCount', 0), errors='coerce').fillna(0)
            
            # 저장
            os.makedirs('data', exist_ok=True)
            raw_df.to_csv('data/latest_monitoring.csv', index=False)
            print("✅ 데이터 저장 성공!")
        else:
            print("❌ 데이터가 없습니다.")
    except Exception as e:
        print(f"❌ 오류 발생: {e}")

if __name__ == "__main__":
    fetch_data()
