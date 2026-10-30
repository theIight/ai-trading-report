# AI Trading - Multi-Agent System (TradingAgents & Antigravity Native)

Dự án phân tích thị trường tài chính bằng hệ thống Đa Tác tử AI (Multi-Agent System), mô phỏng một quỹ đầu tư với đầy đủ các phòng ban:
- **Phòng kỹ thuật (Market Analyst):** Phân tích dữ liệu nến, RSI, MACD, Bollinger Bands, ATR, Moving Averages.
- **Phòng tin tức & tâm lý (Sentiment & News):** Đánh giá tâm lý thị trường, chỉ số sợ hãi/tham lam và tin tức ngành.
- **Phòng tài chính (Fundamentals):** Định giá P/E, vốn hóa, báo cáo tài chính (áp dụng cho cổ phiếu).
- **Tranh luận phe Mua vs phe Bán (Bull vs Bear Debate):** Hai Agent tranh luận đa chiều bảo vệ quan điểm.
- **Hội đồng quản trị rủi ro (Risk Committee):** Đánh giá rủi ro từ góc nhìn Liều, Thận trọng, Trung lập; đề xuất Stop-loss/Take-profit.
- **Giám đốc điều hành (Portfolio Manager):** Tổng hợp và đưa ra phán quyết đầu tư cuối cùng (BUY / SELL / HOLD) kèm xếp hạng khuyến nghị tín nhiệm.

---

## 🌟 Chế độ 1: Antigravity Native (KHUYÊN DÙNG - KHÔNG CẦN API KEY)

Sử dụng trực tiếp phiên làm việc **Antigravity CLI** đã đăng nhập trên máy của bạn (sử dụng model **Gemini 3.8 Flash** hoặc **Gemini 4 Argon**), hoàn toàn không cần thẻ tín dụng hay tạo khóa API Google AI Studio:

```bash
cd /Users/nexusfrontiertech/projects/self/ai-trading
./run_antigravity.sh
```

Hoặc truyền tham số cụ thể:
```bash
./run_antigravity.sh --ma BTC-USD --ngay 2026-10-25
./run_antigravity.sh --ma GC=F --ngay 2026-10-25    # Vàng thế giới
./run_antigravity.sh --ma NVDA --ngay 2026-10-25    # Cổ phiếu Nvidia
```

---

## 🔑 Chế độ 2: Dùng Google Gemini API Key riêng (TradingAgents gốc)

Nếu bạn có riêng Google Gemini API Key (`AIza...`) từ Google AI Studio:

```bash
cd /Users/nexusfrontiertech/projects/self/ai-trading
./run.sh
```

---

## 🐳 Chế độ 3: Chạy qua Docker

Nếu muốn chạy đóng gói trong container Docker:
```bash
cd /Users/nexusfrontiertech/projects/self/ai-trading
./docker-run.sh
```

---

## ⚡ Chế độ 4: Chạy Đám Mây tự động qua GitHub Actions

Bạn có thể uỷ quyền toàn bộ việc chạy phân tích và gen file báo cáo lên GitHub Actions:
1. Đẩy mã nguồn lên GitHub repository của bạn.
2. Cấu hình Secret `GEMINI_API_KEY` trong **Settings -> Secrets and variables -> Actions**.
3. Vào tab **Actions** -> Chọn workflow **AI Trading - Multi-Agent Analysis** -> Nhấn **Run workflow**, nhập mã tài sản (VD: `BTC-USD`) và ngày cần phân tích.
4. GitHub Actions sẽ tự động:
   - Chạy phân tích đa tác tử trên Ubuntu Runner.
   - Xuất file báo cáo Markdown & HTML.
   - Commit & Push file mới vào branch `main` (đồng thời lưu Artifact tải về).
5. Trên máy local, bạn chỉ cần gõ `git pull` là file báo cáo xuất hiện ngay trên `localhost:5050`!

---

## 📊 Giao diện Web Điều Hành & Báo Cáo (`http://localhost:5050`)
- **Giao diện sáng (Light Theme) mặc định:** Thiết kế chuẩn Financial Dashboard hiện đại, hỗ trợ nút bấm chuyển đổi Sáng / Tối linh hoạt.
- **Khởi chạy phân tích trực tiếp trên Web:** Chọn mã tài sản (BTC-USD, GC=F, NVDA, AAPL...), ngày thẩm định và nhấn **"Bắt Đầu Phân Tích"** để hệ thống gọi `run_antigravity.sh` chạy ngầm hoàn toàn tự động mà không cần gõ lệnh terminal.
- **Tiến độ trực tiếp:** Theo dõi thời gian thực từng bước AI đang làm việc cùng bảng log hiển thị trực tiếp.
- **Báo cáo HTML:** Tự động xuất file HTML và xem qua liên kết:
  ```
  http://localhost:5050/Biên bản <Mã> <Ngày>.html
  ```
- **Quản lý báo cáo:** Tìm kiếm, lọc theo mã tài sản, tải Markdown, hoặc xoá báo cáo với nút **`🗑️ Xoá`**.
- **Khởi động server:**
  ```bash
  ./serve.sh                 # Mở Dashboard trên trình duyệt
  python server.py --status  # Kiểm tra trạng thái server
  python server.py --stop    # Dừng máy chủ nền
  ```
