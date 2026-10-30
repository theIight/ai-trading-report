#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
AI Trading Multi-Agent System (TradingAgents v0.5.2)
Chạy phân tích đa tác tử tài chính sử dụng Google Gemini.
Hỗ trợ đa nền tảng: macOS, Linux, Windows, Docker.
"""

import argparse
import html
import json
import os
import shutil
import subprocess
import sys
import time
import traceback
import urllib.parse
import webbrowser
from datetime import datetime, timedelta
from pathlib import Path

# --- Khắc phục lỗi SSL khi đường dẫn có dấu hoặc ký tự đặc biệt ---
try:
    import certifi
    if sys.platform == "win32":
        public_dir = Path(os.environ.get("PUBLIC", r"C:\Users\Public")) / "TradingAgents-cert"
        if all(ord(c) < 128 for c in str(public_dir)):
            dest_cert = public_dir / "cacert.pem"
            dest_cert.parent.mkdir(parents=True, exist_ok=True)
            if not dest_cert.exists() or dest_cert.stat().st_size != Path(certifi.where()).stat().st_size:
                shutil.copyfile(certifi.where(), dest_cert)
            certifi.where = lambda: str(dest_cert)
            for key in ("CURL_CA_BUNDLE", "SSL_CERT_FILE", "REQUESTS_CA_BUNDLE"):
                os.environ[key] = str(dest_cert)
except Exception as e:
    pass
# ------------------------------------------------------------------

GOC = Path(__file__).resolve().parent
KQ = GOC / "Kết quả"
KQ.mkdir(exist_ok=True)

# Nạp khóa Gemini từ biến môi trường, file .env hoặc khoa-gemini.txt
def lay_khoa_gemini():
    # 1. Biến môi trường hiện tại
    if os.environ.get("GOOGLE_API_KEY"):
        return os.environ["GOOGLE_API_KEY"].strip()

    # 2. File .env
    env_file = GOC / ".env"
    if env_file.exists():
        for line in env_file.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line.startswith("GOOGLE_API_KEY="):
                key = line.split("=", 1)[1].strip().strip('"').strip("'")
                if key:
                    os.environ["GOOGLE_API_KEY"] = key
                    return key

    # 3. File khoa-gemini.txt
    khoa_file = GOC / "khoa-gemini.txt"
    if khoa_file.exists():
        key = khoa_file.read_text(encoding="utf-8-sig").strip()
        if key:
            os.environ["GOOGLE_API_KEY"] = key
            return key

    return ""


os.environ.setdefault("PYTHONUTF8", "1")
os.environ.setdefault("TRADINGAGENTS_LLM_MAX_RETRIES", "10")

TEN_BUOC = {
    "Market Analyst": "Phòng kỹ thuật (nến + chỉ báo)",
    "Social Analyst": "Phòng tâm lý",
    "Sentiment Analyst": "Phòng tâm lý",
    "News Analyst": "Phòng tin tức",
    "Fundamentals Analyst": "Phòng tài chính",
    "Memory Log": "Sổ nhớ chấm lệnh cũ",
    "Bull Researcher": "Phe Mua đang nói",
    "Bear Researcher": "Phe Bán đang nói",
    "Research Manager": "Trưởng phòng chốt kế hoạch",
    "Trader": "Trader ra lệnh",
    "Aggressive Analyst": "Rủi ro: người Liều",
    "Conservative Analyst": "Rủi ro: người Thận trọng",
    "Neutral Analyst": "Rủi ro: người Trung lập",
    "Portfolio Manager": "Quyết định cuối",
}


def ten_sach(ma: str) -> str:
    return "".join(ch if ch.isalnum() or ch in "-_." else "_" for ch in ma)


def cau_hinh(ma: str):
    from tradingagents.default_config import DEFAULT_CONFIG
    c = DEFAULT_CONFIG.copy()
    c["llm_provider"] = "google"
    c["quick_think_llm"] = os.getenv("GEMINI_QUICK", "gemini-3.5-flash-lite")
    c["deep_think_llm"] = os.getenv("GEMINI_DEEP", "gemini-3.8-flash")
    thu_muc = KQ / ten_sach(ma)
    thu_muc.mkdir(exist_ok=True)
    c["results_dir"] = str(thu_muc / "logs")
    c["data_cache_dir"] = str(GOC / "cache")
    c["memory_log_path"] = str(thu_muc / "so_nho.md")
    c["output_language"] = "English"
    return c, thu_muc


class TheoDoi:
    def __init__(self, thu_muc: Path, ma: str, ngay: str):
        self.thu_muc, self.ma, self.ngay = thu_muc, ma, ngay
        self.bat_dau = time.time()
        self.buoc = "Khởi động"
        self.so_luot_ai = 0
        self.ket_qua = ""
        self.ghi()

    def ghi(self):
        phut = (time.time() - self.bat_dau) / 60
        trang = f"""<!doctype html><html lang="vi"><head><meta charset="utf-8"><meta http-equiv="refresh" content="20">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>Tiến độ AI Trading</title>
<style>
body{{background:#111;color:#eee;font:17px system-ui,-apple-system,BlinkMacSystemFont,Segoe UI,Roboto,sans-serif;padding:16px;max-width:720px;margin:auto}}
h1{{color:#e8b84a;font-size:24px;margin-bottom:8px}}
.o{{background:#1d1d24;border-radius:10px;padding:14px 18px;margin:12px 0;line-height:1.7}}
b{{color:#fff}}.v{{color:#9b7bff}}
small{{color:#888}}
</style></head><body>
<h1>Tiến độ AI Trading · Multi-Agent System</h1>
<div class="o">Mã: <b>{html.escape(self.ma)}</b> · Ngày: <b>{self.ngay}</b> · Bộ não: <b>Gemini</b></div>
<div class="o">Bước hiện tại: <b class="v">{html.escape(self.buoc)}</b><br>
Số lượt gọi AI: <b>{self.so_luot_ai}</b> · Đã chạy: <b>{phut:.1f} phút</b><br>
<small>Trang tự làm mới mỗi 20 giây.</small></div>
{f'<div class="o">Kết quả: <b class="v">{html.escape(self.ket_qua)}</b><br>Biên bản đã lưu trong thư mục Kết quả.</div>' if self.ket_qua else ''}
</body></html>"""
        (self.thu_muc / "Tiến độ.html").write_text(trang, encoding="utf-8")


def tao_callback(td: TheoDoi):
    from langchain_core.callbacks import BaseCallbackHandler

    class CB(BaseCallbackHandler):
        def on_chat_model_start(self, serialized, messages, *, run_id=None, metadata=None, **kw):
            try:
                md = metadata or {}
                node = md.get("langgraph_node", "")
                ns = str(md.get("langgraph_checkpoint_ns", "") or "")
                cha = ns.split("|")[0].split(":")[0] if ns else ""
                if node not in TEN_BUOC and cha in TEN_BUOC:
                    node = cha
                td.buoc = TEN_BUOC.get(node, "Phòng phân tích đang làm việc" if node in ("agent", "tools", "wrap_up") else (node or td.buoc))
                td.so_luot_ai += 1
                td.ghi()
            except Exception:
                pass

    return CB()


def ghi_bien_ban(thu_muc: Path, ma: str, ngay: str, state: dict, rating: str, phut: float) -> Path:
    s = state or {}
    phan = [
        ("Quyết định cuối của giám đốc (Final Decision)", s.get("final_trade_decision", "")),
        ("Kế hoạch lệnh của Trader", s.get("trader_investment_plan", "")),
        ("Kế hoạch của trưởng phòng nghiên cứu", s.get("investment_plan", "")),
        ("Phòng kỹ thuật (Market Technicals)", s.get("market_report", "")),
        ("Phòng tâm lý & mạng xã hội (Sentiment)", s.get("sentiment_report", "")),
        ("Phòng tin tức (News Analyst)", s.get("news_report", "")),
        ("Phòng tài chính (Fundamentals)", s.get("fundamentals_report", "")),
        ("Tranh luận phe Mua & phe Bán (Bull vs Bear Debate)", (s.get("investment_debate_state") or {}).get("history", "")),
        ("Vòng quản lý rủi ro (Risk Debate)", (s.get("risk_debate_state") or {}).get("history", "")),
    ]
    noi_dung = [
        f"# Biên bản phân tích {ma} ngày {ngay}",
        "",
        f"Xếp hạng khuyến nghị: **{rating}** · Thời gian chạy: {phut:.1f} phút · Bộ não AI: Gemini",
        "",
        "> [!NOTE]",
        "> Biên bản do hệ thống AI đa tác tử tổng hợp. Chỉ phục vụ học tập và nghiên cứu, KHÔNG phải lời khuyên đầu tư.",
        "",
    ]
    for tieu_de, nd in phan:
        if nd and str(nd).strip():
            noi_dung += [f"## {tieu_de}", "", str(nd).strip(), ""]
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
            rating=str(rating),
            model="Google Gemini (TradingAgents)",
            phut=phut,
        )
        tep_html.write_text(html_str, encoding="utf-8")
    except Exception:
        pass

    return tep_md, tep_html


def mo_tep(duong_dan: Path):
    """Mở file theo ứng dụng mặc định của hệ điều hành."""
    try:
        if sys.platform == "darwin":  # macOS
            subprocess.Popen(["open", str(duong_dan)])
        elif sys.platform.startswith("linux"):  # Linux
            if shutil.which("xdg-open"):
                subprocess.Popen(["xdg-open", str(duong_dan)])
        elif sys.platform == "win32":  # Windows
            subprocess.Popen(["notepad.exe", str(duong_dan)])
    except Exception:
        pass


def kiem_tra_khoa_api(api_key: str) -> bool:
    """Kiểm tra API key với Google AI Studio."""
    import requests
    try:
        res = requests.get(
            f"https://generativelanguage.googleapis.com/v1beta/models?key={api_key}",
            timeout=15
        )
        return res.status_code == 200
    except Exception:
        return True  # Nếu không kết nối được mạng test, để runtime xử lý sau


def main():
    parser = argparse.ArgumentParser(description="Chạy AI Trading Multi-Agent với Google Gemini")
    parser.add_argument("--ma", "-m", help="Mã tài sản (VD: BTC-USD, GC=F, NVDA, AAPL)")
    parser.add_argument("--ngay", "-d", help="Ngày phân tích dạng YYYY-MM-DD")
    parser.add_argument("--api-key", "-k", help="Google Gemini API Key")
    parser.add_argument("--headless", action="store_true", help="Không tự động mở trình duyệt hoặc file viewer")
    args = parser.parse_args()

    # 1. Lấy API Key
    api_key = args.api_key or lay_khoa_gemini()
    if not api_key:
        print("\n" + "=" * 50)
        print(" CHƯA CÓ KHÓA GOOGLE GEMINI API")
        print(" Lấy miễn phí tại: https://aistudio.google.com/apikey")
        print("=" * 50)
        try:
            import getpass
            api_key = getpass.getpass(" Dán khóa Gemini của bạn (ký tự sẽ ẩn) rồi nhấn Enter: ").strip()
        except Exception:
            api_key = input(" Dán khóa Gemini của bạn: ").strip()

        if len(api_key) < 20:
            print(" Khóa không hợp lệ (quá ngắn).")
            sys.exit(1)

        # Lưu lại vào khoa-gemini.txt
        (GOC / "khoa-gemini.txt").write_text(api_key, encoding="utf-8")
        os.environ["GOOGLE_API_KEY"] = api_key
        print(f" Đã lưu khóa (3 ký tự cuối: ...{api_key[-3:]})")

    os.environ["GOOGLE_API_KEY"] = api_key

    # 2. Chọn mã tài sản
    ma = args.ma
    if not ma:
        print("\n" + "=" * 50)
        print(" CHỌN MÃ TÀI SẢN MUỐN PHÂN TÍCH:")
        print("   1 = Bitcoin (BTC-USD)")
        print("   2 = Vàng thế giới (GC=F)")
        print("   Hoặc nhập mã khác (VD: ETH-USD, SOL-USD, AAPL, NVDA, TSLA)")
        print("=" * 50)
        chon = input(" Nhập lựa chọn [Mặc định 1]: ").strip()
        if chon == "" or chon == "1":
            ma = "BTC-USD"
        elif chon == "2":
            ma = "GC=F"
        else:
            ma = chon

    ma = ma.strip().upper()

    # 3. Chọn ngày
    ngay = args.ngay
    hom_qua = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")
    if not ngay:
        chon_ngay = input(f"\n Nhập ngày phân tích YYYY-MM-DD [Mặc định hôm qua: {hom_qua}]: ").strip()
        ngay = chon_ngay if chon_ngay else hom_qua

    try:
        datetime.strptime(ngay, "%Y-%m-%d")
    except ValueError:
        print(f" Lỗi: Ngày '{ngay}' không đúng định dạng YYYY-MM-DD.")
        sys.exit(2)

    print("\n" + "-" * 50)
    print(f" BẮT ĐẦU PHÂN TÍCH: Mã {ma} - Ngày {ngay}")
    print(" Đang khởi tạo các Agent phân tích tài chính...")
    print("-" * 50)

    from tradingagents.graph.trading_graph import TradingAgentsGraph

    c, thu_muc = cau_hinh(ma)
    crypto = ma.endswith("-USD")
    hang_hoa = ma.endswith("=F") or ma.startswith("^")
    phong = ["market", "social", "news"]
    if not crypto and not hang_hoa:
        phong.append("fundamentals")  # Cổ phiếu có thêm phân tích BCTC

    td = TheoDoi(thu_muc, ma, ngay)

    # Khởi động sẵn máy chủ báo cáo nội bộ
    port = 5050
    try:
        from server import dam_bao_server_chay
        port = dam_bao_server_chay(5050)
    except Exception:
        pass

    # Mở trang HTML tiến độ nếu không chạy headless
    if not args.headless:
        try:
            url_tiendo = f"http://localhost:{port}/{urllib.parse.quote(ten_sach(ma))}/Tiến độ.html"
            webbrowser.open(url_tiendo)
        except Exception:
            try:
                webbrowser.open((thu_muc / "Tiến độ.html").as_uri())
            except Exception:
                pass

    ta = TradingAgentsGraph(selected_analysts=phong, debug=False, config=c, callbacks=[tao_callback(td)])
    t0 = time.time()
    try:
        state, rating = ta.propagate(ma, ngay, asset_type="crypto" if crypto else "stock")
        loi = None
    except Exception as e:
        state, rating, loi = {}, "LOI", "".join(traceback.format_exception(e))[-3000:]

    phut = (time.time() - t0) / 60

    # Lưu lịch sử log JSONL
    with (thu_muc / "ket_qua.jsonl").open("a", encoding="utf-8") as f:
        f.write(json.dumps({
            "ma": ma,
            "ngay": ngay,
            "rating": str(rating),
            "phut": round(phut, 2),
            "so_luot_ai": td.so_luot_ai,
            "loi": loi
        }, ensure_ascii=False) + "\n")

    if loi:
        if "API_KEY_INVALID" in loi or "API key not valid" in loi:
            td.buoc = "LỖI: Khóa Gemini không hợp lệ"
            td.ghi()
            print("\n LỖI: Khóa Gemini API không đúng hoặc đã hết hạn.")
            sys.exit(4)
        td.buoc = "LỖI khi chạy"
        td.ghi()
        print("\n CÓ LỖI XẢY RA KHI CHẠY (Thường do mã không có trên Yahoo Finance hoặc mất mạng):")
        print(loi[-800:])
        sys.exit(3)

    tep_md, tep_html = ghi_bien_ban(thu_muc, ma, ngay, state, rating, phut)
    td.buoc = "HOÀN THÀNH"
    td.ket_qua = str(rating)
    td.ghi()

    link_bao_cao = f"http://localhost:{port}/{urllib.parse.quote(tep_html.name)}"
    link_dashboard = f"http://localhost:{port}/"

    print("\n" + "=" * 60)
    print(f" 🚀 HOÀN TẤT PHÂN TÍCH: {ma} ({ngay})")
    print(f" 🎯 Xếp hạng khuyến nghị: {rating}")
    print(f" ⏱️ Thời gian thực thi: {phut:.1f} phút (Số lượt gọi AI: {td.so_luot_ai})")
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
