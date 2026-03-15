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
    csv_files = sorted([f for f in os.listdir(data_dir) if f.endswith('.csv')], reverse=True) if os.path.exists(data_dir) else []
    file_path = os.path.join(data_dir, csv_files[0]) if csv_files else None
    st.sidebar.info("ℹ️ 기존 업로드된 데이터를 표시 중입니다.")

if file_path:
    try:
        # 데이터 읽기
        df = pd.read_csv(file_path)
        
        # --- 데이터 전처리 (에러 방지 강화) ---
        if 'timestamp' in df.columns:
            df['timestamp'] = pd.to_datetime(df['timestamp'], errors='coerce')
            df = df.dropna(subset=['timestamp'])
            df['date_only'] = df['timestamp'].dt.date
        else:
            df['date_only'] = pd.Timestamp.now().date()

        # [수정된 부분] 숫자 변환 로직을 더 안전하게 변경
        def safe_numeric(series):
            return pd.to_numeric(series, errors='coerce').fillna(0).astype(int)

        df['view_count'] = safe_numeric(df.get('videoPlayCount', 0))
        df['like_count'] = safe_numeric(df.get('likesCount', 0))

        # 사이드바 필터
        st.sidebar.header("🔍 필터링 설정")
        korean_only = st.sidebar.checkbox("한국 콘텐츠만 보기", value=True)
        
        # 날짜 범위 설정 안전하게
        min_date = df['date_only'].min() if not df.empty else pd.Timestamp.now().date()
        max_date = df['date_only'].max() if not df.empty else pd.Timestamp.now().date()
        date_range = st.sidebar.date_input("조회 기간", value=(min_date, max_date))

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

        if not df.empty:
            col_g1, col_g2 = st.columns(2)
            with col_g1:
                daily_stats = df.groupby('date_only')[['view_count', 'like_count']].sum().reset_index()
                fig = px.line(daily_stats, x='date_only', y='view_count', title="일자별 조회수 트렌드", markers=True)
                st.plotly_chart(fig, use_container_width=True)
            with col_g2:
                if 'ownerUsername' in df.columns:
                    top_acc = df.groupby('ownerUsername')['view_count'].sum().sort_values(ascending=False).head(10).reset_index()
                    fig2 = px.bar(top_acc, x='view_count', y='ownerUsername', orientation='h', title="영향력 TOP 10 계
