import os
from dotenv import load_dotenv
import cv2
import pytesseract
import re
import numpy as np

# 환경변수 로드
load_dotenv()

tess_path = os.getenv("TESSERACT_CMD")
if tess_path:
    pytesseract.pytesseract.tesseract_cmd = tess_path
else:
    # 기본값 설정 (혹시 .env 설정 안 했을 때를 대비)
    pytesseract.pytesseract.tesseract_cmd = r'C:\Tesseract-OCR\tesseract.exe'

def extract_cards_from_image(image_path_or_bytes):
    """
    이미지 처리 파이프라인 개선: 화이트리스트 적용으로 노이즈 원천 차단
    """
    # 1. 이미지 로드
    if isinstance(image_path_or_bytes, str):
        img = cv2.imread(image_path_or_bytes)
    else:
        nparr = np.frombuffer(image_path_or_bytes, np.uint8)
        img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)

    if img is None:
        return []

    # ---------------------------------------------------------
    # [전처리] 글자를 선명하게 만들기
    # ---------------------------------------------------------
    
    # 1) 이미지 확대 (3배) - 작은 글씨 인식률 향상
    img = cv2.resize(img, None, fx=3, fy=3, interpolation=cv2.INTER_CUBIC)

    # 2) 그레이스케일 변환
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

    # 3) 이진화 (Thresholding)
    # 배경 노이즈를 줄이기 위해 약간 강하게 잡습니다.
    # 127보다 어두운 건 검은색, 밝은 건 흰색으로 만듭니다.
    _, binary = cv2.threshold(gray, 127, 255, cv2.THRESH_BINARY)

    # ---------------------------------------------------------
    # [핵심 기술] 화이트리스트 설정 (Whitelist)
    # ---------------------------------------------------------
    # 설명: 테서렉트에게 "A,B,C,D,E"와 "0~9" 숫자만 읽으라고 강제합니다.
    # 이렇게 하면 그림을 이상한 한글이나 특수문자로 읽는 오류가 사라집니다.
    custom_config = r'--oem 3 --psm 6 -c tessedit_char_whitelist=ABCDE0123456789'
    
    text = pytesseract.image_to_string(binary, config=custom_config)

    print(f"\n[DEBUG] 읽은 텍스트: {text}") # 터미널에서 확인용

    # ---------------------------------------------------------
    # [후처리] 패턴 매칭
    # ---------------------------------------------------------
    text_upper = text.upper()
    
    # 패턴: A~E 뒤에 숫자가 붙은 경우 (공백 허용)
    matches = re.findall(r'([A-E])\s*(\d{1,3})', text_upper)
    
    card_ids = []
    for char, num in matches:
        # 1. 원본 조합 (예: C039)
        full_id = f"{char}{num}"
        
        # 2. 0 제거 버전 (예: C039 -> C39)
        # 엑셀에 'C39'로 저장되어 있을 수도 있으므로 둘 다 찾기.
        clean_num = str(int(num))
        clean_id = f"{char}{clean_num}"
        
        card_ids.append(full_id)
        if full_id != clean_id:
            card_ids.append(clean_id)
    
    return list(set(card_ids))