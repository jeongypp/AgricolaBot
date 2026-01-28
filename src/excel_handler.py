import pandas as pd

class AgricolaData:
    def __init__(self, excel_path):
        # 엑셀 로드 (Card Index를 문자열로 변환하여 읽기)
        try:
            self.df = pd.read_excel(excel_path, dtype={'Card Index': str})
            # 인덱스 정리 (대문자 변환, 공백 제거)
            self.df['Card Index'] = self.df['Card Index'].str.upper().str.strip()
            print(f"✅ 엑셀 데이터 로드 완료: {len(self.df)}개 카드")
        except Exception as e:
            print(f"❌ 엑셀 로드 실패: {e}")
            self.df = None

    def get_card_info(self, card_id):
        if self.df is None: return None
        
        # 카드 ID로 검색
        card_id = card_id.upper().strip()
        match = self.df[self.df['Card Index'] == card_id]
        
        if not match.empty:
            return match.iloc[0].to_dict() # 해당 행을 딕셔너리로 반환
        return None