import os
import pandas as pd
from apify_client import ApifyClient

# 설정
APIFY_TOKEN = os.getenv('APIFY_API_TOKEN')
ACTOR_ID = "apify/instagram-hashtag-scraper"
KEYWORDS = ["메이투", "뷰티캠", "meitu", "beautycam"]

def fetch_data():
    client = ApifyClient(APIFY_TOKEN)
    
    # Apify 실행 설정
    run_input = {
        "hashtags": KEYWORDS,
        "resultsLimit": 100,  # 필요한 개수만큼 조절
    }
    
    print("🚀 Apify 수집 시작...")
    run = client.actor(ACTOR_ID).call(run_input=run_input)
    
    # 결과 가져오기 및 저장
    results = list(client.dataset(run["defaultDatasetId"]).iterate_items())
    df = pd.DataFrame(results)
    
    # 파일 저장 (기존 파일을 덮어쓰거나 날짜별로 저장)
    os.makedirs('data', exist_ok=True)
    df.to_csv('data/latest_monitoring.csv', index=False)
    print("✅ 데이터 업데이트 완료!")

if __name__ == "__main__":
    fetch_data()
