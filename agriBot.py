import os
from dotenv import load_dotenv
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes
from src.excel_handler import AgricolaData
from src.ocr_engine import extract_cards_from_image
from telegram.request import HTTPXRequest  # <--- fix Timeout Prob.

# [설정] 텔레그램 봇 토큰 (BotFather에게 받은 토큰 입력)
TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
EXCEL_PATH = os.path.join("data", "agricola_data.xlsx")

# env 예외처리
if __name__ == '__main__':
    if not TOKEN:
        print("❌ 에러: .env 파일에 토큰이 없습니다.")
        exit()

# 데이터 로더 초기화
data_loader = AgricolaData(EXCEL_PATH)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("👋 안녕하세요! AgricolaBot입니다.\n아그리콜라 드래프트 화면을 캡처해서 보내주시면 티어를 분석해드립니다!")

async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.message.from_user
    await update.message.reply_text("🔍 이미지를 분석 중입니다... 잠시만 기다려주세요.")

    try:
        # 1. 텔레그램 서버에서 사진 다운로드 (가장 큰 사이즈)
        photo_file = await update.message.photo[-1].get_file()
        photo_bytes = await photo_file.download_as_bytearray()

        # 2. OCR 엔진으로 카드 ID 추출
        detected_ids = extract_cards_from_image(photo_bytes)
        
        if not detected_ids:
            await update.message.reply_text("⚠️ 이미지에서 카드 번호를 찾지 못했습니다.\n해상도가 높고 글자가 잘 보이는 스크린샷을 보내주세요.")
            return

        # 3. 엑셀 데이터 매칭 및 결과 정렬
        results = []
        for card_id in detected_ids:
            info = data_loader.get_card_info(card_id)
            if info:
                results.append(info)
        
        # 티어 순으로 정렬 (S -> 1 -> 2 -> 3)
        def sort_key(x):
            tier = str(x.get('Tier', '3')) # Tier 컬럼명 확인 필요
            if tier == 'S': return 0.0
            try: return float(tier)
            except: return 99.0
            
        results.sort(key=sort_key)

        # 4. 결과 메시지 작성
        if not results:
            await update.message.reply_text(f"❓ 인식된 번호({', '.join(detected_ids)})에 해당하는 데이터가 엑셀에 없습니다.")
            return

        message = f"✅ **분석 결과 ({len(results)}개)**\n\n"
        for item in results:
            # 이모지 추가 (티어별 색상)
            tier = str(item.get('Tier'))
            icon = "🔴" if tier == 'S' else "🔵" if tier == '1' else "⚪"
            
            message += f"{icon} **Tier {tier}** | {item['Card Index']} | PWR {item['PWR']}\n"
            message += f"└ {item['Card Name']}\n\n"

        await update.message.reply_text(message, parse_mode='Markdown')

    except Exception as e:
        print(f"에러 발생: {e}")
        await update.message.reply_text("❌ 처리 중 오류가 발생했습니다.")

if __name__ == '__main__':
    # [설정] 네트워크 Timeout 시간 늘리기 (기본값보다 길게 설정)
    # read_timeout=60 : 다운로드/업로드에 최대 60초까지 기다림
    req = HTTPXRequest(connection_pool_size=8, read_timeout=60, write_timeout=60, connect_timeout=60)

    # request 설정을 봇에 적용
    app = ApplicationBuilder().token(TOKEN).request(req).build()

    # 핸들러 등록
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.PHOTO, handle_photo))

    print("🤖 AgricolaBot이 실행되었습니다! (타임아웃 설정 적용됨)")
    app.run_polling()