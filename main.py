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
import warnings
import webbrowser

# Bỏ qua triệt để cảnh báo từ thư viện bên thứ 3 (yfinance / pandas PDEP-8 inplace trên mọi thread)
_old_showwarning = warnings.showwarning
def _loc_canh_bao(message, category, filename, lineno, file=None, line=None):
    msg_str = str(message)
    cat_name = getattr(category, "__name__", "")
    if "inplace" in msg_str or "Pandas4Warning" in cat_name or "PDEP-8" in msg_str or "yfinance" in str(filename):
        return
    _old_showwarning(message, category, filename, lineno, file, line)
warnings.showwarning = _loc_canh_bao
warnings.filterwarnings("ignore", category=FutureWarning)
warnings.filterwarnings("ignore", category=DeprecationWarning)
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
KQ = GOC / "results"
KQ.mkdir(exist_ok=True)

import threading

class KeyRotator:
    """Quản lý xoay tua danh sách nhiều API Key (Round-Robin & Tự động Failover khi chạm RateLimit 429)."""

    def __init__(self, raw_input: str | list[str] = "", name: str = "Key"):
        self.keys: list[str] = []
        self.name = name
        self.index = 0
        self.lock = threading.Lock()
        self.them(raw_input)

    def them(self, raw_input: str | list[str]):
        if isinstance(raw_input, str):
            for part in raw_input.replace("\r", "\n").replace(";", "\n").replace(",", "\n").split("\n"):
                k = part.strip().strip('"').strip("'")
                if k and len(k) > 10 and not k.startswith("#"):
                    if k not in self.keys:
                        self.keys.append(k)
        elif isinstance(raw_input, (list, tuple)):
            for item in raw_input:
                self.them(str(item))

    def get_current(self) -> str:
        with self.lock:
            if not self.keys:
                return ""
            return self.keys[self.index % len(self.keys)]

    def rotate(self, reason: str = "") -> str:
        with self.lock:
            if not self.keys:
                return ""
            if len(self.keys) == 1:
                return self.keys[0]
            old_idx = self.index % len(self.keys)
            self.index = (self.index + 1) % len(self.keys)
            new_key = self.keys[self.index]
            tail = new_key[-4:] if len(new_key) >= 4 else "..."
            ly_do_str = f" [{reason}]" if reason else ""
            print(f"🔄 [KeyRotator] Xoay tua {self.name}: Tài khoản #{old_idx+1} ➔ #{self.index+1}/{len(self.keys)} (...{tail}){ly_do_str}", flush=True)
            return new_key

    def has_multiple(self) -> bool:
        return len(self.keys) > 1

    def count(self) -> int:
        return len(self.keys)


# Nạp danh sách khóa Gemini từ biến môi trường, file .env hoặc khoa-gemini.txt
def lay_cac_khoa_gemini(extra: str = "") -> KeyRotator:
    rot = KeyRotator(extra, "Gemini")
    for env_var in ("GOOGLE_API_KEY", "GOOGLE_API_KEYS", "GEMINI_API_KEY"):
        if os.environ.get(env_var):
            rot.them(os.environ[env_var])
    env_file = GOC / ".env"
    if env_file.exists():
        for line in env_file.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            for prefix in ("GOOGLE_API_KEY=", "GOOGLE_API_KEYS=", "GEMINI_API_KEY="):
                if line.startswith(prefix):
                    rot.them(line.split("=", 1)[1].strip())
    khoa_file = GOC / "khoa-gemini.txt"
    if khoa_file.exists():
        rot.them(khoa_file.read_text(encoding="utf-8-sig"))
    return rot


# Nạp danh sách khóa Groq từ biến môi trường, file .env hoặc khoa-groq.txt
def lay_cac_khoa_groq(extra: str = "") -> KeyRotator:
    rot = KeyRotator(extra, "Groq")
    for env_var in ("GROQ_API_KEY", "GROQ_API_KEYS"):
        if os.environ.get(env_var):
            rot.them(os.environ[env_var])
    env_file = GOC / ".env"
    if env_file.exists():
        for line in env_file.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            for prefix in ("GROQ_API_KEY=", "GROQ_API_KEYS="):
                if line.startswith(prefix):
                    rot.them(line.split("=", 1)[1].strip())
    khoa_file = GOC / "khoa-groq.txt"
    if khoa_file.exists():
        rot.them(khoa_file.read_text(encoding="utf-8-sig"))
    return rot


# Nạp khóa FRED từ biến môi trường, file .env hoặc khoa-fred.txt
def lay_khoa_fred() -> str:
    if os.environ.get("FRED_API_KEY"):
        return os.environ["FRED_API_KEY"].strip()

    env_file = GOC / ".env"
    if env_file.exists():
        for line in env_file.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line.startswith("FRED_API_KEY="):
                key = line.split("=", 1)[1].strip().strip('"').strip("'")
                if key:
                    os.environ["FRED_API_KEY"] = key
                    return key

    khoa_file = GOC / "khoa-fred.txt"
    if khoa_file.exists():
        key = khoa_file.read_text(encoding="utf-8-sig").strip()
        if key:
            os.environ["FRED_API_KEY"] = key
            return key

    return ""


def cai_dat_xoay_tua_he_thong(gemini_rotator: KeyRotator, groq_rotator: KeyRotator):
    """Cài đặt hook xoay tua round-robin và failover tự động cho toàn bộ hệ thống LLM."""
    if gemini_rotator.has_multiple():
        from tradingagents.llm_clients.google_client import NormalizedChatGoogleGenerativeAI
        from google.genai import Client

        orig_gemini_invoke = NormalizedChatGoogleGenerativeAI.invoke

        def wrapped_gemini_invoke(self, input, config=None, **kwargs):
            cur_k = gemini_rotator.rotate("Lượt AI mới")
            try:
                self.client = Client(api_key=cur_k)
            except Exception:
                pass

            max_retries = gemini_rotator.count()
            for attempt in range(max_retries):
                try:
                    return orig_gemini_invoke(self, input, config=config, **kwargs)
                except Exception as e:
                    err = str(e)
                    if ("429" in err or "RESOURCE_EXHAUSTED" in err or "quota" in err.lower() or "limit" in err.lower()) and attempt < max_retries - 1:
                        next_k = gemini_rotator.rotate("Chạm RateLimit 429, đổi tài khoản Gemini khác")
                        try:
                            self.client = Client(api_key=next_k)
                        except Exception:
                            pass
                        continue
                    raise

        NormalizedChatGoogleGenerativeAI.invoke = wrapped_gemini_invoke

    if groq_rotator.has_multiple():
        from tradingagents.llm_clients.openai_client import NormalizedChatOpenAI

        orig_groq_invoke = NormalizedChatOpenAI.invoke

        def wrapped_groq_invoke(self, input, config=None, **kwargs):
            cur_k = groq_rotator.rotate("Lượt AI mới")
            try:
                self.root_client.api_key = cur_k
            except Exception:
                pass

            max_retries = groq_rotator.count()
            for attempt in range(max_retries):
                try:
                    return orig_groq_invoke(self, input, config=config, **kwargs)
                except Exception as e:
                    err = str(e)
                    if ("429" in err or "rate_limit" in err.lower() or "quota" in err.lower() or "limit" in err.lower()) and attempt < max_retries - 1:
                        next_k = groq_rotator.rotate("Chạm RateLimit 429/TPM, đổi tài khoản Groq khác")
                        try:
                            self.root_client.api_key = next_k
                        except Exception:
                            pass
                        continue
                    raise

        NormalizedChatOpenAI.invoke = wrapped_groq_invoke


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


def kiem_tra_groq_key(groq_key: str) -> tuple[bool, str]:
    """Kiểm tra khóa Groq và tự động phát hiện model text khả dụng tốt nhất của tài khoản."""
    import requests
    uu_tien = [
        "openai/gpt-oss-120b",
        "openai/gpt-oss-20b",
        "qwen/qwen3.8-27b",
        "llama-3.3-70b-versatile",
        "llama-3.1-8b-instant",
    ]
    try:
        res = requests.get(
            "https://api.groq.com/openai/v1/models",
            headers={"Authorization": f"Bearer {groq_key}"},
            timeout=8,
        )
        if res.status_code == 200:
            danh_sach = {m.get("id") for m in res.json().get("data", [])}
            for m in uu_tien:
                if m in danh_sach:
                    return True, m
            for m in sorted(danh_sach):
                if not any(x in m for x in ("whisper", "orpheus", "guard", "embed")):
                    return True, m
            return False, ""
        else:
            return False, ""
    except Exception:
        return True, "openai/gpt-oss-120b"


def cau_hinh(ma: str, groq_rotator: KeyRotator | None = None, gemini_rotator: KeyRotator | None = None, groq_key: str = "", gemini_key: str = ""):
    from tradingagents.default_config import DEFAULT_CONFIG
    c = DEFAULT_CONFIG.copy()

    g_rot = gemini_rotator or lay_cac_khoa_gemini(gemini_key)
    q_rot = groq_rotator or lay_cac_khoa_groq(groq_key)
    fred_k = lay_khoa_fred()

    if q_rot.get_current():
        os.environ["GROQ_API_KEY"] = q_rot.get_current()
    if g_rot.get_current():
        os.environ["GOOGLE_API_KEY"] = g_rot.get_current()
    if fred_k:
        os.environ["FRED_API_KEY"] = fred_k

    thu_muc = KQ / ten_sach(ma)
    thu_muc.mkdir(exist_ok=True)
    c["results_dir"] = str(thu_muc / "logs")
    c["data_cache_dir"] = str(GOC / "cache")
    c["memory_log_path"] = str(thu_muc / "so_nho.md")
    c["output_language"] = "English"
    c["max_tool_rounds"] = int(os.getenv("MAX_TOOL_ROUNDS", "10"))

    # Cài đặt hook xoay tua đa tài khoản tự động
    cai_dat_xoay_tua_he_thong(g_rot, q_rot)

    # Tự động phát hiện model Groq khả dụng hoặc tự động fallback về Gemini nếu Groq không khả dụng
    model_groq = ""
    groq_co_san = bool(q_rot.get_current())
    if groq_co_san:
        hop_le, model_phat_hien = kiem_tra_groq_key(q_rot.get_current())
        if hop_le and model_phat_hien:
            model_groq = os.getenv("GROQ_QUICK", model_phat_hien)
        elif g_rot.get_current():
            print("⚠️ Khóa Groq không có model chat khả dụng hoặc không hợp lệ. Tự động chuyển sang dùng Google Gemini.")
            groq_co_san = False

    gemini_co_san = bool(g_rot.get_current())

    # Cấu hình đa tác tử thông minh:
    # 1. Chế độ Lai Hybrid (Groq + Gemini) - Tối ưu nhất:
    if groq_co_san and gemini_co_san:
        c["llm_provider"] = "google"
        c["quick_think_provider"] = "groq"
        c["quick_think_llm"] = model_groq or "openai/gpt-oss-120b"
        c["deep_think_provider"] = "google"
        c["deep_think_llm"] = os.getenv("GEMINI_DEEP", "gemini-3.8-flash")
        mo_ta_ai = f"Hybrid (Groq {c['quick_think_llm']} [{q_rot.count()} keys] + Gemini {c['deep_think_llm']} [{g_rot.count()} keys])"
    # 2. Chế độ thuần Groq: Siêu nhanh, hoàn toàn miễn phí, không cần Gemini
    elif groq_co_san:
        c["llm_provider"] = "groq"
        c["quick_think_provider"] = "groq"
        c["quick_think_llm"] = os.getenv("GROQ_QUICK", model_groq or "openai/gpt-oss-20b")
        c["deep_think_provider"] = "groq"
        c["deep_think_llm"] = os.getenv("GROQ_DEEP", model_groq or "openai/gpt-oss-120b")
        mo_ta_ai = f"Groq ({c['deep_think_llm']} [{q_rot.count()} keys])"
    # 3. Chế độ thuần Google Gemini
    else:
        c["llm_provider"] = "google"
        c["quick_think_llm"] = os.getenv("GEMINI_QUICK", "gemini-3.5-flash-lite")
        c["deep_think_llm"] = os.getenv("GEMINI_DEEP", "gemini-3.8-flash")
        mo_ta_ai = f"Google Gemini ({c['deep_think_llm']} [{g_rot.count()} keys])"

    return c, thu_muc, mo_ta_ai


class TheoDoi:
    def __init__(self, thu_muc: Path, ma: str, ngay: str, mo_ta_ai: str = "Gemini"):
        self.thu_muc, self.ma, self.ngay, self.mo_ta_ai = thu_muc, ma, ngay, mo_ta_ai
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
<div class="o">Mã: <b>{html.escape(self.ma)}</b> · Ngày: <b>{self.ngay}</b> · Bộ não: <b>{html.escape(self.mo_ta_ai)}</b></div>
<div class="o">Bước hiện tại: <b class="v">{html.escape(self.buoc)}</b><br>
Số lượt gọi AI: <b>{self.so_luot_ai}</b> · Đã chạy: <b>{phut:.1f} phút</b><br>
<small>Trang tự làm mới mỗi 20 giây.</small></div>
{f'<div class="o">Kết quả: <b class="v">{html.escape(self.ket_qua)}</b><br>Biên bản đã lưu trong thư mục results.</div>' if self.ket_qua else ''}
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
                gio = datetime.now().strftime("%H:%M:%S")
                print(f"[{gio}] 🤖 [AI #{td.so_luot_ai}] {td.buoc}...", flush=True)
            except Exception:
                pass

    return CB()


def ghi_bien_ban(thu_muc: Path, ma: str, ngay: str, state: dict, rating: str, phut: float, mo_ta_ai: str = "Google Gemini") -> Path:
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
        f"Xếp hạng khuyến nghị: **{rating}** · Thời gian chạy: {phut:.1f} phút · Bộ não AI: {mo_ta_ai}",
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
            model=mo_ta_ai,
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
    parser = argparse.ArgumentParser(description="Chạy AI Trading Multi-Agent với Groq và Google Gemini")
    parser.add_argument("--ma", "-m", help="Mã tài sản (VD: BTC-USD, GC=F, NVDA, AAPL)")
    parser.add_argument("--ngay", "-d", help="Ngày phân tích dạng YYYY-MM-DD")
    parser.add_argument("--api-key", "-k", help="Google Gemini API Key")
    parser.add_argument("--groq-key", "-g", help="Groq API Key (khuyên dùng để tăng tốc và tránh rate limit)")
    parser.add_argument("--headless", action="store_true", help="Không tự động mở trình duyệt hoặc file viewer")
    args = parser.parse_args()

    # 1. Lấy danh sách API Keys và thiết lập bể chứa xoay tua đa tài khoản
    gemini_rotator = lay_cac_khoa_gemini(args.api_key or "")
    groq_rotator = lay_cac_khoa_groq(args.groq_key or "")

    if not gemini_rotator.count() and not groq_rotator.count():
        print("\n" + "=" * 55)
        print(" CHƯA CÓ KHÓA API (GROQ hoặc GOOGLE GEMINI)")
        print(" Bạn có thể dùng 1 trong 2 hoặc kết hợp cả 2:")
        print("   1. Groq (Khuyên dùng - Siêu tốc, không lo chạm limit): https://console.groq.com/keys")
        print("   2. Google Gemini: https://aistudio.google.com/apikey")
        print("   (Có thể dán nhiều khóa cách nhau bằng dấu phẩy để tự động xoay tua)")
        print("=" * 55)
        chon = input(" Nhập lựa chọn khóa bạn muốn thêm (1=Groq, 2=Gemini) [Mặc định 1]: ").strip()
        if chon == "2":
            k = input(" Dán khóa Gemini API (có thể dán nhiều khóa): ").strip()
            if len(k) >= 20:
                (GOC / "khoa-gemini.txt").write_text(k, encoding="utf-8")
                gemini_rotator.them(k)
        else:
            k = input(" Dán khóa Groq API (có thể dán nhiều khóa): ").strip()
            if len(k) >= 20:
                (GOC / "khoa-groq.txt").write_text(k, encoding="utf-8")
                groq_rotator.them(k)

        if not gemini_rotator.count() and not groq_rotator.count():
            print(" Khóa không hợp lệ. Thoát chương trình.")
            sys.exit(1)

    if gemini_rotator.count() > 1:
        print(f" 🔑 Bể chứa Gemini: Đã nạp {gemini_rotator.count()} tài khoản để xoay tua chống RateLimit.")
    if groq_rotator.count() > 1:
        print(f" 🔑 Bể chứa Groq: Đã nạp {groq_rotator.count()} tài khoản để xoay tua chống RateLimit.")

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

    c, thu_muc, mo_ta_ai = cau_hinh(ma, groq_rotator=groq_rotator, gemini_rotator=gemini_rotator)

    print("\n" + "-" * 55)
    print(f" BẮT ĐẦU PHÂN TÍCH: Mã {ma} - Ngày {ngay}")
    print(f" 🧠 Cấu hình AI: {mo_ta_ai}")
    print(" Đang khởi tạo các Agent phân tích tài chính...")
    print("-" * 55)

    from tradingagents.graph.trading_graph import TradingAgentsGraph

    crypto = ma.endswith("-USD")
    hang_hoa = ma.endswith("=F") or ma.startswith("^")
    phong = ["market", "social", "news"]
    if not crypto and not hang_hoa:
        phong.append("fundamentals")  # Cổ phiếu có thêm phân tích BCTC

    td = TheoDoi(thu_muc, ma, ngay, mo_ta_ai=mo_ta_ai)

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
            td.buoc = "LỖI: Khóa API không hợp lệ"
            td.ghi()
            print("\n LỖI: Khóa API không đúng hoặc đã hết hạn.")
            sys.exit(4)
        td.buoc = "LỖI khi chạy"
        td.ghi()
        print("\n CÓ LỖI XẢY RA KHI CHẠY (Thường do mã không có trên Yahoo Finance hoặc mất mạng):")
        print(loi[-800:])
        sys.exit(3)

    tep_md, tep_html = ghi_bien_ban(thu_muc, ma, ngay, state, rating, phut, mo_ta_ai=mo_ta_ai)
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
