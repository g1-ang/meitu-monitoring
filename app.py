import streamlit as st
import pandas as pd
import os
import re
from collections import Counter
import plotly.express as px

# 1. 페이지 설정
st.set_page_config(page_title="메이투 마케팅 실시간 대시보드", layout="wide")
st.title("🚀 메이투 즉각 모니터링 자동화 시스템")

# 2. 파일 불러오기 로직
data_dir = './data'
auto_data_path = os.path.join(data_dir, 'latest_monitoring.csv')

if os.path.exists(auto_data_path):
    file_path = auto_data_path
    st.sidebar.success("✅ 자동 업데이트된 최신 데이터를 표시 중입니다.")
else:
    # 자동 파일이 없을 경우 기존 csv 중 가장 최신 것 사용
    csv_files = sorted([f for f in os.listdir(data_dir) if f.endswith('.csv')], reverse=True) if os.path.exists(data_dir) else []
    file_path = os.path.join(data_dir, csv_files[0]) if csv_files else None
    st.sidebar.info("ℹ️ 기존 업로드된 데이터를 표시 중입니다.")

if file_path:
    try:
        df = pd.read_csv(file_path)
        
        # --- 데이터 전처리 ---
        # 날짜 처리
        if 'timestamp' in df.columns:
            df['timestamp'] = pd.to_datetime(df['timestamp'], errors='coerce')
            df = df.dropna(subset=['timestamp'])
            df['date_only'] = df['timestamp'].dt.date
        else:
            df['date_only'] = pd.Timestamp.now().date()

        # 조회수 및 좋아요 컬럼 숫자형 변환
        view_col = next((c for c in ['videoPlayCount', 'playCount', 'viewCount'] if c in df.columns), None)
        like_col = next((c for c in ['likesCount', 'likes'] if c in df.columns), None)
        
        df['view_count'] = pd.to_numeric(df[view_col], errors='coerce').fillna(0) if view_col else 0
        df['like_count'] = pd.to_numeric(df[like_col], errors='coerce').fillna(0) if like_col else 0

        # 사이드바 필터
        st.sidebar.header("🔍 필터링 설정")
        korean_only = st.sidebar.checkbox("한국 콘텐츠만 보기", value=True)
        date_range = st.sidebar.date_input("조회 기간", value=(df['date_only'].min(), df['date_only'].max()))

        # 필터링 적용
        df['caption'] = df['caption'].fillna('')
        if korean_only:
            df = df[df['caption'].str.contains('[가-힣]', regex=True)]
        if isinstance(date_range, tuple) and len(date_range) == 2:
            df = df[(df['date_only'] >= date_range[0]) & (df['date_only'] <= date_range[1])]

        # ---------------------------------------------------------
        # 📈 성과 요약 대시보드
        # ---------------------------------------------------------
        st.subheader("📈 성과 요약 분석")
        m1, m2, m3, m4 = st.columns(4)
        m1.metric("총 수집 콘텐츠", f"{len(df)}개")
        m2.metric("총 조회수 (릴스)", f"{int(df['view_count'].sum()):,}회")
        m3.metric("총 좋아요 (피드)", f"{int(df['like_count'].sum()):,}개")
        m4.metric("평균 조회수", f"{int(df['view_count'].mean()):,}회")

        # 성과 그래프
        col_g1, col_g2 = st.columns(2)
        with col_g1:
            daily_stats = df.groupby('date_only')[['view_count', 'like_count']].sum().reset_index()
            fig = px.line(daily_stats, x='date_only', y='view_count', title="일자별 조회수 트렌드", markers=True)
            st.plotly_chart(fig, use_container_width=True)
        with col_g2:
            top_acc = df.groupby('ownerUsername')['view_count'].sum().sort_values(ascending=False).head(10).reset_index()
            fig2 = px.bar(top_acc, x='view_count', y='ownerUsername', orientation='h', title="영향력 TOP 10 계정", color='view_count')
            st.plotly_chart(fig2, use_container_width=True)

        st.divider()

        # ---------------------------------------------------------
        # 📱 브랜드별 상세 피드 (릴스 vs 피드)
        # ---------------------------------------------------------
        tab1, tab2 = st.tabs(["✨ 메이투 (Meitu)", "📸 뷰티캠 (BeautyCam)"])

        def display_brand_grid(brand_keywords, brand_name):
            # 해당 브랜드 키워드가 포함된 데이터 필터링
            target = df[df['caption'].str.contains('|'.join(brand_keywords), case=False)]
            
            if not target.empty:
                # 키워드 분석
                all_text = " ".join(target['caption'].tolist())
                words = [w for w in re.findall(r'[가-힣]{2,}', all_text) if w not in ['진짜', '너무', '추천', '어플']+brand_keywords]
                most_common = Counter(words).most_common(10)
                
                st.write(f"### 🏷️ {brand_name} 인기 키워드")
                kw_cols = st.columns(10)
                for idx, (word, count) in enumerate(most_common):
                    kw_cols[idx].caption(f"**{word}**\n({count}회)")
                
                st.write("---")
                
                # [강화된 분류 로직]
                # 1. 릴스: update_data.py에서 만든 커스텀 플래그가 있으면 사용, 없으면 조회수 0보다 큰 것
                if 'is_reels_custom' in target.columns:
                    reels = target[target['is_reels_custom'] == True].sort_values(by='view_count', ascending=False).head(10)
                    feeds = target[target['is_reels_custom'] == False].sort_values(by='like_count', ascending=False).head(10)
                else:
                    reels = target[target['view_count'] > 0].sort_values(by='view_count', ascending=False).head(10)
                    feeds = target[target['view_count'] == 0].sort_values(by='like_count', ascending=False).head(10)

                col_left, col_right = st.columns(2)
                
                with col_left:
                    st.markdown("#### 🎬 인기 릴스 (조회수 기준)")
                    if not reels.empty:
                        for _, row in reels.iterrows():
                            with st.container(border=True):
                                if pd.notna(row.get('displayUrl')): st.image(row['displayUrl'], use_container_width=True)
                                st.write(f"**@{row.get('ownerUsername', 'unknown')}**")
                                st.write(f"🔥 조회수: **{int(row['view_count']):,}회**")
                                st.link_button("영상 보기", row.get('url', '#'))
                    else:
                        st.info("조건에 맞는 릴스 데이터가 없습니다.")

                with col_right:
                    st.markdown("#### 📸 인기 피드 (좋아요 기준)")
                    if not feeds.empty:
                        for _, row in feeds.iterrows():
                            with st.container(border=True):
                                if pd.notna(row.get('displayUrl')): st.image(row['displayUrl'], use_container_width=True)
                                st.write(f"**@{row.get('ownerUsername', 'unknown')}**")
                                st.write(f"❤️ 좋아요: **{int(row['like_count']):,}개**")
                                st.link_button("게시물 보기", row.get('url', '#'))
                    else:
                        st.info("조건에 맞는 피드 데이터가 없습니다.")
            else:
                st.warning(f"{brand_name} 데이터가 없습니다.")

        with tab1:
            display_brand_grid(['메이투', 'meitu'], "메이투")
        with tab2:
            display_brand_grid(['뷰티캠', 'beautycam'], "뷰티캠")

    except Exception as e:
        st.error(f"데이터를 표시하는 중 오류가 발생했습니다: {e}")
else:
    st.error("데이터 파일을 찾을 수 없습니다. GitHub Actions 실행 여부를 확인하세요.")
