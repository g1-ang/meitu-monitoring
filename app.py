import streamlit as st
import pandas as pd
import os

# 1. 페이지 설정
st.set_page_config(page_title="메이투 모니터링", layout="wide")
st.title("🚀 메이투 즉각 모니터링 자동화")

# 2. 파일 불러오기
data_path = './data/latest_monitoring.csv'

if os.path.exists(data_path):
    try:
        # 데이터 읽기
        df = pd.read_csv(data_path)
        
        # [에러 해결 핵심] replace 대신 fillna만 사용하여 안전하게 변환
        def clean_num(df, col_names):
            # 후보 컬럼들 중 실제로 있는 것 하나를 찾음
            found_col = None
            for c in col_names:
                if c in df.columns:
                    found_col = c
                    break
            
            if found_col is not None:
                # 찾았다면 숫자로 변환하고 비어있으면 0으로 채움
                return pd.to_numeric(df[found_col], errors='coerce').fillna(0).astype(int)
            else:
                # 아예 컬럼이 없으면 0으로 채운 리스트 반환
                return [0] * len(df)

        # 조회수와 좋아요 처리
        df['view_count'] = clean_num(df, ['videoPlayCount', 'playCount'])
        df['like_count'] = clean_num(df, ['likesCount', 'likes'])
        
        # 캡션 처리 (글자)
        df['caption'] = df['caption'].fillna('').astype(str)

        # 3. 화면 표시 (요약 수치)
        m1, m2, m3 = st.columns(3)
        m1.metric("총 수집 콘텐츠", f"{len(df)}개")
        m2.metric("총 조회수 (릴스)", f"{int(df['view_count'].sum()):,}회")
        m3.metric("총 좋아요 (피드)", f"{int(df['like_count'].sum()):,}개")

        st.divider()

        # 4. 브랜드별 탭
        tab1, tab2 = st.tabs(["✨ 메이투 (Meitu)", "📸 뷰티캠 (BeautyCam)"])

        def show_grid(brand_kw):
            target = df[df['caption'].str.contains('|'.join(brand_kw), case=False, na=False)]
            
            if target.empty:
                st.info(f"{brand_kw[0]} 관련 데이터가 아직 없습니다.")
                return

            # 릴스(조회수 중심) vs 피드(좋아요 중심)
            reels = target[target['view_count'] > 0].sort_values('view_count', ascending=False).head(12)
            feeds = target[target['view_count'] == 0].sort_values('like_count', ascending=False).head(12)

            col1, col2 = st.columns(2)
            with col1:
                st.subheader("🎬 인기 릴스")
                for _, row in reels.iterrows():
                    with st.container(border=True):
                        img = row.get('displayUrl')
                        if pd.notna(img) and str(img).startswith('http'): 
                            st.image(img, use_container_width=True)
                        st.write(f"**@{row.get('ownerUsername', 'user')}**")
                        st.write(f"🔥 조회수: {int(row['view_count']):,}회")
                        st.link_button("영상 보기", row.get('url', '#'))

            with col2:
                st.subheader("📸 인기 피드")
                for _, row in feeds.iterrows():
                    with st.container(border=True):
                        img = row.get('displayUrl')
                        if pd.notna(img) and str(img).startswith('http'): 
                            st.image(img, use_container_width=True)
                        st.write(f"**@{row.get('ownerUsername', 'user')}**")
                        st.write(f"❤️ 좋아요: {int(row['like_count']):,}개")
                        st.link_button("게시물 보기", row.get('url', '#'))

        with tab1: show_grid(['메이투', 'meitu'])
        with tab2: show_grid(['뷰티캠', 'beautycam'])

    except Exception as e:
        st.error(f"⚠️ 대시보드 구성 중 오류 발생: {e}")
else:
    st.error("📂 데이터 파일을 찾을 수 없습니다. GitHub에서 데이터 수집이 완료되었는지 확인해 주세요.")
