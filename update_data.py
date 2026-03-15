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
        run_input = {"hashtags": KEYWORDS, "resultsLimit": 100}
        
        print(f"🚀 Apify 접속 중...")
        run = client.actor(ACTOR_ID).call(run_input=run_input)
        
        results = list(client.dataset(run["defaultDatasetId"]).iterate_items())
        raw_df = pd.DataFrame(results)
        
        if not raw_df.empty:
            # 컬럼명 정리 및 업데이트 시간 기록 (중요!)
            if 'playCount' in raw_df.columns: raw_df['videoPlayCount'] = raw_df['playCount']
            if 'likes' in raw_df.columns: raw_df['likesCount'] = raw_df['likes']
            raw_df['last_updated'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

            os.makedirs('data', exist_ok=True)
            raw_df.to_csv('data/latest_monitoring.csv', index=False)
            print(f"✅ 데이터 수집 및 저장 성공! ({len(raw_df)}건)")
        else:
            print("⚠️ 수집된 데이터가 없습니다.")
    except Exception as e:
        print(f"❌ 오류: {e}")

if __name__ == "__main__":
    fetch_data()
