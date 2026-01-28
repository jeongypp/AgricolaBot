import os
from dotenv import load_dotenv
import cv2
import pytesseract
import re
import numpy as np

# 환경 변수 로드
load_dotenv()

# Tesseract 경로 설정
tess_path = os.getenv("TESSERACT_CMD")
if tess_path:
    pytesseract.pytesseract.tesseract_cmd = tess_path
else:
    # 기본값 (경로가 없을 경우)
    pytesseract.pytesseract.tesseract_cmd = r'C:\Program Files\Tesseract-OCR\tesseract.exe'

def preprocess_for_ocr(img_roi):
    """
    최적화된 전처리 파이프라인:
    1. 3배 확대 (작은 글씨 보정)
    2. 흰색 여백 추가 (테서렉트 인식률 상승 핵심)
    3. 적응형 이진화 (Adaptive Threshold - 카드 배경 무늬 제거)
    """
    # 1. 3배 확대
    img_roi = cv2.resize(img_roi, None, fx=3, fy=3, interpolation=cv2.INTER_CUBIC)
    
    # 2. 흰색 여백(Padding) 추가 (상하좌우 30px)
    img_roi = cv2.copyMakeBorder(
        img_roi, 
        top=30, bottom=30, left=30, right=30, 
        borderType=cv2.BORDER_CONSTANT, 
        value=(255, 255, 255) # 흰색
    )

    # 3. 그레이스케일
    gray = cv2.cvtColor(img_roi, cv2.COLOR_BGR2GRAY)
    
    # 4. 적응형 이진화 (Adaptive Threshold)
    # 조명이나 배경색 변화에 강하게 대응하여 글자만 선명하게 따냅니다.
    binary = cv2.adaptiveThreshold(
        gray, 
        255, 
        cv2.ADAPTIVE_THRESH_GAUSSIAN_C, 
        cv2.THRESH_BINARY, 
        31, # 블록 크기
        11  # 상수
    )
    
    return binary

def extract_cards_from_image(image_path_or_bytes):
    # 1. 이미지 로드
    if isinstance(image_path_or_bytes, str):
        img = cv2.imread(image_path_or_bytes)
    else:
        nparr = np.frombuffer(image_path_or_bytes, np.uint8)
        img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)

    if img is None:
        return []

    original_img = img.copy()
    
    # ---------------------------------------------------------
    # [Step 1] 카드 윤곽선(Contour) 찾기
    # ---------------------------------------------------------
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    blur = cv2.GaussianBlur(gray, (7, 7), 0) 
    edged = cv2.Canny(blur, 30, 150) 
    
    contours, _ = cv2.findContours(edged, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    detected_ids = []
    
    # (디버깅) 발견된 윤곽선 개수 확인
    print(f"[Debug] 발견된 총 윤곽선 개수: {len(contours)}")

    for cnt in contours:
        # 윤곽선 근사화
        epsilon = 0.02 * cv2.arcLength(cnt, True)
        approx = cv2.approxPolyDP(cnt, epsilon, True)
        area = cv2.contourArea(cnt)
        
        # [조건] 꼭짓점 4~8개 (둥근 모서리 고려) AND 일정 크기 이상
        if 4 <= len(approx) <= 8 and area > 5000: 
            x, y, w, h = cv2.boundingRect(approx)
            
            # 비율 체크 (세로로 긴 직사각형인지)
            aspect_ratio = float(w)/h
            if not (0.5 < aspect_ratio < 0.95):
                continue

            print(f"[Debug] 카드 후보 발견! (Area: {area})")

            # ---------------------------------------------------------
            # [Step 2] ROI(관심 영역) 추출 - 정엽님 튜닝값 적용 완료 ✅
            # ---------------------------------------------------------
            roi_x = x
            roi_y = y + int(h * 0.23) # [수정됨] 0.21 -> 0.23 (조금 더 아래로)
            roi_w = int(w * 0.24)     # 너비 24%
            roi_h = int(h * 0.08)     # 높이 8%

            roi_img = original_img[roi_y:roi_y+roi_h, roi_x:roi_x+roi_w]

            # ---------------------------------------------------------
            # [Step 3] OCR 수행
            # ---------------------------------------------------------
            processed_roi = preprocess_for_ocr(roi_img)
            
            # [설정] 화이트리스트(A-E, 0-9) + PSM 6(단일 블록)
            custom_config = r'--oem 3 --psm 6 -c tessedit_char_whitelist=ABCDE0123456789'
            text = pytesseract.image_to_string(processed_roi, config=custom_config)
            
            print(f"[Debug] ROI Result: '{text.strip()}'") # 결과 확인용

            # 패턴 매칭 (A102, C39 등)
            matches = re.findall(r'([A-E])\s*(\d{1,3})', text.upper())
            for char, num in matches:
                full_id = f"{char}{num}"
                clean_num = str(int(num)) # 039 -> 39 변환
                
                # 원본(C039)과 정제본(C39) 모두 저장 (엑셀 매칭 확률 높이기 위해)
                detected_ids.append(full_id)
                if full_id != f"{char}{clean_num}":
                    detected_ids.append(f"{char}{clean_num}")

    # ---------------------------------------------------------
    # [Fallback] 윤곽선 감지 실패 시 전체 스캔 (안전장치)
    # ---------------------------------------------------------
    if not detected_ids:
        print("[Info] 윤곽선 감지 실패(또는 텍스트 없음). 전체 이미지 스캔으로 전환합니다.")
        processed_full = preprocess_for_ocr(original_img)
        custom_config = r'--oem 3 --psm 6 -c tessedit_char_whitelist=ABCDE0123456789'
        text = pytesseract.image_to_string(processed_full, config=custom_config)
        matches = re.findall(r'([A-E])\s*(\d{1,3})', text.upper())
        for char, num in matches:
            detected_ids.append(f"{char}{num}")
            detected_ids.append(f"{char}{int(num)}")

    return list(set(detected_ids))