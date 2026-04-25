import asyncio
import json
from playwright.async_api import async_playwright
import os
from pathlib import Path

WORKSPACE_DIR = Path(__file__).resolve().parent
CHROME_USER_DATA_ROOT = Path(os.getenv("GROK_CHROME_USER_DATA_ROOT", str(WORKSPACE_DIR / "chrome_user_data_test")))

async def main():
    print("🚀 Đang khởi động trình duyệt để bắt Payload Nano Banana / Imagen 4...")
    async with async_playwright() as p:
        browser = await p.chromium.launch_persistent_context(
            user_data_dir=str(CHROME_USER_DATA_ROOT),
            headless=False,
            viewport={"width": 1280, "height": 720}, # Kích thước màn hình chuẩn để không bị cắt chữ
            args=["--window-size=1280,720"]
        )
        
        page = browser.pages[0] if browser.pages else await browser.new_page()
        
        captured = False

        async def handle_request(request):
            nonlocal captured
            if "batchGenerateImages" in request.url:
                print(f"\n🎉 ĐÃ BẮT ĐƯỢC REQUEST: {request.url}")
                
                headers = request.headers
                post_data = request.post_data
                
                try:
                    parsed_data = json.loads(post_data) if post_data else {}
                except:
                    parsed_data = post_data

                output = {
                    "url": request.url,
                    "headers": headers,
                    "post_data": parsed_data
                }
                
                with open("payload_nano.json", "w", encoding="utf-8") as f:
                    json.dump(output, f, indent=4, ensure_ascii=False)
                
                print("✅ Đã lưu toàn bộ payload vào file 'payload_nano.json'")
                captured = True

        page.on("request", handle_request)
        
        print("👉 Mở trang ImageFX...")
        await page.goto("https://labs.google/fx/tools/image-fx", wait_until="domcontentloaded")
        
        # Tự động zoom nhỏ trang web xuống 80% để đảm bảo thấy nút
        await page.evaluate("document.body.style.zoom = '80%'")
        
        print("⏳ Đang chờ trang tải xong...")
        await asyncio.sleep(5)
        
        print("🤖 Tự động nhập prompt 'con mèo' và bấm tạo...")
        try:
            # Tìm ô nhập liệu và gõ chữ
            # Google Flow thường dùng textarea hoặc thẻ div contenteditable
            candidates = [
                "textarea#PINHOLE_TEXT_AREA_ELEMENT_ID",
                "textarea[placeholder*='Bạn muốn tạo gì']",
                "textarea[placeholder*='What do you want']",
                "div[contenteditable='true'][role='textbox']"
            ]
            
            for sel in candidates:
                if await page.locator(sel).count() > 0:
                    await page.locator(sel).first.fill("con mèo")
                    break
            else:
                # Fallback, just press tab multiple times or something, or assume the user will do it
                print("⚠️ Không tìm thấy ô nhập liệu tự động, bạn vui lòng gõ 'con mèo' và ấn phím ENTER nhé!")
            
            # Cố gắng tự bấm phím Enter
            await page.keyboard.press("Enter")
            
        except Exception as e:
            print(f"⚠️ Không thể auto-click: {e}")
            print("👉 Bạn hãy tự gõ prompt và ấn ENTER hoặc ấn Ctrl + (-) để thu nhỏ màn hình nhé!")
            
        for _ in range(120):
            if captured:
                break
            await asyncio.sleep(1)
            
        if not captured:
            print("\n⚠️ Đã hết thời gian chờ mà chưa bắt được payload.")
        else:
            print("\n✅ Thành công! Bạn có thể đóng Chrome và gửi nội dung file payload_nano.json cho tôi.")
            
        await browser.close()

if __name__ == "__main__":
    asyncio.run(main())
