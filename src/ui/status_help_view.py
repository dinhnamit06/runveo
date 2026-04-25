from __future__ import annotations

import re
from pathlib import Path

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QLabel, QScrollArea, QVBoxLayout, QWidget

from src.core.settings_manager import DATA_GENERAL_DIR


HELP_GUIDE_FILE = Path(DATA_GENERAL_DIR) / "huong_dan_su_dung_tool.md"


DEFAULT_GUIDE_TEXT = """1) Quy Trình Chung Khi Dùng Tool
- Bước 1: Vào Cài đặt, nhập License Key, Gemini API Key, tài khoản VEO/GROK và thư mục xuất file.
- Bước 2: Chọn đúng tab theo nhu cầu: Text to Video, Image to Video, Ý tưởng, Sao chép video, Tạo ảnh, Đồng bộ nhân vật hoặc GROK.
- Bước 3: Chọn model, tỷ lệ khung hình, số lượng output, giọng đọc và phong cách trước khi bấm chạy.
- Bước 4: Kiểm tra bảng Status sau khi tool tạo dòng; có thể sửa prompt từng dòng trước khi render.
- Bước 5: Bấm nút bắt đầu hoặc đưa job vào hàng chờ; theo dõi trạng thái Đang chờ, Đang tạo, Hoàn thành hoặc Lỗi.
- LƯU Ý: Mỗi dòng trong bảng Status là một cảnh hoặc một ảnh. Không tắt tool khi đang có dòng Đang tạo.
- LƯU Ý: Nếu bị lỗi mạng, lỗi token hoặc lỗi API, chọn dòng lỗi rồi dùng Tạo lại video/Tạo lại lỗi.

2) Cài Đặt Key, Tài Khoản Và Thư Mục Xuất
- Bước 1: Vào tab Cài đặt, nhập License Key rồi bấm Kích hoạt nếu chưa kích hoạt.
- Bước 2: Nhập Gemini API Key; có thể lưu nhiều key để tool tự xoay key khi bị hết lượt.
- Bước 3: Chọn tài khoản/model VEO hoặc GROK đúng với sản phẩm muốn chạy.
- Bước 4: Chọn thư mục Output để video, ảnh và file storytelling được lưu đúng nơi.
- Bước 5: Bấm Lưu sau mỗi nhóm cài đặt quan trọng.
- LƯU Ý: Nếu tạo ảnh/video không chạy, kiểm tra lại token, tài khoản đăng nhập, API key và quyền ghi của thư mục Output.
- LƯU Ý: Nếu chữ tiếng Việt bị lỗi, giữ file hướng dẫn và prompt ở UTF-8.

3) Tạo Video Từ Văn Bản
- Bước 1: Chọn tab Text to Video.
- Bước 2: Nhập prompt, mỗi dòng là một video/cảnh riêng.
- Bước 3: Chọn tỷ lệ khung hình, model, số lượng video muốn tạo và giọng đọc nếu cần.
- Bước 4: Bấm BẮT ĐẦU TẠO VIDEO TỪ VĂN BẢN.
- Bước 5: Sau khi tool đẩy prompt vào bảng Status, có thể sửa prompt ở từng dòng trước khi chạy lại.
- LƯU Ý: Prompt nên có đầy đủ bối cảnh, nhân vật, hành động, camera, ánh sáng, âm thanh và quy tắc không chữ trong khung hình.

4) Tạo Video Từ Ảnh
- Bước 1: Chọn tab Image to Video và chọn chế độ Tạo Video Từ Ảnh.
- Bước 2: Tải ảnh đầu vào; ảnh nên rõ chủ thể, không quá mờ, không chứa chữ quan trọng.
- Bước 3: Nhập prompt tương ứng theo từng dòng; thứ tự prompt sẽ ghép với thứ tự ảnh.
- Bước 4: Chọn tỷ lệ, model và số lượng output rồi bấm BẮT ĐẦU.
- LƯU Ý: Nếu dùng ảnh nhân vật, prompt nên nhắc giữ nguyên khuôn mặt, trang phục, màu tóc và dáng người.
- LƯU Ý: Có thể click vào preview trong bảng Status để mở file đã tạo.

5) Tạo Video Từ Ảnh Đầu Và Ảnh Cuối
- Bước 1: Chọn tab Image to Video và chọn chế độ Ảnh Đầu - Ảnh Cuối.
- Bước 2: Tải danh sách ảnh bắt đầu.
- Bước 3: Tải danh sách ảnh kết thúc theo đúng thứ tự tương ứng.
- Bước 4: Nhập prompt mô tả chuyển động từ ảnh đầu sang ảnh cuối.
- Bước 5: Bấm BẮT ĐẦU TẠO VIDEO TỪ ẢNH ĐẦU - ẢNH CUỐI.
- LƯU Ý: Ảnh đầu và ảnh cuối nên cùng nhân vật, cùng tỷ lệ khung hình và cùng phong cách để chuyển động ổn định.

6) Tạo Ảnh Từ Prompt Hoặc Ảnh Tham Chiếu
- Bước 1: Chọn tab Tạo Ảnh.
- Bước 2: Chọn Từ Prompt nếu muốn AI tạo ảnh hoàn toàn từ mô tả.
- Bước 3: Chọn Từ Ảnh Tham Chiếu nếu muốn giữ nhân vật, sản phẩm hoặc phong cách từ ảnh mẫu.
- Bước 4: Nhập prompt hàng loạt, mỗi dòng là một ảnh riêng.
- Bước 5: Chọn model tạo ảnh, tỷ lệ khung hình và bấm Bắt đầu Tạo Ảnh.
- LƯU Ý: Với ảnh tham chiếu, gọi đúng tên nhân vật/sản phẩm trong prompt để AI bám tốt hơn.
- LƯU Ý: Nếu dùng ảnh để làm storytelling, mỗi cảnh nên chỉ cần một ảnh rõ ý chính.

7) Tạo Video Từ Ý Tưởng, Link Báo Hoặc Truyện Chữ
- Bước 1: Chọn tab Ý tưởng to Video.
- Bước 2: Ở Nguồn nội dung, chọn Tự nhập nếu dán ý tưởng/kịch bản thủ công.
- Bước 3: Chọn Từ link nếu muốn dán link báo, link truyện chữ hoặc nội dung web để AI tự đọc và tóm thành cảnh.
- Bước 4: Chọn Từ file PDF nếu muốn nhập PDF truyện chữ/truyện tranh có layer text.
- Bước 5: Ở Loại nguồn, chọn Tự động, Báo, Truyện chữ hoặc Truyện tranh để AI hiểu kiểu nội dung đầu vào.
- Bước 6: Chọn Số cảnh, Phong cách, Ngôn ngữ thoại, Giọng đọc và Kiểu xuất.
- Bước 7: Chọn Kiểu xuất Video nếu muốn tool tạo prompt rồi chạy video bằng workflow video cũ.
- Bước 8: Chọn Kiểu xuất Ảnh storytelling nếu muốn tool chỉ tạo ảnh từng cảnh rồi xuất MP4 chuyển động nhẹ có voice TTS.
- LƯU Ý: Mục Phong cách là phong cách đầu ra cuối cùng. Không cần phân tích phong cách đầu vào hay mục chuyển thể riêng.
- LƯU Ý: Với Kiểu xuất Video, Giọng đọc chỉ là phong cách giọng được chèn vào prompt; tool không tạo file TTS riêng.
- LƯU Ý: Với Kiểu xuất Video, tool dùng JSON nội bộ để chia cảnh ổn định, sau đó tự chuyển sang prompt tiếng Anh dạng VIDEO PROMPT + AUDIO / TTS trước khi gửi sang VEO. Lời đọc vẫn giữ theo ngôn ngữ thoại đã chọn.
- LƯU Ý: Nếu dùng link, ô Kịch bản/Ý tưởng có thể dùng làm ghi chú thêm như giọng kể, độ dài, góc nhìn, yêu cầu tránh nhạy cảm.
- LƯU Ý: Với Truyện tranh, link hoặc PDF cần có chữ/caption/dialogue đọc được. PDF chỉ là ảnh scan không có OCR thì tool sẽ báo không trích được chữ.

8) Chế Độ Ảnh Storytelling
- Bước 1: Vào tab Ý tưởng to Video.
- Bước 2: Chọn Kiểu xuất là Ảnh storytelling.
- Bước 3: Chọn phong cách đầu ra như Hyper Realistic, Anime, Cartoon, Stick Figure, Manga, Comic, Low Poly hoặc phong cách khác.
- Bước 4: Chọn TTS và Giọng đọc. Edge TTS có danh sách giọng riêng, ưu tiên giọng Việt Hoài My và Nam Minh. Có thể bấm Nghe thử để kiểm tra giọng.
- LƯU Ý: Muốn Edge TTS chạy trong bản source/build mới, môi trường Python cần có gói edge-tts; nếu không có, tool sẽ tự fallback.
- Bước 5: Bấm chạy; tool tạo prompt ảnh trước, tạo ảnh từng cảnh, rồi ghép ảnh thành MP4.
- Bước 6: MP4 storytelling có hiệu ứng chuyển động nhẹ trên ảnh, không dùng text-to-video.
- LƯU Ý: Chế độ này phù hợp với truyện kể, báo kể lại, tóm tắt chương truyện, video giọng đọc, video kể chuyện faceless.
- LƯU Ý: Nếu TTS chính không khả dụng, tool sẽ fallback để không làm hỏng quá trình xuất video.
- LƯU Ý: Vì đây là ảnh chuyển động nhẹ, prompt nên tập trung vào khoảnh khắc chính, cảm xúc, bố cục và nhân vật của từng cảnh.

9) Sao Chép Video Với Độ Copy 50% - 100%
- Bước 1: Chọn tab Sao chép video.
- Bước 2: Chọn video nguồn cần phân tích.
- Bước 3: Chọn ngôn ngữ đích, giọng đọc, phong cách đầu ra và độ copy.
- Bước 4: Kéo độ copy từ 50% đến 100%.
- Bước 5: Nếu muốn biến đổi nội dung, nhập vào ô Ý tưởng chỉnh sửa, ví dụ đổi giới tính/độ tuổi/nghề nghiệp nhân vật, đổi bối cảnh, đổi cảm xúc hoặc đổi đạo cụ.
- Mức 50% - 60%: Chỉ lấy ý tưởng, cấu trúc cảm xúc và phong cách cốt lõi; nhân vật, bối cảnh, hành động và chi tiết sẽ được làm mới nhiều.
- Mức 61% - 75%: Giữ nhịp kể, mạch chính và phong cách, nhưng thay đổi nhiều chi tiết để ra bản mới.
- Mức 76% - 99%: Bám khá sát bố cục, nhịp cảnh và camera, chỉ đổi nhẹ chi tiết phụ.
- Mức 100%: Bám sát nhất cấu trúc, cảnh, hành động, camera và phong cách của video nguồn.
- Bước 6: Bấm phân tích; tool sẽ tạo prompt đủ mở bài, thân bài, kết bài cho video.
- LƯU Ý: Chọn Phong cách đầu ra là đủ. Không cần mục chuyển thể riêng; AI sẽ tự làm video theo phong cách đã chọn.
- LƯU Ý: Nếu muốn tránh giống 100%, nên dùng 50% - 75% để lấy ý tưởng nhưng tạo bản mới an toàn hơn.
- LƯU Ý: Ô Ý tưởng chỉnh sửa là tùy chọn; bỏ trống thì tool sao chép theo video nguồn như bình thường.

10) Đồng Bộ Nhân Vật
- Bước 1: Chọn tab Đồng bộ nhân vật.
- Bước 2: Tải ảnh nhân vật, đặt tên nhân vật rõ ràng, tối đa khoảng 10 nhân vật.
- Bước 3: Trong prompt, gọi nhân vật bằng đúng cú pháp tên đã đặt, ví dụ {Nam}, {Linh}.
- Bước 4: Nhập prompt cho từng cảnh và bấm TẠO VIDEO ĐỒNG NHẤT NHÂN VẬT.
- LƯU Ý: Mỗi prompt nên dùng tối đa 3 nhân vật để giữ chất lượng và độ ổn định.
- LƯU Ý: Ảnh nhân vật nên rõ mặt, rõ trang phục, không bị che khuất quá nhiều.

11) Hàng Chờ Và Bảng Status
- Trạng thái Đang chờ nghĩa là dòng đã vào hàng chờ nhưng chưa gửi request.
- Trạng thái Đang lấy token nghĩa là tool đang lấy token tài khoản để gửi yêu cầu.
- Trạng thái Đã gửi request nghĩa là yêu cầu đã gửi lên hệ thống tạo ảnh/video.
- Trạng thái Đang tải video nghĩa là file đang được tải về thư mục Output.
- Trạng thái Hoàn thành nghĩa là đã có file ảnh/video trong ô preview.
- Trạng thái Lỗi nghĩa là dòng đó cần kiểm tra thông báo lỗi hoặc chạy lại.
- Có thể tích chọn nhiều dòng để tạo lại, xóa file, ghép video hoặc xử lý theo nhóm.
- LƯU Ý: Không nên chạy nhiều workflow cùng lúc nếu tài khoản hoặc mạng yếu.

12) Ghép Video Và Xuất File
- Bước 1: Sau khi nhiều cảnh đã hoàn thành, chọn các dòng muốn ghép.
- Bước 2: Bấm Nối video để ghép các clip theo thứ tự trong bảng Status.
- Bước 3: Kiểm tra thư mục Output để lấy file cuối.
- LƯU Ý: Trước khi ghép, nên đảm bảo các cảnh cùng tỷ lệ khung hình và cùng chất lượng.
- LƯU Ý: Với Storytelling, tool tự ghép ảnh thành MP4 sau khi ảnh hoàn tất, không cần bấm Nối video.

13) Lỗi Thường Gặp Và Cách Xử Lý
- Lỗi thiếu API key: Vào Cài đặt, nhập Gemini API Key rồi lưu lại.
- Lỗi thiếu link: Khi chọn Từ link, phải dán link vào ô Link nguồn.
- Lỗi không tạo được ảnh/video: Kiểm tra tài khoản, token, mạng, model và giới hạn tài khoản.
- Lỗi không có output: Chạy lại dòng lỗi hoặc giảm số lượng output.
- Lỗi prompt bị từ chối: Sửa prompt bớt nhạy cảm, tránh người thật, thương hiệu, máu me, nội dung vi phạm.
- Lỗi voice/TTS: Chọn giọng khác hoặc để Không có giọng đọc; Storytelling vẫn xuất được nếu phải fallback audio im lặng.
- Lỗi chữ trong video/ảnh: Thêm yêu cầu không chữ, không subtitle, không logo, không watermark vào prompt.
- Lỗi nhân vật không đồng nhất: Dùng ảnh tham chiếu rõ hơn, giảm số nhân vật trong cảnh và gọi tên nhân vật nhất quán.

14) Mẹo Viết Prompt Ổn Định
- Prompt tốt nên có nhân vật, bối cảnh, hành động, camera, ánh sáng, cảm xúc, phong cách và âm thanh.
- Với video kể chuyện, mỗi cảnh nên có một hành động chính, không nhồi quá nhiều sự kiện.
- Với phong cách hoạt hình, ghi rõ loại hoạt hình muốn xuất như anime, cartoon, comic, stick figure hoặc Pixar/Disney 3D.
- Với phong cách chân thực, ghi rõ realistic, cinematic lighting, natural colors, depth of field và camera movement.
- Luôn thêm quy tắc không chữ trong khung hình nếu không muốn AI sinh chữ sai.
- Nếu copy video 50%, hãy yêu cầu giữ ý tưởng và nhịp cảm xúc nhưng đổi nhân vật, bối cảnh và chi tiết hình ảnh.
"""


def get_status_help_file_path() -> Path:
    try:
        HELP_GUIDE_FILE.parent.mkdir(parents=True, exist_ok=True)
    except Exception:
        pass
    try:
        if not HELP_GUIDE_FILE.exists():
            HELP_GUIDE_FILE.write_text(DEFAULT_GUIDE_TEXT, encoding="utf-8")
    except Exception:
        pass
    return HELP_GUIDE_FILE


def _load_help_groups() -> list[tuple[str, list[str]]]:
    path = get_status_help_file_path()
    try:
        text = path.read_text(encoding="utf-8")
    except Exception:
        text = DEFAULT_GUIDE_TEXT

    groups: list[tuple[str, list[str]]] = []
    current_title = ""
    current_lines: list[str] = []

    header_re = re.compile(r"^\s*(\d+\)\s*.+)$")
    bullet_re = re.compile(r"^\s*[-*•]\s*(.+)$")

    def flush_group() -> None:
        nonlocal current_title, current_lines
        title = str(current_title or "").strip()
        lines = [str(item or "").strip() for item in current_lines if str(item or "").strip()]
        if title and lines:
            groups.append((title, lines))
        current_title = ""
        current_lines = []

    for raw_ln in str(text or "").splitlines():
        ln = str(raw_ln or "").strip()
        if not ln:
            continue

        if header_re.match(ln):
            flush_group()
            current_title = ln
            continue

        bullet_match = bullet_re.match(ln)
        if bullet_match:
            current_lines.append(str(bullet_match.group(1) or "").strip())
            continue

        if current_title:
            current_lines.append(ln)

    flush_group()

    if groups:
        return groups

    # Fallback minimal group if file is malformed
    return [
        (
            "1) Hướng Dẫn Sử Dụng",
            [
                "Nội dung file hướng dẫn chưa đúng định dạng.",
                f"Vui lòng chỉnh lại file: {path}",
            ],
        )
    ]


def _add_box(layout: QVBoxLayout, title: str, lines: list[str]) -> None:
    box = QWidget()
    box.setStyleSheet("border:1px solid #c8d7f2; border-radius:10px; background:#eaf2ff;")
    bl = QVBoxLayout(box)
    bl.setContentsMargins(12, 10, 12, 10)
    bl.setSpacing(6)

    t = QLabel(title)
    t.setStyleSheet("font-weight:800; color:#1f2d48;")
    bl.addWidget(t)

    for ln in lines:
        lb = QLabel("• " + ln)
        lb.setWordWrap(True)
        lb.setStyleSheet(
            "border:1px solid #c8d7f2; border-radius:8px; background:#f2f7ff; padding:6px 8px; color:#1f2d48;"
        )
        bl.addWidget(lb)

    layout.addWidget(box)


def build_status_help_view() -> QWidget:
    wrap = QWidget()
    root = QVBoxLayout(wrap)
    root.setContentsMargins(8, 8, 8, 8)
    root.setSpacing(10)

    title = QLabel("Hướng Dẫn Sử Dụng")
    title.setStyleSheet("font-weight:800; color:#1f2d48; font-size:14px;")
    root.addWidget(title)

    scroll = QScrollArea()
    scroll.setWidgetResizable(True)
    scroll.setFrameShape(QScrollArea.Shape.NoFrame)
    root.addWidget(scroll, 1)

    body = QWidget()
    scroll.setWidget(body)
    v = QVBoxLayout(body)
    v.setContentsMargins(6, 6, 6, 6)
    v.setSpacing(12)

    for title_text, line_items in _load_help_groups():
        _add_box(v, title_text, line_items)

    v.addStretch(1)
    return wrap
