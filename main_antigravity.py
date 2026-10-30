#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
AI Trading Multi-Agent System - Phiên bản Antigravity Native
Sử dụng trực tiếp phiên Antigravity đã đăng nhập (KHÔNG CẦN GEMINI API KEY).
"""

import argparse
import html
import json
import os
import shutil
import subprocess
import sys
import time
import urllib.parse
import webbrowser
from datetime import datetime, timedelta
from pathlib import Path
import yfinance as yf
from stockstats import wrap

GOC = Path(__file__).resolve().parent
KQ = GOC / "Kết quả"
KQ.mkdir(exist_ok=True)

TEN_BUOC = {
    "khoi_dong": "Khởi động & Thu thập dữ liệu nến/chỉ báo",
    "market": "Phòng kỹ thuật (nến, xu hướng, RSI, MACD)",
    "news": "Phòng tin tức & tâm lý thị trường",
    "fundamentals": "Phòng tài chính (định giá & cơ bản)",
    "debate": "Phe Mua và Phe Bán tranh luận (Bull vs Bear)",
    "risk": "Hội đồng quản trị rủi ro (Liều, Thận trọng, Trung lập)",
    "portfolio": "Giám đốc điều hành ra phán quyết cuối cùng",
    "hoan_thanh": "HOÀN THÀNH - Đã xuất biên bản báo cáo",
}


def ten_sach(ma: str) -> str:
    return "".join(ch if ch.isalnum() or ch in "-_." else "_" for ch in ma)


class TheoDoi:
    def __init__(self, thu_muc: Path, ma: str, ngay: str, model: str):
        self.thu_muc, self.ma, self.ngay, self.model = thu_muc, ma, ngay, model
        self.bat_dau = time.time()
        self.buoc = TEN_BUOC["khoi_dong"]
        self.so_luot_ai = 0
        self.ket_qua = ""
        self.ghi()

    def cap_nhat(self, key_buoc: str):
        self.buoc = TEN_BUOC.get(key_buoc, key_buoc)
        self.ghi()

    def ghi(self):
        phut = (time.time() - self.bat_dau) / 60
        trang = f"""<!doctype html><html lang="vi" data-theme="light"><head><meta charset="utf-8"><meta http-equiv="refresh" content="10">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>Tiến độ AI Trading ({html.escape(self.ma)})</title>
<style>
:root {{
  --bg-primary: #f8fafc;
  --bg-card: #ffffff;
  --border-color: #e2e8f0;
  --text-primary: #0f172a;
  --text-muted: #64748b;
  --accent-gold: #d97706;
  --accent-blue: #0284c7;
  --accent-green: #059669;
  --badge-bg: #f1f5f9;
}}
[data-theme="dark"] {{
  --bg-primary: #0f1117;
  --bg-card: #1a1d26;
  --border-color: #282c37;
  --text-primary: #e1e4ea;
  --text-muted: #8b949e;
  --accent-gold: #f3ba2f;
  --accent-blue: #61afef;
  --accent-green: #98c379;
  --badge-bg: #2d3342;
}}
body{{background:var(--bg-primary);color:var(--text-primary);font:16px -apple-system,BlinkMacSystemFont,Segoe UI,Roboto,sans-serif;padding:24px 20px;max-width:760px;margin:auto;line-height:1.6}}
h1{{color:var(--accent-gold);font-size:24px;margin-bottom:12px;display:flex;align-items:center;gap:8px}}
.o{{background:var(--bg-card);border:1px solid var(--border-color);border-radius:12px;padding:18px 22px;margin:14px 0;box-shadow:0 2px 8px rgba(0,0,0,0.04)}}
b{{color:var(--text-primary)}}.v{{color:var(--accent-blue);font-weight:700}}.success{{color:var(--accent-green);font-weight:700}}
small{{color:var(--text-muted);display:block;margin-top:6px}}
.badge{{background:var(--badge-bg);padding:3px 9px;border-radius:6px;font-size:13px;color:var(--text-muted);font-weight:600}}
.top-bar{{display:flex;justify-content:space-between;align-items:center;margin-bottom:10px}}
.btn{{display:inline-flex;padding:5px 12px;border-radius:6px;font-size:12px;border:1px solid var(--border-color);background:var(--bg-card);color:var(--text-primary);cursor:pointer;text-decoration:none}}
</style></head><body>
<div class="top-bar">
  <a href="/" class="btn">🏠 Về Trang Chủ</a>
  <button class="btn" onclick="toggleTheme()">🌓 Giao diện</button>
</div>
<h1>🚀 Tiến độ AI Trading · Antigravity Native</h1>
<div class="o">
  Mã: <b>{html.escape(self.ma)}</b> · Ngày phân tích: <b>{self.ngay}</b><br>
  Bộ não AI: <span class="badge">{html.escape(self.model)} (Antigravity CLI Session)</span>
</div>
<div class="o">
  Bước hiện tại: <b class="v">{html.escape(self.buoc)}</b><br>
  Số lượt gọi AI Agent: <b>{self.so_luot_ai}</b> · Đã chạy: <b>{phut:.1f} phút</b><br>
  <small>Trang tự làm mới mỗi 10 giây. Bạn có thể theo dõi trực tiếp tại đây.</small>
</div>
{f'<div class="o">Phán quyết cuối cùng: <b class="success">{html.escape(self.ket_qua)}</b><br>Biên bản phân tích đã được hoàn thành.</div>' if self.ket_qua else ''}
<script>
function toggleTheme() {{
  const cur = document.documentElement.getAttribute('data-theme') || 'light';
  const target = cur === 'dark' ? 'light' : 'dark';
  document.documentElement.setAttribute('data-theme', target);
  localStorage.setItem('ai_trading_theme', target);
}}
(function() {{
  const saved = localStorage.getItem('ai_trading_theme') || 'light';
  document.documentElement.setAttribute('data-theme', saved);
}})();
</script>
</body></html>"""
        (self.thu_muc / "Tiến độ.html").write_text(trang, encoding="utf-8")


def goi_antigravity_llm(prompt: str, model: str = "gemini-3.8-flash-high", max_retries: int = 3) -> str:
    """Gọi LLM thông qua phiên Antigravity CLI (agy -p) đã đăng nhập."""
    cmd = [
        "agy",
        "-p", prompt,
        "--model", model,
        "--output-format", "json",
    ]
    for attempt in range(max_retries):
        try:
            res = subprocess.run(cmd, capture_output=True, text=True, check=True)
            data = json.loads(res.stdout)
            return data.get("response", "").strip()
        except subprocess.CalledProcessError as e:
            if attempt == max_retries - 1:
                raise RuntimeError(f"Lỗi khi gọi Antigravity CLI: {e.stderr or e.stdout}")
            time.sleep(2)
        except Exception as e:
            if attempt == max_retries - 1:
                raise e
            time.sleep(2)
    return ""


def lay_du_lieu_thi_truong(ma: str, ngay: str):
    """Lấy dữ liệu OHLCV và tính toán các chỉ báo kỹ thuật qua yfinance + stockstats."""
    target_dt = datetime.strptime(ngay, "%Y-%m-%d")
    start_dt = target_dt - timedelta(days=220)  # Lấy dư dữ liệu để tính SMA 200

    ticker = yf.Ticker(ma)
    df = ticker.history(
        start=start_dt.strftime("%Y-%m-%d"),
        end=(target_dt + timedelta(days=1)).strftime("%Y-%m-%d")
    )

    if df.empty:
        raise ValueError(f"Không tìm thấy dữ liệu giá cho mã '{ma}' trên Yahoo Finance đến ngày {ngay}.")

    sdf = wrap(df)

    latest = sdf.iloc[-1]
    prev = sdf.iloc[-2] if len(sdf) > 1 else latest

    # Tính toán các chỉ báo
    close_price = float(latest["close"])
    open_price = float(latest["open"])
    high_price = float(latest["high"])
    low_price = float(latest["low"])
    volume = float(latest["volume"])

    change_pct = ((close_price - float(prev["close"])) / float(prev["close"])) * 100 if float(prev["close"]) != 0 else 0

    rsi = float(sdf["rsi"].iloc[-1])
    macd = float(sdf["macd"].iloc[-1])
    macd_signal = float(sdf["macds"].iloc[-1])
    macd_hist = float(sdf["macdh"].iloc[-1])

    sma_10 = float(sdf["close_10_sma"].iloc[-1])
    sma_50 = float(sdf["close_50_sma"].iloc[-1])
    sma_200 = float(sdf["close_200_sma"].iloc[-1]) if len(sdf) >= 200 else None

    boll_ub = float(sdf["boll_ub"].iloc[-1])
    boll_mid = float(sdf["boll"].iloc[-1])
    boll_lb = float(sdf["boll_lb"].iloc[-1])
    atr = float(sdf["atr"].iloc[-1])

    bang_chi_bao = f"""### Dữ liệu thị trường & Chỉ báo kỹ thuật ({ma} tại ngày {ngay}):
- **Giá đóng cửa (Close):** {close_price:,.2f} USD (Biến động ngày: {change_pct:+.2f}%)
- **Biên độ trong ngày:** Thấp nhất = {low_price:,.2f} USD | Cao nhất = {high_price:,.2f} USD
- **Khối lượng giao dịch (Volume):** {volume:,.0f}
- **RSI (14 ngày):** {rsi:.2f} ({'Quá mua (Overbought)' if rsi >= 70 else 'Quá bán (Oversold)' if rsi <= 30 else 'Trung tính'})
- **MACD:** {macd:.2f} | **Signal Line:** {macd_signal:.2f} | **Histogram:** {macd_hist:+.2f} ({'Cắt lên (Bullish Cross)' if macd_hist > 0 else 'Cắt xuống (Bearish Cross)'})
- **Đường trung bình (SMA):**
  - SMA 10 (Ngắn hạn): {sma_10:,.2f} USD ({'Trên SMA 10' if close_price > sma_10 else 'Dưới SMA 10'})
  - SMA 50 (Trung hạn): {sma_50:,.2f} USD ({'Trên SMA 50' if close_price > sma_50 else 'Dưới SMA 50'})
  - SMA 200 (Dài hạn): {f"{sma_200:,.2f} USD" if sma_200 else "Chưa đủ 200 phiên"}
- **Dải Bollinger Bands:**
  - Dải trên (Upper Band): {boll_ub:,.2f} USD
  - Dải giữa (Middle Band): {boll_mid:,.2f} USD
  - Dải dưới (Lower Band): {boll_lb:,.2f} USD
- **Độ biến động ATR (14):** {atr:,.2f} USD
"""
    return bang_chi_bao, ticker, close_price


def lay_thong_tin_co_ban(ticker, ma: str):
    """Lấy thông tin cơ bản và tin tức."""
    info_text = ""
    try:
        info = ticker.info or {}
        news = ticker.news or []
        
        pe = info.get("trailingPE")
        mcap = info.get("marketCap")
        target_high = info.get("targetHighPrice")
        target_low = info.get("targetLowPrice")
        recommendation = info.get("recommendationKey", "N/A")

        info_text += f"\n### Thông tin cơ bản & Định giá ({ma}):\n"
        if mcap:
            info_text += f"- Vốn hóa thị trường (Market Cap): {mcap:,.0f} USD\n"
        if pe:
            info_text += f"- P/E Trailing: {pe:.2f}\n"
        if target_high and target_low:
            info_text += f"- Định giá mục tiêu của các chuyên gia: {target_low} - {target_high} USD\n"
        info_text += f"- Đồng thuận của các quỹ: {recommendation.upper()}\n"

        if news:
            info_text += "\n### Tiêu đề tin tức gần đây:\n"
            for n in news[:5]:
                tieu_de = n.get("title", "")
                publisher = n.get("publisher", "")
                if tieu_de:
                    info_text += f"- [{publisher}] {tieu_de}\n"
    except Exception:
        pass
    return info_text


def chay_phan_tich_multi_agent(ma: str, ngay: str, model: str, td: TheoDoi):
    """Điều phối toàn bộ quy trình hội đồng chuyên gia Đa Tác tử AI."""
    # Bước 1: Thu thập dữ liệu
    td.cap_nhat("khoi_dong")
    bang_chi_bao, ticker, close_price = lay_du_lieu_thi_truong(ma, ngay)
    info_text = lay_thong_tin_co_ban(ticker, ma)
    is_crypto = ma.endswith("-USD")
    is_gold = ma.endswith("=F")

    # Bước 2: Phòng kỹ thuật (Market Analyst)
    td.cap_nhat("market")
    p_market = f"""Bạn là Trưởng phòng Phân tích Kỹ thuật (Senior Market Technician).
Dựa trên dữ liệu kỹ thuật thực tế sau đây của mã {ma} vào ngày {ngay}:
{bang_chi_bao}

Hãy viết báo cáo phân tích kỹ thuật chuyên sâu bằng tiếng Việt:
1. Đánh giá xu hướng hiện tại (Ngắn hạn, Trung hạn, Dài hạn) dựa trên cấu trúc nến và các đường SMA/EMA.
2. Đọc vị xung lượng và động lượng qua RSI, MACD Histogram và Volume.
3. Đánh giá độ nén biến động qua Bollinger Bands và ATR.
4. Xác định các ngưỡng Hỗ trợ (Support) và Kháng cự (Resistance) quan trọng nhất quanh mức giá hiện tại {close_price:,.2f} USD.
5. Tổng kết nhận định kỹ thuật ngắn gọn.
Trình bày rõ ràng, dùng bullet points và bảng tóm tắt nếu cần."""
    market_report = goi_antigravity_llm(p_market, model=model)
    td.so_luot_ai += 1
    td.ghi()

    # Bước 3: Phòng Tin tức & Tâm lý (News & Sentiment Analyst)
    td.cap_nhat("news")
    p_news = f"""Bạn là Chuyên viên Phân tích Tin tức và Tâm lý Thị trường (Sentiment & News Analyst).
Mã tài sản: {ma} - Ngày phân tích: {ngay}.
Thông tin thu thập:
{info_text if info_text else 'Thị trường biến động theo dòng tiền vĩ mô và chỉ số DXY / Lãi suất FED.'}

Hãy viết báo cáo đánh giá tâm lý thị trường bằng tiếng Việt:
1. Tâm lý chung của đám đông hiện tại (Tham lam, Sợ hãi, hay Do dự?).
2. Các sự kiện vĩ mô hoặc tin tức ngành đang tác động trực tiếp tới {ma}.
3. Dòng tiền lớn (Whale / Smart Money) đang có xu hướng gom hàng, phân phối hay đứng ngoài?
4. Đánh giá rủi ro thiên nga đen hoặc tin tức bất ngờ có thể xảy ra."""
    news_report = goi_antigravity_llm(p_news, model=model)
    td.so_luot_ai += 1
    td.ghi()

    # Bước 4: Phòng Tài chính (nếu là cổ phiếu)
    fundamentals_report = ""
    if not is_crypto and not is_gold:
        td.cap_nhat("fundamentals")
        p_fund = f"""Bạn là Chuyên gia Định giá & Phân tích Cơ bản (Fundamentals Analyst).
Mã cổ phiếu: {ma} - Ngày: {ngay}.
Dữ liệu cơ bản:
{info_text}

Hãy đánh giá tình hình tài chính của doanh nghiệp bằng tiếng Việt:
1. Mức định giá hiện tại (P/E, P/B, Vốn hóa) là đắt hay rẻ so với tiềm năng tăng trưởng?
2. Sức khỏe tài chính, lợi thế cạnh tranh cốt lõi (Moat) và triển vọng kinh doanh.
3. Nhận định đầu tư giá trị dài hạn."""
        fundamentals_report = goi_antigravity_llm(p_fund, model=model)
        td.so_luot_ai += 1
        td.ghi()

    # Bước 5: Phe Mua vs Phe Bán tranh luận (Bull vs Bear Debate)
    td.cap_nhat("debate")
    p_debate = f"""Bạn đóng vai một cuộc tranh luận kịch tính và sâu sắc giữa hai phe:
- **Phe Mua (Bull Researcher):** Tìm mọi lý do xác đáng ủng hộ giá sẽ TĂNG mạnh.
- **Phe Bán (Bear Researcher):** Chỉ ra mọi cạm bẫy, rủi ro khiến giá có nguy cơ SẬP hoặc điều chỉnh sâu.

Mã tài sản: {ma} - Giá hiện tại: {close_price:,.2f} USD.
Tóm tắt kỹ thuật:
{market_report[:1500]}

Tóm tắt tin tức & tâm lý:
{news_report[:1000]}

Hãy tường thuật lại cuộc tranh biện giữa 2 bên bằng tiếng Việt với các luận điểm sắc bén nhất. Mỗi bên đưa ra 3 luận điểm cốt lõi nhất để bảo vệ quan điểm của mình."""
    debate_report = goi_antigravity_llm(p_debate, model=model)
    td.so_luot_ai += 1
    td.ghi()

    # Bước 6: Hội đồng Quản lý Rủi ro (Risk Debate)
    td.cap_nhat("risk")
    p_risk = f"""Bạn là Hội đồng Quản trị Rủi ro của Quỹ Đầu tư, gồm 3 chuyên gia:
1. **Chuyên viên Liều (Aggressive Risk Officer):** Chấp nhận biên độ biến động lớn để tìm kiếm lợi nhuận tối đa.
2. **Chuyên viên Thận trọng (Conservative Risk Officer):** Ưu tiên bảo vệ vốn tuyệt đối, không vào lệnh nếu không có xác suất thắng cao.
3. **Chuyên viên Trung lập (Neutral Risk Officer):** Cân bằng giữa lợi nhuận và rủi ro, kiểm soát tỷ lệ R:R (Risk/Reward).

Mã: {ma} - Giá hiện tại: {close_price:,.2f} USD.
Xem xét luận điểm của Phe Mua và Phe Bán:
{debate_report[:1500]}

Hãy đưa ra đánh giá rủi ro bằng tiếng Việt:
- Mỗi chuyên viên đưa ra nhận định và khuyến nghị của mình.
- Đề xuất cụ thể mức: Stop Loss (Cắt lỗ), Take Profit (Chốt lời mục tiêu) và tỷ lệ Risk:Reward khuyến nghị."""
    risk_report = goi_antigravity_llm(p_risk, model=model)
    td.so_luot_ai += 1
    td.ghi()

    # Bước 7: Giám đốc Quỹ (Portfolio Manager) ra quyết định cuối cùng & Xếp hạng
    td.cap_nhat("portfolio")
    p_portfolio = f"""Bạn là Giám đốc Quỹ Đầu tư (Chief Investment Officer / Portfolio Manager).
Nhiệm vụ của bạn là tổng hợp toàn bộ báo cáo từ các phòng ban dưới quyền để đưa ra **PHÁN QUYẾT CUỐI CÙNG** về mã {ma} tại ngày {ngay}.

Dữ liệu giá hiện tại: {close_price:,.2f} USD.
Báo cáo kỹ thuật: {market_report[:1000]}
Báo cáo rủi ro & tranh biện: {risk_report[:1200]}

Hãy ra quyết định dứt khoát bằng tiếng Việt theo định dạng sau:
1. **QUYẾT ĐỊNH HÀNH ĐỘNG:** [Chọn rõ 1 trong 3: MUA (BUY) / BÁN (SELL) / ĐỨNG NGOÀI QUAN SÁT (HOLD)]
2. **XẾP HẠNG KHUYẾN NGHỊ:** [Chọn rõ: RẤT TÍCH CỰC (5/5 sao) | TÍCH CỰC (4/5 sao) | TRUNG LẬP (3/5 sao) | TIÊU CỰC (2/5 sao) | RẤT TIÊU CỰC (1/5 sao)]
3. **KẾ HOẠCH GIAO DỊCH CỤ THỂ:**
   - Vùng giá mua/bán khuyến nghị (Entry Zone):
   - Mức cắt lỗ tuyệt đối (Stop Loss):
   - Mục tiêu giá 1 (TP1) & Mục tiêu giá 2 (TP2):
   - Tỷ lệ phân bổ vốn khuyến nghị: (VD: 5%, 10% danh mục)
4. **3 LÝ DO CỐT LÕI CỦA PHÁN QUYẾT:** (Ngắn gọn, súc tích)"""
    final_decision = goi_antigravity_llm(p_portfolio, model=model)
    td.so_luot_ai += 1
    td.ghi()

    # Trích xuất rating từ phán quyết
    rating = "TRUNG LẬP (3/5)"
    for line in final_decision.splitlines():
        if "XẾP HẠNG" in line.upper():
            rating = line.split(":", 1)[-1].strip().strip("[]*")
            break

    return {
        "bang_chi_bao": bang_chi_bao,
        "market_report": market_report,
        "news_report": news_report,
        "fundamentals_report": fundamentals_report,
        "debate_report": debate_report,
        "risk_report": risk_report,
        "final_decision": final_decision,
        "rating": rating,
        "close_price": close_price,
    }


def ghi_bien_ban_antigravity(thu_muc: Path, ma: str, ngay: str, res: dict, model: str, phut: float) -> Path:
    noi_dung = [
        f"# BIÊN BẢN PHÂN TÍCH ĐA TÁC TỬ: {ma}",
        "",
        f"- **Ngày phân tích:** {ngay}",
        f"- **Bộ não AI:** `{model}` (Antigravity Native Session - Không tốn API key)",
        f"- **Xếp hạng khuyến nghị:** **{res['rating']}**",
        f"- **Thời gian chạy:** {phut:.1f} phút",
        "",
        "> [!IMPORTANT]",
        "> Biên bản do hệ sinh thái Antigravity Multi-Agent tổng hợp dựa trên dữ liệu giá thực tế từ Yahoo Finance. Báo cáo chỉ nhằm mục đích nghiên cứu học tập, **KHÔNG PHẢI LỜI KHUYÊN ĐẦU TƯ TÀI CHÍNH**.",
        "",
        "---",
        "",
        "## 🏆 1. PHÁN QUYẾT CUỐI CÙNG CỦA GIÁM ĐỐC QUỸ",
        "",
        res["final_decision"],
        "",
        "---",
        "",
        "## 📊 2. BÁO CÁO PHÒNG KỸ THUẬT (MARKET TECHNICIAN)",
        "",
        res["bang_chi_bao"],
        "",
        res["market_report"],
        "",
        "---",
        "",
        "## 📰 3. BÁO CÁO PHÒNG TIN TỨC & TÂM LÝ (SENTIMENT & NEWS)",
        "",
        res["news_report"],
        "",
    ]

    if res.get("fundamentals_report"):
        noi_dung += [
            "---",
            "",
            "## 🏢 4. BÁO CÁO PHÒNG PHÂN TÍCH CƠ BẢN (FUNDAMENTALS)",
            "",
            res["fundamentals_report"],
            "",
        ]

    noi_dung += [
        "---",
        "",
        "## ⚔️ 5. TRANH BIỆN PHE MUA VS PHE BÁN (BULL VS BEAR DEBATE)",
        "",
        res["debate_report"],
        "",
        "---",
        "",
        "## 🛡️ 6. HỘI ĐỒNG QUẢN LÝ RỦI RO (RISK COMMITTEE)",
        "",
        res["risk_report"],
        "",
    ]

    tep_md = thu_muc / f"Biên bản {ten_sach(ma)} {ngay}.md"
    tep_md.write_text("\n".join(noi_dung), encoding="utf-8")

    # Tạo thêm file Báo cáo HTML trực quan
    tep_html = thu_muc / f"Biên bản {ten_sach(ma)} {ngay}.html"
    try:
        from report_generator import tao_trang_bao_cao_html
        html_str = tao_trang_bao_cao_html(
            md_content="\n".join(noi_dung),
            ma=ma,
            ngay=ngay,
            rating=res.get("rating"),
            model=model,
            phut=phut,
        )
        tep_html.write_text(html_str, encoding="utf-8")
    except Exception:
        pass

    return tep_md, tep_html


def mo_tep(duong_dan: Path):
    try:
        if sys.platform == "darwin":
            subprocess.Popen(["open", str(duong_dan)])
        elif sys.platform.startswith("linux"):
            if shutil.which("xdg-open"):
                subprocess.Popen(["xdg-open", str(duong_dan)])
    except Exception:
        pass


def main():
    parser = argparse.ArgumentParser(description="AI Trading Multi-Agent qua phiên Antigravity")
    parser.add_argument("--ma", "-m", help="Mã tài sản (VD: BTC-USD, GC=F, NVDA, AAPL)")
    parser.add_argument("--ngay", "-d", help="Ngày phân tích YYYY-MM-DD")
    parser.add_argument("--model", default="gemini-3.8-flash-high", help="Model Antigravity (mặc định: gemini-3.8-flash-high)")
    parser.add_argument("--headless", action="store_true", help="Không tự động mở trình duyệt hoặc file viewer")
    args = parser.parse_args()

    # Kiểm tra agy binary
    if not shutil.which("agy"):
        print("LỖI: Không tìm thấy công cụ 'agy' trong PATH hệ thống.")
        sys.exit(1)

    ma = args.ma
    if not ma:
        print("\n" + "=" * 55)
        print("    AI TRADING MULTI-AGENT (ANTIGRAVITY NATIVE)")
        print("    Không cần API Key · Chạy trực tiếp qua Antigravity")
        print("=" * 55)
        print(" CHỌN MÃ TÀI SẢN MUỐN PHÂN TÍCH:")
        print("   1 = Bitcoin (BTC-USD)")
        print("   2 = Vàng thế giới (GC=F)")
        print("   Hoặc nhập mã khác (VD: ETH-USD, SOL-USD, AAPL, NVDA, TSLA)")
        print("-" * 55)
        chon = input(" Nhập lựa chọn [Mặc định 1]: ").strip()
        if chon == "" or chon == "1":
            ma = "BTC-USD"
        elif chon == "2":
            ma = "GC=F"
        else:
            ma = chon

    ma = ma.strip().upper()

    ngay = args.ngay
    hom_qua = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")
    if not ngay:
        chon_ngay = input(f" Nhập ngày phân tích YYYY-MM-DD [Mặc định: {hom_qua}]: ").strip()
        ngay = chon_ngay if chon_ngay else hom_qua

    try:
        datetime.strptime(ngay, "%Y-%m-%d")
    except ValueError:
        print(f"Lỗi: Ngày '{ngay}' sai định dạng YYYY-MM-DD.")
        sys.exit(2)

    thu_muc = KQ / ten_sach(ma)
    thu_muc.mkdir(exist_ok=True)

    print("\n" + "=" * 55)
    print(f" Đang khởi tạo phiên phân tích: Mã {ma} - Ngày {ngay}")
    print(f" Bộ não: {args.model} (Antigravity CLI Session)")
    print("=" * 55)

    td = TheoDoi(thu_muc, ma, ngay, args.model)

    # Khởi động sẵn máy chủ báo cáo nội bộ
    port = 5050
    try:
        from server import dam_bao_server_chay
        port = dam_bao_server_chay(5050)
    except Exception:
        pass

    if not args.headless:
        try:
            url_tiendo = f"http://localhost:{port}/{urllib.parse.quote(ten_sach(ma))}/Tiến độ.html"
            webbrowser.open(url_tiendo)
        except Exception:
            mo_tep(thu_muc / "Tiến độ.html")

    t0 = time.time()
    try:
        res = chay_phan_tich_multi_agent(ma, ngay, args.model, td)
        loi = None
    except Exception as e:
        res = {}
        loi = "".join(traceback.format_exception(e)) if "traceback" in globals() else str(e)

    phut = (time.time() - t0) / 60

    if loi:
        td.buoc = "LỖI KHI XỬ LÝ"
        td.ghi()
        print(f"\n Có lỗi xảy ra: {loi}")
        sys.exit(3)

    tep_md, tep_html = ghi_bien_ban_antigravity(thu_muc, ma, ngay, res, args.model, phut)
    td.buoc = "HOÀN THÀNH"
    td.ket_qua = res["rating"]
    td.ghi()

    # Ghi log jsonl
    with (thu_muc / "ket_qua.jsonl").open("a", encoding="utf-8") as f:
        f.write(json.dumps({
            "ma": ma,
            "ngay": ngay,
            "rating": res["rating"],
            "model": args.model,
            "phut": round(phut, 2),
            "so_luot_ai": td.so_luot_ai,
        }, ensure_ascii=False) + "\n")

    link_bao_cao = f"http://localhost:{port}/{urllib.parse.quote(tep_html.name)}"
    link_dashboard = f"http://localhost:{port}/"

    print("\n" + "=" * 60)
    print(f" 🚀 HOÀN TẤT PHÂN TÍCH: {ma} ({ngay})")
    print(f" 🎯 Xếp hạng: {res['rating']}")
    print(f" ⏱️ Thời gian thực hiện: {phut:.1f} phút (Số lượt AI: {td.so_luot_ai})")
    print(f" 📄 File Markdown: {tep_md}")
    print(f" 🌐 File HTML:     {tep_html}")
    print("-" * 60)
    print(f" 🔗 LINK BÁO CÁO: {link_bao_cao}")
    print(f" 🏠 DASHBOARD:    {link_dashboard}")
    print("=" * 60)

    if not args.headless:
        try:
            from server import mo_link_bao_cao
            mo_link_bao_cao(tep_html, port=port)
        except Exception:
            mo_tep(tep_html)


if __name__ == "__main__":
    main()
