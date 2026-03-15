import streamlit as st
import pandas as pd
import os
import re

# 1. 페이지 설정
st.set_page_config(page_title="메이투 모니터링", layout="wide")
st.title("🚀 메이투 즉각 모니터링 자동화")

# 2. 파일 불러오기
data_path = './data/latest_monitoring.csv'

if os.path.exists(data_path):
    try:
        df = pd.read_csv(data_path)
        
        # 숫자 데이터 안전하게 변환
        df['view_count'] = pd.to_numeric(df.get('videoPlayCount', 0), errors='coerce').fillna(0).astype(int)
        df['like_count'] = pd.to_numeric(df.get('likesCount', 0), errors='coerce').fillna(0).astype(int)
        df['caption'] = df['caption'].fillna('')

        # 한국 콘텐츠 필터 (사이드바)
        korean_only = st.sidebar.checkbox("한국 콘텐츠만 보기", value=True)
        if korean_only:
            df = df[df['caption'].str.contains('[가-힣]', regex=True)]

        # ---------------------------------------------------------
        # 요약 수치
        # ---------------------------------------------------------
        m1, m2, m3 = st.columns(3)
        m1.metric("총 수집", f"{len(df)}개")
        m2.metric("총 조회수", f"{df['view_count'].sum():,}회")
        m3.metric("총 좋아요", f"{df['like_count'].sum():,}개")

        st.divider()

        # ---------------------------------------------------------
        # 브랜드 탭 (메이투 / 뷰티캠)
        # ---------------------------------------------------------
        tab1, tab2 = st.tabs(["✨ 메이투", "📸 뷰티캠"])

        def show_grid(brand_kw):
            target = df[df['caption'].str.contains('|'.join(brand_kw), case=False)]
            
            # 릴스(조회수 > 0) vs 피드(조회수 == 0)
            reels = target[target['view_count'] > 0].sort_values('view_count', ascending=False).head(10)
            feeds = target[target['view_count'] == 0].sort_values('like_count', ascending=False).head(10)

            col1, col2 = st.columns(2)
            with col1:
                st.subheader("🎬 인기 릴스")
                for _, row in reels.iterrows():
                    with st.container(border=True):
                        if pd.notna(row.get('displayUrl')): st.image(row['displayUrl'], use_container_width=True)
                        st.write(f"**@{row.get('ownerUsername', 'user')}** | 🔥 {row['view_count']:,}")
                        st.link_button("영상 보기", row.get('url', '#'))
            with col2:
                st.subheader("📸 인기 피드")
                for _, row in feeds.iterrows():
                    with st.container(border=True):
                        if pd.notna(row.get('displayUrl')): st.image(row['displayUrl'], use_container_width=True)
                        st.write(f"**@{row.get('ownerUsername', 'user')}** | ❤️ {row['like_count']:,}")
                        st.link_button("게시물 보기", row.get('url', '#'))

        with tab1: show_grid(['메이투', 'meitu'])
        with tab2: show_grid(['뷰티캠', 'beautycam'])

    except Exception as e:
        st.error(f"데이터 분석 중 오류 발생: {e}")
else:
    st.error("데이터 파일을 찾을 수 없습니다. GitHub에서 'Run workflow'가 성공했는지 확인해 주세요.")
