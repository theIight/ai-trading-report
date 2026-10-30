#!/usr/bin/env python3
"""Máy chủ HTTP cục bộ phục vụ các file Báo cáo phân tích AI Trading.
Cho phép mở báo cáo trực tiếp dạng link:
  http://localhost:5050/ten_file_bao_cao.html
  hoặc http://localhost:5050/
Tích hợp:
  - Giao diện Sáng (Light Theme) mặc định, hỗ trợ đổi Sáng/Tối
  - Khởi chạy phân tích trực tiếp trên giao diện web (gọi run_antigravity.sh)
  - Theo dõi tiến trình thời gian thực
  - Quản lý, tải và xoá báo cáo
"""

from __future__ import annotations

import argparse
import html
import http.server
import json
import os
import re
import socket
import socketserver
import subprocess
import sys
import threading
import time
import urllib.parse
import urllib.request
import webbrowser
from datetime import datetime, timedelta
from pathlib import Path

# Thư mục gốc dự án và thư mục Kết quả
GOC = Path(__file__).resolve().parent
THU_MUC_KQ = GOC / "Kết quả"
PORT_MAC_DINH = 5050
PID_FILE = GOC / ".server.pid"


def ten_sach(ma: str) -> str:
    return "".join(ch if ch.isalnum() or ch in "-_." else "_" for ch in ma)


def tim_file_bao_cao(duong_dan_hoac_ten: str) -> Path | None:
    """Tìm file báo cáo trong thư mục Kết quả (hỗ trợ cả đường dẫn tương đối và tên file)."""
    duong_chuan = duong_dan_hoac_ten.strip().lstrip("/")

    # 1. Thử đường dẫn chính xác trong Kết quả/
    truc_tiep = THU_MUC_KQ / duong_chuan
    if truc_tiep.is_file():
        return truc_tiep

    # 2. Tìm theo tên file ở cấp gốc hoặc trong bất kỳ thư mục con nào
    ten_tep = Path(duong_chuan).name
    for p in THU_MUC_KQ.rglob("*"):
        if p.is_file() and p.name == ten_tep:
            return p

    # 3. Thử tìm kiếm không phân biệt hoa thường
    ten_lower = ten_tep.lower()
    for p in THU_MUC_KQ.rglob("*"):
        if p.is_file() and p.name.lower() == ten_lower:
            return p

    return None


class AnalysisRunner:
    """Quản lý tiến trình chạy phân tích nền đa tác tử (qua run_antigravity.sh)."""

    def __init__(self):
        self.lock = threading.Lock()
        self.process: subprocess.Popen | None = None
        self.ma = ""
        self.ngay = ""
        self.model = ""
        self.start_time = 0.0
        self.status = "idle"  # "idle", "running", "completed", "error"
        self.current_step = ""
        self.log_lines: list[str] = []
        self.report_file = ""
        self.error_message = ""

    def start(self, ma: str, ngay: str, model: str) -> tuple[bool, str]:
        with self.lock:
            if self.process and self.process.poll() is None:
                return False, f"Một phiên phân tích cho {self.ma} đang chạy. Vui lòng đợi hoặc huỷ trước."

            self.ma = ma.strip().upper()
            self.ngay = ngay.strip()
            self.model = model.strip() or "gemini-3.8-flash-high"
            self.start_time = time.time()
            self.status = "running"
            self.current_step = "Đang khởi động môi trường Antigravity..."
            self.log_lines = []
            self.report_file = ""
            self.error_message = ""

            script_sh = GOC / "run_antigravity.sh"
            cmd = [
                str(script_sh),
                "--ma", self.ma,
                "--ngay", self.ngay,
                "--model", self.model,
                "--headless"
            ]

            env = os.environ.copy()
            user_home = Path.home()
            extra_paths = [
                str(user_home / ".local" / "bin"),
                "/opt/homebrew/bin",
                "/usr/local/bin",
                "/usr/bin",
                "/bin"
            ]
            env["PATH"] = ":".join(extra_paths) + ":" + env.get("PATH", "")
            env["PYTHONUNBUFFERED"] = "1"
            env["PYTHONIOENCODING"] = "utf-8"

            try:
                self.process = subprocess.Popen(
                    cmd,
                    cwd=str(GOC),
                    env=env,
                    stdin=subprocess.DEVNULL,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    text=True,
                    bufsize=1,
                    universal_newlines=True
                )
            except Exception as e:
                self.status = "error"
                self.error_message = str(e)
                return False, f"Không thể khởi động lệnh: {e}"

            t = threading.Thread(target=self._read_output, daemon=True)
            t.start()
            return True, "Đã bắt đầu phiên phân tích."

    def cancel(self) -> tuple[bool, str]:
        with self.lock:
            if self.process and self.process.poll() is None:
                try:
                    self.process.terminate()
                    self.status = "error"
                    self.error_message = "Đã bị dừng bởi người dùng."
                    return True, "Đã gửi lệnh dừng phiên phân tích."
                except Exception as e:
                    return False, f"Không thể dừng tiến trình: {e}"
            return False, "Không có tiến trình nào đang chạy."

    def _read_output(self):
        proc = self.process
        if not proc or not proc.stdout:
            return

        for line in proc.stdout:
            s_line = line.strip()
            if s_line:
                self.log_lines.append(s_line)
                if len(self.log_lines) > 300:
                    self.log_lines.pop(0)

                if "Khởi động & Thu thập" in s_line or "Thu thập dữ liệu" in s_line:
                    self.current_step = "Khởi động & Thu thập dữ liệu nến/chỉ báo"
                elif "Phòng kỹ thuật" in s_line or "Market Technician" in s_line:
                    self.current_step = "Phòng kỹ thuật (nến, xu hướng, RSI, MACD)"
                elif "Phòng tin tức" in s_line or "Sentiment" in s_line:
                    self.current_step = "Phòng tin tức & tâm lý thị trường"
                elif "Phòng tài chính" in s_line or "Fundamentals" in s_line:
                    self.current_step = "Phòng tài chính (định giá & cơ bản)"
                elif "tranh luận" in s_line.lower() or "bull vs bear" in s_line.lower():
                    self.current_step = "Phe Mua và Phe Bán tranh luận (Bull vs Bear)"
                elif "quản lý rủi ro" in s_line.lower() or "risk" in s_line.lower():
                    self.current_step = "Hội đồng quản trị rủi ro thẩm định"
                elif "Giám đốc" in s_line or "Portfolio Manager" in s_line:
                    self.current_step = "Giám đốc quỹ ra phán quyết cuối cùng"
                elif "HOÀN TẤT PHÂN TÍCH" in s_line:
                    self.current_step = "Đã hoàn tất phân tích!"

        proc.wait()
        with self.lock:
            if proc.returncode == 0:
                self.status = "completed"
                self.current_step = "Hoàn tất! Báo cáo đã sẵn sàng."
                ten_ma_sach = ten_sach(self.ma)
                self.report_file = f"Biên bản {ten_ma_sach} {self.ngay}.html"
            else:
                if self.status != "error":
                    self.status = "error"
                    self.error_message = f"Tiến trình kết thúc với mã lỗi {proc.returncode}."

    def get_status(self) -> dict:
        with self.lock:
            is_running = self.process is not None and self.process.poll() is None
            elapsed = int(time.time() - self.start_time) if self.start_time > 0 else 0
            return {
                "running": is_running,
                "status": self.status,
                "ma": self.ma,
                "ngay": self.ngay,
                "model": self.model,
                "step": self.current_step,
                "elapsed": elapsed,
                "report_file": self.report_file,
                "report_url": f"/{urllib.parse.quote(self.report_file)}" if self.report_file else None,
                "error": self.error_message,
                "logs": self.log_lines[-25:],
            }


RUNNER = AnalysisRunner()


def lay_danh_sach_bao_cao() -> list[dict]:
    danh_sach = []
    for p in sorted(THU_MUC_KQ.rglob("*.html"), key=lambda x: x.stat().st_mtime, reverse=True):
        if p.name.startswith("Tiến độ") or p.name.startswith("Tiến"):
            continue
        ten = p.name
        ma = p.parent.name
        mtime = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(p.stat().st_mtime))
        kich_thuoc = f"{p.stat().st_size / 1024:.1f} KB"

        noi_dung = ""
        try:
            noi_dung = p.read_text(encoding="utf-8")[:4000]
        except Exception:
            pass

        badge = '<span class="badge badge-info">Báo cáo</span>'
        rating_text = "N/A"
        if "badge-buy" in noi_dung:
            badge = '<span class="badge badge-buy">🟢 BUY</span>'
            rating_text = "BUY"
        elif "badge-sell" in noi_dung:
            badge = '<span class="badge badge-sell">🔴 SELL</span>'
            rating_text = "SELL"
        elif "badge-hold" in noi_dung:
            badge = '<span class="badge badge-hold">🟡 HOLD</span>'
            rating_text = "HOLD"

        md_file = p.with_suffix(".md")
        has_md = md_file.exists()

        danh_sach.append({
            "ten": ten,
            "ma": ma,
            "mtime": mtime,
            "size": kich_thuoc,
            "badge": badge,
            "rating": rating_text,
            "link_html": f"/{urllib.parse.quote(ten)}",
            "link_md": f"/{urllib.parse.quote(md_file.name)}" if has_md else None,
        })
    return danh_sach


def tao_trang_dashboard_html(port: int) -> str:
    """Tạo giao diện Dashboard trang chủ: Mặc định Light theme, có Form chạy phân tích và nút Xoá."""
    danh_sach = lay_danh_sach_bao_cao()
    cac_ma = {item["ma"] for item in danh_sach}

    hom_qua = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")

    hang_html = []
    for idx, item in enumerate(danh_sach):
        ten_escaped = html.escape(item['ten'])
        ten_js = item['ten'].replace("'", "\\'")
        hang_html.append(f"""
        <tr id="row-{idx}" class="report-row" data-ma="{html.escape(item['ma'].upper())}" data-ten="{html.escape(item['ten'].lower())}">
          <td><span class="ticker-pill">{html.escape(item['ma'])}</span></td>
          <td><b>{ten_escaped}</b></td>
          <td>{item['badge']}</td>
          <td style="color:var(--text-muted); font-size:13px;">{item['mtime']}</td>
          <td style="color:var(--text-muted); font-size:13px;">{item['size']}</td>
          <td style="text-align:right; white-space:nowrap;">
            <a href="{item['link_html']}" class="btn btn-primary btn-sm">Mở Báo Cáo ↗</a>
            {'<a href="' + item['link_md'] + '" class="btn btn-sm" style="margin-left:5px;" download>Markdown</a>' if item['link_md'] else ''}
            <button class="btn btn-danger btn-sm" style="margin-left:5px;" onclick="xoaBaoCao('{ten_js}', 'row-{idx}')" title="Xoá báo cáo này">🗑️ Xoá</button>
          </td>
        </tr>
        """)

    danh_sach_rows = "".join(hang_html) if hang_html else """
      <tr id="emptyRow">
        <td colspan="6" style="text-align:center; padding: 40px; color: var(--text-muted);">
          Chưa có báo cáo nào được tạo. Hãy nhấn "Bắt Đầu Phân Tích" ở trên để tạo báo cáo đầu tiên!
        </td>
      </tr>
    """

    return f"""<!doctype html>
<html lang="vi" data-theme="light">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>AI Trading · Trung Tâm Quản Lý Báo Cáo</title>
  <style>
    :root {{
      --bg-primary: #f8fafc;
      --bg-secondary: #f1f5f9;
      --bg-card: #ffffff;
      --bg-hover: #f1f5f9;
      --border-color: #e2e8f0;
      --text-primary: #0f172a;
      --text-secondary: #475569;
      --text-muted: #64748b;
      --accent-gold: #d97706;
      --accent-blue: #0284c7;
      --accent-green: #059669;
      --accent-red: #dc2626;
      --card-shadow: 0 4px 14px rgba(0, 0, 0, 0.05);
      --input-bg: #ffffff;
      --code-bg: #0f172a;
      --code-text: #e2e8f0;
    }}

    [data-theme="dark"] {{
      --bg-primary: #0b0e14;
      --bg-secondary: #121722;
      --bg-card: #182030;
      --bg-hover: #222d42;
      --border-color: #273349;
      --text-primary: #e6edf3;
      --text-secondary: #8b9bb4;
      --text-muted: #5d6e87;
      --accent-gold: #f59e0b;
      --accent-blue: #38bdf8;
      --accent-green: #10b981;
      --accent-red: #ef4444;
      --card-shadow: 0 10px 30px rgba(0, 0, 0, 0.2);
      --input-bg: #121722;
      --code-bg: #0b0e14;
      --code-text: #e2e8f0;
    }}

    * {{ box-sizing: border-box; margin: 0; padding: 0; }}
    body {{
      background: var(--bg-primary);
      color: var(--text-primary);
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
      padding: 24px 20px 80px 20px;
      line-height: 1.6;
      transition: background 0.2s, color 0.2s;
    }}
    .container {{
      max-width: 1120px;
      margin: 0 auto;
    }}
    header {{
      display: flex;
      justify-content: space-between;
      align-items: center;
      flex-wrap: wrap;
      gap: 16px;
      margin-bottom: 24px;
      padding-bottom: 16px;
      border-bottom: 1px solid var(--border-color);
    }}
    .title-group h1 {{
      font-size: 26px;
      font-weight: 800;
      background: linear-gradient(135deg, #f59e0b, #ef4444);
      -webkit-background-clip: text;
      -webkit-text-fill-color: transparent;
      letter-spacing: -0.5px;
    }}
    .title-group p {{
      color: var(--text-secondary);
      font-size: 14px;
      margin-top: 2px;
    }}
    .header-actions {{
      display: flex;
      align-items: center;
      gap: 8px;
    }}

    .stats-grid {{
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
      gap: 14px;
      margin-bottom: 24px;
    }}
    .stat-card {{
      background: var(--bg-card);
      border: 1px solid var(--border-color);
      border-radius: 12px;
      padding: 16px 20px;
      box-shadow: var(--card-shadow);
    }}
    .stat-card .label {{
      font-size: 12px;
      color: var(--text-muted);
      text-transform: uppercase;
      letter-spacing: 0.5px;
      margin-bottom: 4px;
    }}
    .stat-card .val {{
      font-size: 24px;
      font-weight: 700;
      color: var(--accent-blue);
    }}

    /* Panel Khởi Tạo Phân Tích */
    .runner-card {{
      background: var(--bg-card);
      border: 1px solid var(--border-color);
      border-radius: 14px;
      padding: 24px;
      margin-bottom: 24px;
      box-shadow: var(--card-shadow);
    }}
    .runner-header {{
      display: flex;
      justify-content: space-between;
      align-items: center;
      margin-bottom: 18px;
      flex-wrap: wrap;
      gap: 12px;
    }}
    .runner-header h2 {{
      font-size: 18px;
      font-weight: 700;
      display: flex;
      align-items: center;
      gap: 8px;
    }}
    .quick-chips {{
      display: flex;
      gap: 6px;
      flex-wrap: wrap;
      margin-bottom: 14px;
    }}
    .chip {{
      padding: 4px 10px;
      border-radius: 20px;
      font-size: 12px;
      font-weight: 600;
      cursor: pointer;
      border: 1px solid var(--border-color);
      background: var(--bg-secondary);
      color: var(--text-secondary);
      transition: all 0.15s;
    }}
    .chip:hover, .chip.active {{
      background: var(--accent-blue);
      color: #fff;
      border-color: var(--accent-blue);
    }}

    .form-grid {{
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)) auto;
      gap: 14px;
      align-items: end;
    }}
    @media (max-width: 768px) {{
      .form-grid {{ grid-template-columns: 1fr; }}
    }}

    .form-group label {{
      display: block;
      font-size: 12px;
      font-weight: 600;
      color: var(--text-muted);
      text-transform: uppercase;
      letter-spacing: 0.5px;
      margin-bottom: 6px;
    }}
    .form-control {{
      width: 100%;
      background: var(--input-bg);
      border: 1px solid var(--border-color);
      color: var(--text-primary);
      padding: 10px 14px;
      border-radius: 8px;
      font-size: 14px;
      outline: none;
      transition: border 0.15s;
    }}
    .form-control:focus {{
      border-color: var(--accent-blue);
    }}

    /* Khối trạng thái Live Progress */
    #liveProgressBox {{
      display: none;
      margin-top: 20px;
      padding: 18px;
      border-radius: 10px;
      background: var(--bg-secondary);
      border: 1px solid var(--border-color);
    }}
    .live-top {{
      display: flex;
      justify-content: space-between;
      align-items: center;
      flex-wrap: wrap;
      gap: 12px;
      margin-bottom: 12px;
    }}
    .pulse-dot {{
      display: inline-block;
      width: 10px;
      height: 10px;
      border-radius: 50%;
      background: #10b981;
      margin-right: 6px;
      animation: pulse 1.5s infinite;
    }}
    @keyframes pulse {{
      0% {{ opacity: 1; transform: scale(1); }}
      50% {{ opacity: 0.4; transform: scale(1.2); }}
      100% {{ opacity: 1; transform: scale(1); }}
    }}

    .log-box {{
      background: var(--code-bg);
      color: var(--code-text);
      font-family: ui-monospace, Menlo, Consolas, monospace;
      font-size: 12px;
      padding: 12px 14px;
      border-radius: 8px;
      max-height: 150px;
      overflow-y: auto;
      white-space: pre-wrap;
      line-height: 1.5;
      margin-top: 10px;
    }}

    /* Card Danh Sách */
    .card {{
      background: var(--bg-card);
      border: 1px solid var(--border-color);
      border-radius: 14px;
      padding: 24px;
      box-shadow: var(--card-shadow);
    }}
    .toolbar {{
      display: flex;
      justify-content: space-between;
      align-items: center;
      gap: 16px;
      margin-bottom: 20px;
      flex-wrap: wrap;
    }}
    .search-input {{
      background: var(--input-bg);
      border: 1px solid var(--border-color);
      color: var(--text-primary);
      padding: 9px 14px;
      border-radius: 8px;
      font-size: 14px;
      width: 280px;
      max-width: 100%;
    }}
    .search-input:focus {{
      outline: none;
      border-color: var(--accent-blue);
    }}

    table {{
      width: 100%;
      border-collapse: collapse;
      font-size: 14px;
    }}
    th {{
      text-align: left;
      padding: 12px 14px;
      color: var(--text-muted);
      font-weight: 600;
      border-bottom: 2px solid var(--border-color);
      font-size: 12px;
      text-transform: uppercase;
      letter-spacing: 0.5px;
    }}
    td {{
      padding: 14px;
      border-bottom: 1px solid var(--border-color);
    }}
    tr:hover td {{
      background: var(--bg-hover);
    }}
    .ticker-pill {{
      background: rgba(2, 132, 199, 0.08);
      color: var(--accent-blue);
      padding: 4px 10px;
      border-radius: 6px;
      font-weight: 700;
      font-size: 13px;
      border: 1px solid rgba(2, 132, 199, 0.2);
    }}
    .badge {{
      display: inline-flex;
      align-items: center;
      padding: 3px 8px;
      border-radius: 9999px;
      font-size: 12px;
      font-weight: 600;
    }}
    .badge-buy {{ background: rgba(16, 185, 129, 0.12); color: #047857; border: 1px solid rgba(16, 185, 129, 0.25); }}
    .badge-sell {{ background: rgba(239, 68, 68, 0.12); color: #b91c1c; border: 1px solid rgba(239, 68, 68, 0.25); }}
    .badge-hold {{ background: rgba(245, 158, 11, 0.12); color: #b45309; border: 1px solid rgba(245, 158, 11, 0.25); }}
    .badge-info {{ background: var(--bg-secondary); color: var(--text-secondary); border: 1px solid var(--border-color); }}
    [data-theme="dark"] .badge-buy {{ background: rgba(16, 185, 129, 0.15); color: #34d399; border-color: rgba(16, 185, 129, 0.3); }}
    [data-theme="dark"] .badge-sell {{ background: rgba(239, 68, 68, 0.15); color: #f87171; border-color: rgba(239, 68, 68, 0.3); }}
    [data-theme="dark"] .badge-hold {{ background: rgba(245, 158, 11, 0.15); color: #fbbf24; border-color: rgba(245, 158, 11, 0.3); }}

    .btn {{
      display: inline-flex;
      align-items: center;
      padding: 7px 14px;
      border-radius: 8px;
      font-size: 13px;
      font-weight: 500;
      text-decoration: none;
      cursor: pointer;
      border: 1px solid var(--border-color);
      background: var(--bg-card);
      color: var(--text-primary);
      transition: all 0.15s ease;
    }}
    .btn:hover {{
      background: var(--bg-hover);
      border-color: var(--accent-blue);
    }}
    .btn-primary {{
      background: #2563eb;
      border-color: #1d4ed8;
      color: #fff;
      font-weight: 600;
    }}
    .btn-primary:hover {{
      background: #1d4ed8;
    }}
    .btn-danger {{
      background: rgba(239, 68, 68, 0.1);
      border-color: rgba(239, 68, 68, 0.25);
      color: #dc2626;
      font-weight: 500;
    }}
    .btn-danger:hover {{
      background: #dc2626;
      border-color: #b91c1c;
      color: #fff;
    }}
    .btn-sm {{
      padding: 4px 10px;
      font-size: 12px;
    }}
    #toast {{
      position: fixed;
      bottom: 24px;
      right: 24px;
      background: #10b981;
      color: #fff;
      padding: 12px 20px;
      border-radius: 8px;
      font-size: 14px;
      font-weight: 600;
      box-shadow: 0 6px 16px rgba(0,0,0,0.3);
      display: none;
      z-index: 1000;
    }}
  </style>
</head>
<body>
  <div class="container">
    <header>
      <div class="title-group">
        <h1>⚡ AI TRADING · HỆ THỐNG PHÂN TÍCH & BÁO CÁO</h1>
        <p>Giao diện điều hành, thẩm định tài chính đa tác tử trên localhost:{port}</p>
      </div>
      <div class="header-actions">
        <a href="/Tiến độ.html" class="btn" title="Xem file tiến độ">🚀 Tiến độ</a>
        <button class="btn" onclick="toggleTheme()" title="Đổi giao diện Sáng / Tối">🌓 Giao diện</button>
      </div>
    </header>

    <!-- Thống kê tổng quan -->
    <div class="stats-grid">
      <div class="stat-card">
        <div class="label">Tổng số báo cáo</div>
        <div class="val" id="totalReportsCount">{len(danh_sach)}</div>
      </div>
      <div class="stat-card">
        <div class="label">Mã tài sản đã phân tích</div>
        <div class="val" id="totalSymbolsCount">{len(cac_ma)}</div>
      </div>
      <div class="stat-card">
        <div class="label">Cổng máy chủ</div>
        <div class="val">:{port}</div>
      </div>
    </div>

    <!-- Bảng Điều Khiển: Khởi Chạy Phân Tích Mới -->
    <div class="runner-card">
      <div class="runner-header">
        <h2>🚀 Khởi Tạo Phân Tích Mới (Antigravity Native)</h2>
        <span class="badge badge-info" style="font-size:12px;">Phiên làm việc tự động · Không tốn API Key</span>
      </div>

      <div class="quick-chips">
        <span style="font-size:12px; color:var(--text-muted); align-self:center; margin-right:4px;">Chọn nhanh:</span>
        <button type="button" class="chip active" onclick="chonMa('BTC-USD')">BTC-USD (Bitcoin)</button>
        <button type="button" class="chip" onclick="chonMa('GC=F')">GC=F (Vàng thế giới)</button>
        <button type="button" class="chip" onclick="chonMa('NVDA')">NVDA (Nvidia)</button>
        <button type="button" class="chip" onclick="chonMa('AAPL')">AAPL (Apple)</button>
        <button type="button" class="chip" onclick="chonMa('TSLA')">TSLA (Tesla)</button>
        <button type="button" class="chip" onclick="chonMa('ETH-USD')">ETH-USD (Ethereum)</button>
      </div>

      <div class="form-grid">
        <div class="form-group">
          <label for="inputSymbol">Mã tài sản</label>
          <input type="text" id="inputSymbol" class="form-control" value="BTC-USD" placeholder="VD: BTC-USD, GC=F, NVDA...">
        </div>
        <div class="form-group">
          <label for="inputDate">Ngày phân tích</label>
          <input type="date" id="inputDate" class="form-control" value="{hom_qua}">
        </div>
        <div class="form-group">
          <label for="selectModel">Bộ não AI (Antigravity)</label>
          <select id="selectModel" class="form-control">
            <option value="gemini-3.8-flash-high" selected>Gemini 3.8 Flash (High) - Khuyên dùng</option>
            <option value="gemini-3.8-flash">Gemini 3.8 Flash</option>
            <option value="gemini-4-argon">Gemini 4 Argon</option>
          </select>
        </div>
        <div>
          <button id="btnRun" class="btn btn-primary" onclick="startAnalysis()" style="height:42px; width:100%; justify-content:center;">
            ▶️ Bắt Đầu Phân Tích
          </button>
        </div>
      </div>

      <!-- Khối hiển thị trạng thái Live Progress -->
      <div id="liveProgressBox">
        <div class="live-top">
          <div>
            <span class="pulse-dot"></span>
            <b>Đang phân tích:</b> <span id="liveSymbol" style="font-weight:700; color:var(--accent-blue);"></span>
            <span style="color:var(--text-muted); margin:0 6px;">·</span>
            <b>Bước:</b> <span id="liveStep" style="color:var(--accent-gold); font-weight:600;"></span>
          </div>
          <div style="display:flex; align-items:center; gap:8px;">
            <span style="font-size:13px; color:var(--text-muted);">Thời gian: <b id="liveElapsed">0s</b></span>
            <button class="btn btn-danger btn-sm" onclick="cancelAnalysis()">⏹️ Dừng</button>
            <a id="btnTienDoLink" href="#" target="_blank" class="btn btn-sm">Mở Tiến độ ↗</a>
          </div>
        </div>
        <div class="log-box" id="liveLogBox">Đang khởi tạo phiên...</div>
      </div>
    </div>

    <!-- Danh Sách Báo Cáo -->
    <div class="card">
      <div class="toolbar">
        <h2 style="font-size:18px;">Danh Sách Báo Cáo Phân Tích</h2>
        <div style="display:flex; align-items:center; gap:8px;">
          <input type="text" class="search-input" id="searchInput" placeholder="Tìm theo mã hoặc tên file..." oninput="filterReports()">
          <button class="btn btn-sm" onclick="syncFromGitHub(event)" title="Kéo các báo cáo mới được GitHub Actions tạo về máy (git pull)">🔄 Đồng bộ từ GitHub</button>
        </div>
      </div>

      <div style="overflow-x:auto;">
        <table>
          <thead>
            <tr>
              <th>Mã</th>
              <th>Tên File Báo Cáo</th>
              <th>Phán quyết</th>
              <th>Thời gian tạo</th>
              <th>Dung lượng</th>
              <th style="text-align:right;">Thao tác</th>
            </tr>
          </thead>
          <tbody id="reportTableBody">
            {danh_sach_rows}
          </tbody>
        </table>
      </div>
    </div>
  </div>

  <div id="toast"></div>

  <script>
    // Quản lý Theme: Mặc định Light nếu chưa chọn
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

    function chonMa(ma) {{
      document.getElementById('inputSymbol').value = ma;
      document.querySelectorAll('.chip').forEach(c => {{
        if (c.textContent.startsWith(ma)) {{
          c.classList.add('active');
        }} else {{
          c.classList.remove('active');
        }}
      }});
    }}

    function filterReports() {{
      const q = document.getElementById('searchInput').value.trim().toLowerCase();
      const rows = document.querySelectorAll('.report-row');
      rows.forEach(r => {{
        const ma = r.getAttribute('data-ma').toLowerCase();
        const ten = r.getAttribute('data-ten').toLowerCase();
        if (ma.includes(q) || ten.includes(q)) {{
          r.style.display = '';
        }} else {{
          r.style.display = 'none';
        }}
      }});
    }}

    function hienToast(msg, bg) {{
      const toast = document.getElementById('toast');
      if (toast) {{
        toast.textContent = msg;
        toast.style.background = bg || '#10b981';
        toast.style.display = 'block';
        setTimeout(() => {{ toast.style.display = 'none'; }}, 3000);
      }}
    }}

    let pollingTimer = null;

    function startAnalysis() {{
      const ma = document.getElementById('inputSymbol').value.trim().toUpperCase();
      const ngay = document.getElementById('inputDate').value.trim();
      const model = document.getElementById('selectModel').value.trim();

      if (!ma) {{
        alert('Vui lòng nhập mã tài sản (VD: BTC-USD, GC=F, NVDA)');
        return;
      }}
      if (!ngay) {{
        alert('Vui lòng chọn ngày phân tích');
        return;
      }}

      const btnRun = document.getElementById('btnRun');
      btnRun.disabled = true;
      btnRun.innerHTML = '⏳ Đang khởi chạy...';

      fetch('/api/run', {{
        method: 'POST',
        headers: {{ 'Content-Type': 'application/json' }},
        body: JSON.stringify({{ ma, ngay, model }})
      }})
      .then(res => res.json())
      .then(data => {{
        if (data.status === 'ok') {{
          hienToast('🚀 Đã bắt đầu phiên phân tích cho ' + ma);
          batDauTheoDoi();
        }} else {{
          alert('Lỗi: ' + (data.message || 'Không thể bắt đầu phân tích'));
          btnRun.disabled = false;
          btnRun.innerHTML = '▶️ Bắt Đầu Phân Tích';
        }}
      }})
      .catch(err => {{
        alert('Lỗi kết nối: ' + err);
        btnRun.disabled = false;
        btnRun.innerHTML = '▶️ Bắt Đầu Phân Tích';
      }});
    }}

    function batDauTheoDoi() {{
      const box = document.getElementById('liveProgressBox');
      box.style.display = 'block';

      if (pollingTimer) clearInterval(pollingTimer);
      pollingTimer = setInterval(kiemTraTienDo, 2000);
      kiemTraTienDo();
    }}

    function formatTime(sec) {{
      const m = Math.floor(sec / 60);
      const s = sec % 60;
      return `${{m}}p ${{s < 10 ? '0' : ''}}${{s}}s`;
    }}

    function kiemTraTienDo() {{
      fetch('/api/run-status')
      .then(res => res.json())
      .then(data => {{
        const btnRun = document.getElementById('btnRun');
        const box = document.getElementById('liveProgressBox');

        if (data.running) {{
          btnRun.disabled = true;
          btnRun.innerHTML = '⏳ Đang phân tích...';
          box.style.display = 'block';

          document.getElementById('liveSymbol').textContent = `${{data.ma}} (${{data.ngay}})`;
          document.getElementById('liveStep').textContent = data.step || 'Đang phân tích...';
          document.getElementById('liveElapsed').textContent = formatTime(data.elapsed || 0);

          const linkTienDo = document.getElementById('btnTienDoLink');
          linkTienDo.href = `/${{encodeURIComponent(data.ma)}}/Tiến độ.html`;

          const logBox = document.getElementById('liveLogBox');
          if (data.logs && data.logs.length > 0) {{
            logBox.textContent = data.logs.join('\\n');
            logBox.scrollTop = logBox.scrollHeight;
          }}
        }} else {{
          if (pollingTimer) {{
            clearInterval(pollingTimer);
            pollingTimer = null;
          }}
          btnRun.disabled = false;
          btnRun.innerHTML = '▶️ Bắt Đầu Phân Tích';

          if (data.status === 'completed') {{
            hienToast('🎉 Phân tích hoàn tất! Báo cáo đã sẵn sàng.', '#10b981');
            document.getElementById('liveStep').textContent = '✅ Hoàn tất thành công!';
            const logBox = document.getElementById('liveLogBox');
            if (data.report_url) {{
              logBox.innerHTML = `✅ Báo cáo đã xuất: <a href="${{data.report_url}}" target="_blank" style="color:#38bdf8; font-weight:700; text-decoration:underline;">${{data.report_file}} ↗</a>`;
            }}
            taiLaiDanhSachBaoCao();
          }} else if (data.status === 'error') {{
            hienToast('❌ Phân tích gặp lỗi hoặc đã bị dừng.', '#ef4444');
            document.getElementById('liveStep').textContent = '❌ Lỗi: ' + (data.error || 'Thất bại');
          }}
        }}
      }})
      .catch(() => {{}});
    }}

    function cancelAnalysis() {{
      if (!confirm('Bạn có chắc chắn muốn dừng phiên phân tích đang chạy?')) return;
      fetch('/api/run-cancel', {{ method: 'POST' }})
      .then(res => res.json())
      .then(d => {{
        hienToast(d.message || 'Đã gửi lệnh dừng');
        kiemTraTienDo();
      }});
    }}

    function syncFromGitHub(evt) {{
      const btn = evt ? evt.target : null;
      let oldHtml = '';
      if (btn) {{
        oldHtml = btn.innerHTML;
        btn.disabled = true;
        btn.innerHTML = '⏳ Đang kéo dữ liệu...';
      }}

      fetch('/api/git-pull', {{ method: 'POST' }})
      .then(res => res.json())
      .then(d => {{
        if (btn) {{
          btn.disabled = false;
          btn.innerHTML = oldHtml;
        }}
        if (d.status === 'ok') {{
          hienToast('✅ ' + (d.message || 'Đồng bộ từ GitHub thành công!'));
          taiLaiDanhSachBaoCao();
        }} else {{
          alert('Thông báo: ' + (d.message || 'Không thể chạy git pull. Kiểm tra xem dự án đã liên kết GitHub chưa.'));
        }}
      }})
      .catch(err => {{
        if (btn) {{
          btn.disabled = false;
          btn.innerHTML = oldHtml;
        }}
        alert('Lỗi kết nối: ' + err);
      }});
    }}

    function taiLaiDanhSachBaoCao() {{
      fetch('/api/reports')
      .then(res => res.json())
      .then(danhSach => {{
        const tbody = document.getElementById('reportTableBody');
        if (!danhSach || danhSach.length === 0) {{
          tbody.innerHTML = '<tr><td colspan="6" style="text-align:center; padding: 40px; color: var(--text-muted);">Chưa có báo cáo nào.</td></tr>';
          return;
        }}
        document.getElementById('totalReportsCount').textContent = danhSach.length;
        const cacMa = new Set(danhSach.map(x => x.ma));
        document.getElementById('totalSymbolsCount').textContent = cacMa.size;

        let htmlRows = '';
        for (let idx = 0; idx < danhSach.length; idx++) {{
          const item = danhSach[idx];
          const tenSafe = item.ten.replace(/'/g, "\\\\'");
          htmlRows += '<tr id="row-' + idx + '" class="report-row" data-ma="' + item.ma.toUpperCase() + '" data-ten="' + item.ten.toLowerCase() + '">';
          htmlRows += '<td><span class="ticker-pill">' + item.ma + '</span></td>';
          htmlRows += '<td><b>' + item.ten + '</b></td>';
          htmlRows += '<td>' + item.badge + '</td>';
          htmlRows += '<td style="color:var(--text-muted); font-size:13px;">' + item.mtime + '</td>';
          htmlRows += '<td style="color:var(--text-muted); font-size:13px;">' + item.size + '</td>';
          htmlRows += '<td style="text-align:right; white-space:nowrap;">';
          htmlRows += '<a href="' + item.link_html + '" class="btn btn-primary btn-sm">Mở Báo Cáo ↗</a>';
          if (item.link_md) {{
            htmlRows += '<a href="' + item.link_md + '" class="btn btn-sm" style="margin-left:5px;" download>Markdown</a>';
          }}
          htmlRows += '<button class="btn btn-danger btn-sm" style="margin-left:5px;" onclick="xoaBaoCao(\\'' + tenSafe + '\\', \\'row-' + idx + '\\')" title="Xoá báo cáo">🗑️ Xoá</button>';
          htmlRows += '</td></tr>';
        }}
        tbody.innerHTML = htmlRows;
      }});
    }}

    function xoaBaoCao(tenFile, rowId) {{
      if (!confirm(`Bạn có chắc chắn muốn xoá báo cáo:\\n"${{tenFile}}"?\\n\\n(Thao tác này sẽ xoá cả file HTML và Markdown tương ứng)`)) {{
        return;
      }}

      fetch('/api/delete?file=' + encodeURIComponent(tenFile), {{
        method: 'POST'
      }})
      .then(res => res.json())
      .then(data => {{
        if (data.status === 'ok') {{
          const row = document.getElementById(rowId);
          if (row) {{
            row.style.transition = 'all 0.3s ease';
            row.style.opacity = '0';
            row.style.transform = 'translateX(20px)';
            setTimeout(() => {{
              row.remove();
              const totalElem = document.getElementById('totalReportsCount');
              if (totalElem) {{
                const cur = parseInt(totalElem.textContent) || 1;
                totalElem.textContent = Math.max(0, cur - 1);
              }}
              const tbody = document.getElementById('reportTableBody');
              if (tbody && tbody.querySelectorAll('.report-row').length === 0) {{
                tbody.innerHTML = '<tr><td colspan="6" style="text-align:center; padding: 40px; color: var(--text-muted);">Không còn báo cáo nào.</td></tr>';
              }}
            }}, 300);
          }}
          hienToast('🗑️ Đã xoá báo cáo thành công!');
        }} else {{
          alert('Lỗi: ' + (data.message || 'Không thể xoá báo cáo'));
        }}
      }})
      .catch(err => {{
        alert('Lỗi kết nối tới máy chủ: ' + err);
      }});
    }}

    // Kiểm tra xem hiện có tác vụ đang chạy hay không khi vừa mở trang
    kiemTraTienDo();
  </script>
</body>
</html>
"""


class ReportHTTPRequestHandler(http.server.SimpleHTTPRequestHandler):
    """Custom Request Handler hỗ trợ:
    1. / -> Trang Dashboard danh sách báo cáo
    2. /ping -> Kiểm tra trạng thái máy chủ
    3. /api/run -> Khởi chạy phân tích đa tác tử
    4. /api/run-status -> Lấy trạng thái tiến trình thời gian thực
    5. /api/run-cancel -> Dừng tiến trình phân tích
    6. /api/reports -> Lấy danh sách báo cáo mới nhất (JSON)
    7. /api/delete -> API xoá báo cáo an toàn
    8. /<ten_file_bao_cao.html> -> Tìm kiếm và phục vụ file báo cáo
    """

    def log_message(self, format, *args):
        pass

    def do_OPTIONS(self):
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, DELETE, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def do_HEAD(self):
        self._xu_ly_request(chi_gui_header=True)

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        duong_dan = urllib.parse.unquote(parsed.path)

        # 1. API ping
        if duong_dan == "/ping":
            self._tra_ve_json(200, {"status": "ok", "app": "ai-trading-server"})
            return

        # 2. API run-status
        if duong_dan == "/api/run-status":
            self._tra_ve_json(200, RUNNER.get_status())
            return

        # 3. API reports
        if duong_dan == "/api/reports":
            self._tra_ve_json(200, lay_danh_sach_bao_cao())
            return

        self._xu_ly_request(chi_gui_header=False)

    def do_POST(self):
        parsed = urllib.parse.urlparse(self.path)
        duong_dan = urllib.parse.unquote(parsed.path)

        if duong_dan == "/api/delete":
            self._xu_ly_xoa()
            return

        if duong_dan == "/api/run":
            self._xu_ly_chay_phan_tich()
            return

        if duong_dan == "/api/run-cancel":
            ok, msg = RUNNER.cancel()
            self._tra_ve_json(200 if ok else 400, {"status": "ok" if ok else "error", "message": msg})
            return

        if duong_dan == "/api/git-pull":
            try:
                proc = subprocess.run(
                    ["git", "pull", "--rebase"],
                    cwd=str(GOC),
                    capture_output=True,
                    text=True,
                    timeout=30
                )
                if proc.returncode == 0:
                    self._tra_ve_json(200, {"status": "ok", "message": "Đã đồng bộ báo cáo từ GitHub thành công!"})
                else:
                    self._tra_ve_json(400, {"status": "error", "message": proc.stderr.strip() or "Chưa cấu hình Git remote hoặc có lỗi pull."})
            except Exception as e:
                self._tra_ve_json(500, {"status": "error", "message": f"Lỗi thực thi git: {e}"})
            return

        self.send_error(404, "Endpoint not found")

    def do_DELETE(self):
        parsed = urllib.parse.urlparse(self.path)
        duong_dan = urllib.parse.unquote(parsed.path)
        if duong_dan.startswith("/api/delete"):
            self._xu_ly_xoa()
            return
        self.send_error(404, "Endpoint not found")

    def _xu_ly_chay_phan_tich(self):
        body = self._doc_body_json()
        ma = body.get("ma", "")
        ngay = body.get("ngay", "")
        model = body.get("model", "gemini-3.8-flash-high")

        if not ma or not ngay:
            self._tra_ve_json(400, {"status": "error", "message": "Vui lòng cung cấp 'ma' và 'ngay'"})
            return

        ok, msg = RUNNER.start(ma, ngay, model)
        self._tra_ve_json(200 if ok else 400, {"status": "ok" if ok else "error", "message": msg})

    def _xu_ly_xoa(self):
        parsed = urllib.parse.urlparse(self.path)
        qs = urllib.parse.parse_qs(parsed.query)
        ten_tep = ""
        if "file" in qs and qs["file"]:
            ten_tep = qs["file"][0]
        else:
            body = self._doc_body_json()
            ten_tep = body.get("file", "")

        if not ten_tep:
            self._tra_ve_json(400, {"status": "error", "message": "Thiếu tham số 'file'"})
            return

        file_found = tim_file_bao_cao(ten_tep)
        if not file_found or not file_found.is_file():
            self._tra_ve_json(404, {"status": "error", "message": f"Không tìm thấy file: {ten_tep}"})
            return

        # Kiểm tra an toàn: File bắt buộc phải nằm trong THU_MUC_KQ
        try:
            file_found.resolve().relative_to(THU_MUC_KQ.resolve())
        except ValueError:
            self._tra_ve_json(403, {"status": "error", "message": "Từ chối truy cập: Không thể xoá file ngoài thư mục Kết quả"})
            return

        deleted_files = []
        try:
            file_found.unlink(missing_ok=True)
            deleted_files.append(file_found.name)

            # Xoá file đối ứng (.html <-> .md)
            if file_found.suffix.lower() == ".html":
                doi_ung = file_found.with_suffix(".md")
                if doi_ung.exists() and doi_ung.is_file():
                    doi_ung.unlink(missing_ok=True)
                    deleted_files.append(doi_ung.name)
            elif file_found.suffix.lower() == ".md":
                doi_ung = file_found.with_suffix(".html")
                if doi_ung.exists() and doi_ung.is_file():
                    doi_ung.unlink(missing_ok=True)
                    deleted_files.append(doi_ung.name)

            self._tra_ve_json(200, {
                "status": "ok",
                "message": "Đã xoá báo cáo thành công",
                "deleted": deleted_files
            })
        except Exception as e:
            self._tra_ve_json(500, {"status": "error", "message": f"Lỗi khi xoá file: {e}"})

    def _doc_body_json(self) -> dict:
        try:
            length = int(self.headers.get("Content-Length", 0))
            if length > 0:
                raw = self.rfile.read(length).decode("utf-8")
                return json.loads(raw)
        except Exception:
            pass
        return {}

    def _tra_ve_json(self, status_code: int, data: any):
        resp = json.dumps(data, ensure_ascii=False).encode("utf-8")
        self.send_response(status_code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(resp)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(resp)

    def _xu_ly_request(self, chi_gui_header: bool = False):
        parsed = urllib.parse.urlparse(self.path)
        duong_dan = urllib.parse.unquote(parsed.path)

        # Trang chủ Dashboard
        if duong_dan in ("/", "/index.html"):
            server_port = self.server.server_address[1]
            dashboard_html = tao_trang_dashboard_html(server_port)
            data = dashboard_html.encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            if not chi_gui_header:
                self.wfile.write(data)
            return

        # Tìm kiếm file báo cáo theo đường dẫn hoặc tên yêu cầu
        file_found = tim_file_bao_cao(duong_dan)

        # Nếu người dùng yêu cầu file .html nhưng chỉ mới có file .md, tự động convert sang .html
        if not file_found and duong_dan.endswith(".html"):
            duong_md = str(Path(duong_dan).with_suffix(".md"))
            md_found = tim_file_bao_cao(duong_md)
            if md_found:
                try:
                    from report_generator import chuyen_doi_md_sang_html
                    server_port = self.server.server_address[1]
                    file_found = chuyen_doi_md_sang_html(md_found, server_port=server_port)
                except Exception:
                    pass

        if file_found and file_found.is_file():
            no_cache = "tiến độ" in file_found.name.lower() or "tiến" in file_found.name.lower()
            self._gui_file(file_found, no_cache=no_cache, chi_gui_header=chi_gui_header)
            return

        # Không tìm thấy file
        self.send_error(404, f"Không tìm thấy file: {duong_dan}")

    def _gui_file(self, file_path: Path, no_cache: bool = False, chi_gui_header: bool = False):
        try:
            data = file_path.read_bytes()
            content_type = "text/html; charset=utf-8"
            if file_path.suffix.lower() == ".md":
                content_type = "text/markdown; charset=utf-8"
            elif file_path.suffix.lower() in (".json", ".jsonl"):
                content_type = "application/json; charset=utf-8"

            self.send_response(200)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(data)))
            if no_cache:
                self.send_header("Cache-Control", "no-cache, no-store, must-revalidate")
            self.end_headers()
            if not chi_gui_header:
                self.wfile.write(data)
        except Exception as e:
            self.send_error(500, f"Lỗi đọc file: {e}")


class ThreadedHTTPServer(socketserver.ThreadingMixIn, http.server.HTTPServer):
    daemon_threads = True
    allow_reuse_address = True


def is_port_in_use(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        return s.connect_ex(("127.0.0.1", port)) == 0


def ping_server(port: int, timeout: float = 0.5) -> bool:
    try:
        url = f"http://127.0.0.1:{port}/ping"
        req = urllib.request.Request(url, headers={"User-Agent": "AITradingPing/1.0"})
        with urllib.request.urlopen(req, timeout=timeout) as res:
            if res.status == 200:
                data = json.loads(res.read().decode("utf-8"))
                return data.get("app") == "ai-trading-server"
    except Exception:
        pass
    return False


def dam_bao_server_chay(port_khoi_dau: int = PORT_MAC_DINH, max_thu: int = 10) -> int:
    """Kiểm tra và tự động khởi động server cục bộ nếu chưa chạy."""
    for p in range(port_khoi_dau, port_khoi_dau + max_thu):
        if ping_server(p, timeout=0.3):
            return p

    port_chon = port_khoi_dau
    for p in range(port_khoi_dau, port_khoi_dau + max_thu):
        if not is_port_in_use(p):
            port_chon = p
            break

    py_bin = sys.executable
    script_path = str(GOC / "server.py")
    cmd = [py_bin, script_path, "--port", str(port_chon), "--daemon"]

    proc = subprocess.Popen(
        cmd,
        cwd=str(GOC),
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        start_new_session=True,
    )

    try:
        PID_FILE.write_text(str(proc.pid), encoding="utf-8")
    except Exception:
        pass

    t0 = time.time()
    while time.time() - t0 < 2.5:
        if ping_server(port_chon, timeout=0.2):
            return port_chon
        time.sleep(0.15)

    return port_chon


def mo_link_bao_cao(duong_dan_html: Path, port: int = PORT_MAC_DINH) -> str:
    """Khởi động server (nếu chưa chạy) và mở link localhost:port/ten_file.html trên trình duyệt."""
    active_port = dam_bao_server_chay(port)
    ten_tep = duong_dan_html.name
    url = f"http://localhost:{active_port}/{urllib.parse.quote(ten_tep)}"

    try:
        webbrowser.open(url)
    except Exception:
        if sys.platform == "darwin":
            subprocess.Popen(["open", url])
        elif shutil_which("xdg-open"):
            subprocess.Popen(["xdg-open", url])

    return url


def shutil_which(cmd: str):
    import shutil
    return shutil.which(cmd)


def main():
    parser = argparse.ArgumentParser(description="Máy chủ phục vụ báo cáo và giao diện AI Trading localhost")
    parser.add_argument("--port", "-p", type=int, default=PORT_MAC_DINH, help=f"Cổng HTTP (mặc định: {PORT_MAC_DINH})")
    parser.add_argument("--daemon", action="store_true", help="Chạy ở chế độ daemon background")
    parser.add_argument("--open", "-o", action="store_true", help="Tự động mở trình duyệt trang Dashboard")
    parser.add_argument("--stop", action="store_true", help="Dừng máy chủ đang chạy nền")
    parser.add_argument("--status", action="store_true", help="Kiểm tra trạng thái máy chủ")
    args = parser.parse_args()

    if args.stop:
        if PID_FILE.exists():
            try:
                pid = int(PID_FILE.read_text(encoding="utf-8").strip())
                os.kill(pid, 15)  # SIGTERM
                PID_FILE.unlink(missing_ok=True)
                print(f"Đã dừng máy chủ (PID: {pid}).")
            except Exception as e:
                print(f"Không thể dừng tiến trình: {e}")
        else:
            print("Không tìm thấy file PID của máy chủ.")
        return

    if args.status:
        for p in range(args.port, args.port + 5):
            if ping_server(p):
                print(f"✅ Máy chủ AI Trading đang chạy tại: http://localhost:{p}")
                return
        print("❌ Máy chủ AI Trading chưa chạy.")
        return

    server_address = ("0.0.0.0", args.port)
    try:
        httpd = ThreadedHTTPServer(server_address, ReportHTTPRequestHandler)
    except OSError as e:
        print(f"Lỗi: Không thể mở cổng {args.port}: {e}")
        sys.exit(1)

    url_home = f"http://localhost:{args.port}/"
    if not args.daemon:
        print("\n" + "=" * 65)
        print("   ⚡ MÁY CHỦ BÁO CÁO & ĐIỀU HÀNH AI TRADING (LOCAL SERVER)")
        print("=" * 65)
        print(f"   Trang chủ Dashboard:  {url_home}")
        print(f"   Giao diện:            Sáng (Light Mode) mặc định · Hỗ trợ Đổi Theme")
        print(f"   Tính năng:            Khởi chạy phân tích trực tiếp qua Web")
        print(f"   Thư mục báo cáo:      {THU_MUC_KQ}")
        print("=" * 65)
        print("   Nhấn Ctrl+C để dừng máy chủ.\n")

    if args.open:
        try:
            webbrowser.open(url_home)
        except Exception:
            pass

    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        if not args.daemon:
            print("\nĐã dừng máy chủ.")
    finally:
        httpd.server_close()


if __name__ == "__main__":
    main()
