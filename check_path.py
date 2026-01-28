import os

# 테스트용
target_path = r'C:\Tesseract-OCR\tesseract.exe'

print(f"1. 경로가 존재하는가? : {os.path.exists(target_path)}")
print(f"2. 그것이 파일인가?   : {os.path.isfile(target_path)}")
print(f"3. 실행 권한이 있는가?: {os.access(target_path, os.X_OK)}")