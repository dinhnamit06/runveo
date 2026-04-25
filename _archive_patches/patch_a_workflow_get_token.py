import sys
import os

with open(r'A_workflow_get_token.py', 'r', encoding='utf-8') as f:
    content = f.read()

target1 = """                        create_button = (
                            self.page.locator("button:has-text('Tạo')")
                            .filter(has_not_text="Trình tạo cảnh") \\
                            .filter(has_not_text="Không tạo được")
                            .last
                        )
                        await create_button.wait_for(state="visible", timeout=500)
                        await create_button.click()
                        return True"""

patch1 = """                        # Cải tiến: Dùng JavaScript đâm thẳng vào DOM để ép click, xuyên thủng mọi popup/che khuất và hỗ trợ cả tiếng Anh/Việt
                        clicked = await self.page.evaluate('''() => {
                            let btns = Array.from(document.querySelectorAll("button"));
                            let btn = btns.reverse().find(b => 
                                (b.textContent.includes("Tạo") || b.textContent.includes("Create") || b.innerText.includes("Tạo") || b.innerText.includes("Create")) &&
                                !b.textContent.includes("Trình tạo cảnh") &&
                                !b.textContent.includes("Không tạo được") &&
                                !b.disabled &&
                                b.style.display !== "none" && 
                                b.style.visibility !== "hidden"
                            );
                            if (btn) {
                                btn.click();
                                return true;
                            }
                            return false;
                        }''')
                        
                        if clicked:
                            return True
                            
                        # Fallback (Dự phòng nếu JS không tìm thấy)
                        create_button = (
                            self.page.locator("button:has-text('Tạo'), button:has-text('Create')")
                            .filter(has_not_text="Trình tạo cảnh") \\
                            .filter(has_not_text="Không tạo được")
                            .last
                        )
                        await create_button.wait_for(state="visible", timeout=500)
                        await create_button.click(force=True)
                        return True"""

if target1 in content:
    content = content.replace(target1, patch1)
else:
    print("WARNING: target1 not found in A_workflow_get_token.py")

with open(r'A_workflow_get_token.py', 'w', encoding='utf-8') as f:
    f.write(content)

# Update dist too
try:
    with open(r'dist\VEO_4.0_V2.2.6_PROMAX\_internal\A_workflow_get_token.py', 'r', encoding='utf-8') as f:
        content_dist = f.read()
    if target1 in content_dist:
        content_dist = content_dist.replace(target1, patch1)
    with open(r'dist\VEO_4.0_V2.2.6_PROMAX\_internal\A_workflow_get_token.py', 'w', encoding='utf-8') as f:
        f.write(content_dist)
except Exception:
    pass

print("Patched A_workflow_get_token.py with JS Evaluate Click")
