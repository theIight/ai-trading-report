"""Bộ chuyển đổi và tạo file Báo cáo HTML chuyên nghiệp cho AI Trading.
Hỗ trợ hiển thị trực quan, phong cách Financial Dashboard, tự chứa (self-contained).
Giao diện sáng (Light Theme) mặc định, hỗ trợ đổi Sáng/Tối.
"""

from __future__ import annotations

import html
import re
from pathlib import Path
from typing import Optional

try:
    from markdown_it import MarkdownIt
    _MD = MarkdownIt("gfm-like", {"linkify": False, "html": True})
except Exception:
    _MD = None


CSS_TEMPLATE = """
:root {
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
  --accent-purple: #9333ea;
  --code-bg: #f8fafc;
  --card-shadow: 0 4px 14px rgba(0, 0, 0, 0.05);
}

[data-theme="dark"] {
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
  --accent-purple: #a855f7;
  --code-bg: #0d1117;
  --card-shadow: 0 10px 30px rgba(0, 0, 0, 0.2);
}

* { box-sizing: border-box; margin: 0; padding: 0; }
body {
  background-color: var(--bg-primary);
  color: var(--text-primary);
  font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
  line-height: 1.65;
  font-size: 15px;
  -webkit-font-smoothing: antialiased;
}

/* Header & Top Bar */
.topbar {
  position: sticky;
  top: 0;
  z-index: 100;
  background: rgba(255, 255, 255, 0.94);
  backdrop-filter: blur(12px);
  -webkit-backdrop-filter: blur(12px);
  border-bottom: 1px solid var(--border-color);
  padding: 12px 24px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.05);
}
[data-theme="dark"] .topbar {
  background: rgba(18, 23, 34, 0.92);
  box-shadow: none;
}

.brand-section {
  display: flex;
  align-items: center;
  gap: 12px;
}
.brand-logo {
  font-size: 22px;
  background: linear-gradient(135deg, #f59e0b, #ef4444);
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
  font-weight: 800;
  letter-spacing: -0.5px;
}
.brand-meta {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}

.top-actions {
  display: flex;
  align-items: center;
  gap: 8px;
}

.btn {
  display: inline-flex;
  align-items: center;
  gap: 6px;
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
}
.btn:hover {
  background: var(--bg-hover);
  border-color: var(--accent-blue);
}
.btn-primary {
  background: #2563eb;
  border-color: #1d4ed8;
  color: #fff;
  font-weight: 600;
}
.btn-primary:hover {
  background: #1d4ed8;
}
.btn-danger {
  background: rgba(239, 68, 68, 0.1);
  border-color: rgba(239, 68, 68, 0.25);
  color: #dc2626;
  font-weight: 500;
}
.btn-danger:hover {
  background: #dc2626;
  border-color: #b91c1c;
  color: #fff;
}
[data-theme="dark"] .btn-danger {
  background: rgba(239, 68, 68, 0.15);
  border-color: rgba(239, 68, 68, 0.35);
  color: #f87171;
}

/* Badges */
.badge {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  padding: 4px 10px;
  border-radius: 9999px;
  font-size: 12px;
  font-weight: 600;
  letter-spacing: 0.3px;
}
.badge-buy {
  background: rgba(16, 185, 129, 0.12);
  color: #047857;
  border: 1px solid rgba(16, 185, 129, 0.25);
}
.badge-sell {
  background: rgba(239, 68, 68, 0.12);
  color: #b91c1c;
  border: 1px solid rgba(239, 68, 68, 0.25);
}
.badge-hold {
  background: rgba(245, 158, 11, 0.12);
  color: #b45309;
  border: 1px solid rgba(245, 158, 11, 0.25);
}
.badge-info {
  background: var(--bg-secondary);
  color: var(--text-secondary);
  border: 1px solid var(--border-color);
}
[data-theme="dark"] .badge-buy {
  background: rgba(16, 185, 129, 0.15);
  color: #34d399;
  border-color: rgba(16, 185, 129, 0.3);
}
[data-theme="dark"] .badge-sell {
  background: rgba(239, 68, 68, 0.15);
  color: #f87171;
  border-color: rgba(239, 68, 68, 0.3);
}
[data-theme="dark"] .badge-hold {
  background: rgba(245, 158, 11, 0.15);
  color: #fbbf24;
  border-color: rgba(245, 158, 11, 0.3);
}

/* Layout */
.container {
  max-width: 1080px;
  margin: 0 auto;
  padding: 32px 20px 80px 20px;
}

/* Hero Section */
.hero-card {
  background: var(--bg-card);
  border: 1px solid var(--border-color);
  border-radius: 16px;
  padding: 28px;
  margin-bottom: 24px;
  box-shadow: var(--card-shadow);
}
[data-theme="dark"] .hero-card {
  background: linear-gradient(180deg, var(--bg-card) 0%, var(--bg-secondary) 100%);
}

.hero-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  flex-wrap: wrap;
  gap: 16px;
  margin-bottom: 18px;
}
.hero-title-group h1 {
  font-size: 28px;
  font-weight: 800;
  color: var(--text-primary);
  margin-bottom: 4px;
}
.hero-subtitle {
  color: var(--text-secondary);
  font-size: 14px;
}

.hero-stats {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
  gap: 14px;
  margin-top: 18px;
  padding-top: 18px;
  border-top: 1px solid var(--border-color);
}
.stat-box {
  background: var(--bg-secondary);
  padding: 12px 16px;
  border-radius: 10px;
  border: 1px solid var(--border-color);
}
.stat-label {
  font-size: 12px;
  color: var(--text-muted);
  text-transform: uppercase;
  letter-spacing: 0.5px;
  margin-bottom: 4px;
}
.stat-value {
  font-size: 18px;
  font-weight: 700;
  color: var(--text-primary);
}

/* Table of Contents */
.toc-bar {
  background: var(--bg-card);
  border: 1px solid var(--border-color);
  border-radius: 12px;
  padding: 12px 18px;
  margin-bottom: 28px;
  display: flex;
  align-items: center;
  gap: 10px;
  overflow-x: auto;
  white-space: nowrap;
  box-shadow: var(--card-shadow);
}
.toc-title {
  font-size: 12px;
  font-weight: 700;
  text-transform: uppercase;
  color: var(--text-muted);
  letter-spacing: 0.5px;
}
.toc-link {
  color: var(--text-secondary);
  text-decoration: none;
  font-size: 13px;
  padding: 4px 10px;
  border-radius: 6px;
  transition: all 0.15s;
}
.toc-link:hover {
  background: var(--bg-hover);
  color: var(--accent-blue);
}

/* Article Body */
.report-content {
  background: var(--bg-card);
  border: 1px solid var(--border-color);
  border-radius: 16px;
  padding: 36px 40px;
  box-shadow: var(--card-shadow);
}
@media (max-width: 768px) {
  .report-content { padding: 20px; }
}

.report-content h1,
.report-content h2,
.report-content h3,
.report-content h4 {
  color: var(--text-primary);
  margin-top: 36px;
  margin-bottom: 16px;
  font-weight: 700;
  line-height: 1.3;
}
.report-content h1 { font-size: 26px; border-bottom: 2px solid var(--border-color); padding-bottom: 12px; }
.report-content h2 {
  font-size: 20px;
  display: flex;
  align-items: center;
  gap: 8px;
  padding-left: 12px;
  border-left: 4px solid var(--accent-blue);
  background: linear-gradient(90deg, rgba(2, 132, 199, 0.08) 0%, transparent 100%);
  padding-top: 6px;
  padding-bottom: 6px;
  border-radius: 0 8px 8px 0;
}
.report-content h3 { font-size: 17px; color: var(--accent-gold); }
.report-content p { margin-bottom: 16px; }
.report-content ul, .report-content ol {
  margin-bottom: 18px;
  padding-left: 24px;
}
.report-content li { margin-bottom: 6px; }
.report-content strong { color: var(--text-primary); font-weight: 700; }

.report-content hr {
  border: 0;
  height: 1px;
  background: var(--border-color);
  margin: 32px 0;
}

/* Tables */
.report-content table {
  width: 100%;
  border-collapse: collapse;
  margin: 20px 0;
  font-size: 14px;
  border-radius: 10px;
  overflow: hidden;
  border: 1px solid var(--border-color);
}
.report-content th {
  background: var(--bg-secondary);
  color: var(--text-primary);
  font-weight: 600;
  text-align: left;
  padding: 12px 14px;
  border-bottom: 2px solid var(--border-color);
}
.report-content td {
  padding: 10px 14px;
  border-bottom: 1px solid var(--border-color);
  color: var(--text-secondary);
}
.report-content tr:nth-child(even) td {
  background: rgba(0, 0, 0, 0.02);
}
[data-theme="dark"] .report-content tr:nth-child(even) td {
  background: rgba(255, 255, 255, 0.02);
}
.report-content tr:hover td {
  background: var(--bg-hover);
  color: var(--text-primary);
}

/* Code & Pre */
.report-content code {
  background: var(--code-bg);
  color: #e11d48;
  padding: 2px 6px;
  border-radius: 4px;
  font-size: 13px;
  font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
  border: 1px solid var(--border-color);
}
[data-theme="dark"] .report-content code {
  color: #ff7b72;
}

.report-content pre {
  background: var(--code-bg);
  padding: 16px;
  border-radius: 10px;
  overflow-x: auto;
  border: 1px solid var(--border-color);
  margin: 18px 0;
}
.report-content pre code {
  background: transparent;
  padding: 0;
  border: none;
  color: inherit;
}

/* Alert Callouts */
.alert {
  padding: 14px 18px;
  border-radius: 10px;
  margin: 20px 0;
  border-left: 4px solid;
  line-height: 1.6;
}
.alert p:last-child { margin-bottom: 0; }
.alert-note {
  background: #eff6ff;
  border-color: var(--accent-blue);
  color: #1e40af;
}
[data-theme="dark"] .alert-note {
  background: rgba(56, 189, 248, 0.1);
  color: #bae6fd;
}
.alert-important {
  background: #faf5ff;
  border-color: var(--accent-purple);
  color: #6b21a8;
}
[data-theme="dark"] .alert-important {
  background: rgba(168, 85, 247, 0.12);
  color: #e9d5ff;
}
.alert-warning {
  background: #fffbeb;
  border-color: var(--accent-gold);
  color: #92400e;
}
[data-theme="dark"] .alert-warning {
  background: rgba(245, 158, 11, 0.12);
  color: #fde68a;
}
.alert-caution {
  background: #fef2f2;
  border-color: var(--accent-red);
  color: #991b1b;
}
[data-theme="dark"] .alert-caution {
  background: rgba(239, 68, 68, 0.12);
  color: #fecaca;
}

/* Footer */
.footer {
  text-align: center;
  color: var(--text-muted);
  font-size: 13px;
  margin-top: 40px;
  padding-top: 20px;
  border-top: 1px solid var(--border-color);
}

/* Toast */
#toast {
  position: fixed;
  bottom: 24px;
  right: 24px;
  background: #10b981;
  color: #fff;
  padding: 10px 18px;
  border-radius: 8px;
  font-size: 13px;
  font-weight: 600;
  box-shadow: 0 4px 12px rgba(0,0,0,0.3);
  display: none;
  z-index: 1000;
}

@media print {
  .topbar, .toc-bar, .top-actions, .footer, #toast { display: none !important; }
  body { background: #fff !important; color: #000 !important; }
  .report-content, .hero-card { border: none !important; box-shadow: none !important; padding: 0 !important; }
}
"""

JS_TEMPLATE = """
function toggleTheme() {
  const current = document.documentElement.getAttribute('data-theme') || 'light';
  const target = current === 'dark' ? 'light' : 'dark';
  document.documentElement.setAttribute('data-theme', target);
  localStorage.setItem('ai_trading_theme', target);
}

function copyReportLink() {
  navigator.clipboard.writeText(window.location.href).then(() => {
    const toast = document.getElementById('toast');
    toast.style.display = 'block';
    setTimeout(() => { toast.style.display = 'none'; }, 2500);
  });
}

function xoaBaoCaoHienTai() {
  const parts = window.location.pathname.split('/');
  const tenFile = decodeURIComponent(parts[parts.length - 1] || '');
  if (!confirm(`Bạn có chắc chắn muốn xoá vĩnh viễn báo cáo này?\\n"${tenFile}"?\\n\\n(Thao tác này sẽ xoá cả file HTML và Markdown tương ứng)`)) {
    return;
  }
  fetch('/api/delete?file=' + encodeURIComponent(tenFile), {
    method: 'POST'
  })
  .then(res => res.json())
  .then(data => {
    if (data.status === 'ok') {
      alert('Đã xoá báo cáo thành công. Hệ thống sẽ quay về trang danh sách.');
      window.location.href = '/';
    } else {
      alert('Lỗi: ' + (data.message || 'Không thể xoá báo cáo'));
    }
  })
  .catch(err => {
    alert('Lỗi kết nối tới máy chủ: ' + err);
  });
}

// Khởi tạo theme: Mặc định Light nếu chưa chọn
(function() {
  const saved = localStorage.getItem('ai_trading_theme') || 'light';
  document.documentElement.setAttribute('data-theme', saved);
})();
"""


def _chuan_hoa_markdown(md_text: str) -> str:
    """Xử lý định dạng GitHub alerts như [!IMPORTANT], [!NOTE] trước khi parse."""
    dong = md_text.splitlines()
    ket_qua = []
    i = 0
    while i < len(dong):
        d = dong[i]
        m = re.match(r"^>\s*\[!(NOTE|IMPORTANT|WARNING|TIP|CAUTION)\]", d.strip(), re.IGNORECASE)
        if m:
            alert_type = m.group(1).lower()
            if alert_type == "tip":
                alert_type = "note"
            noi_dung_alert = []
            i += 1
            while i < len(dong) and dong[i].strip().startswith(">"):
                dong_alert = re.sub(r"^>\s?", "", dong[i])
                noi_dung_alert.append(dong_alert)
                i += 1
            nd_text = "<br>".join(html.escape(line) for line in noi_dung_alert if line.strip())
            ket_qua.append(f'<div class="alert alert-{alert_type}">{nd_text}</div>\n')
            continue
        ket_qua.append(d)
        i += 1
    return "\n".join(ket_qua)


def render_markdown_to_html(md_text: str) -> str:
    """Chuyển đổi chuỗi markdown sang HTML."""
    chuan_hoa = _chuan_hoa_markdown(md_text)
    if _MD is not None:
        return _MD.render(chuan_hoa)

    # Fallback đơn giản nếu không có thư viện
    out = []
    for line in chuan_hoa.splitlines():
        if line.startswith("# "):
            out.append(f"<h1>{html.escape(line[2:])}</h1>")
        elif line.startswith("## "):
            out.append(f"<h2>{html.escape(line[3:])}</h2>")
        elif line.startswith("### "):
            out.append(f"<h3>{html.escape(line[4:])}</h3>")
        elif line.startswith("- "):
            out.append(f"<li>{html.escape(line[2:])}</li>")
        elif line.strip() == "---":
            out.append("<hr>")
        elif line.strip():
            out.append(f"<p>{html.escape(line)}</p>")
    return "\n".join(out)


def _xac_dinh_rating_badge(rating: str) -> tuple[str, str]:
    """Trả về (class_css, nhãn_hiển_thị) cho rating."""
    r_up = (rating or "").upper()
    if "BUY" in r_up or "MUA" in r_up:
        return "badge-buy", "🟢 " + (rating or "BUY")
    elif "SELL" in r_up or "BÁN" in r_up:
        return "badge-sell", "🔴 " + (rating or "SELL")
    elif "HOLD" in r_up or "QUAN SÁT" in r_up or "TRUNG LẬP" in r_up:
        return "badge-hold", "🟡 " + (rating or "HOLD")
    return "badge-info", "⚪ " + (rating or "CHƯA XÁC ĐỊNH")


def trich_xuat_thong_tin(md_text: str) -> dict:
    """Trích xuất thông tin cơ bản từ Markdown biên bản."""
    info = {
        "ma": "",
        "ngay": "",
        "rating": "",
        "model": "",
        "phut": "",
    }
    first_lines = md_text.splitlines()[:5]
    for fl in first_lines:
        m_ma = re.search(r"(?:BIÊN BẢN PHÂN TÍCH|Biên bản phân tích).*?[:\s]\s*([A-Za-z0-9\-_=\^]{2,15})(?:\s+ngày|\s*$)", fl, re.IGNORECASE)
        if m_ma:
            info["ma"] = m_ma.group(1).strip()
            break

    m_ngay = re.search(r"(?:Ngày phân tích|ngày)[:\s*]+([0-9]{4}-[0-9]{2}-[0-9]{2})", md_text)
    if m_ngay:
        info["ngay"] = m_ngay.group(1).strip()

    m_rat = re.search(r"(?:Xếp hạng khuyến nghị|rating)[:\s*]+([^\n\r·]+)", md_text, re.IGNORECASE)
    if m_rat:
        info["rating"] = m_rat.group(1).replace("*", "").strip()

    m_mod = re.search(r"(?:Bộ não AI|Model)[:\s*]+`?([a-zA-Z0-9\.\-_]+)`?", md_text, re.IGNORECASE)
    if m_mod:
        info["model"] = m_mod.group(1).strip()

    m_phut = re.search(r"(?:Thời gian chạy|Thời gian thực thi)[:\s*]+([0-9\.]+)\s*phút", md_text, re.IGNORECASE)
    if m_phut:
        info["phut"] = m_phut.group(1).strip()

    return info


def tao_trang_bao_cao_html(
    md_content: str,
    ma: Optional[str] = None,
    ngay: Optional[str] = None,
    rating: Optional[str] = None,
    model: Optional[str] = None,
    phut: Optional[float] = None,
    server_port: int = 5050
) -> str:
    """Tạo toàn bộ tài liệu HTML hoàn chỉnh từ nội dung Markdown."""
    trich = trich_xuat_thong_tin(md_content)
    ma = ma or trich.get("ma") or "TAI_SAN"
    ngay = ngay or trich.get("ngay") or ""
    rating = rating or trich.get("rating") or "TRUNG LẬP"
    model = model or trich.get("model") or "Gemini Multi-Agent"
    phut_str = f"{phut:.1f}" if phut is not None else (trich.get("phut") or "—")

    badge_class, badge_label = _xac_dinh_rating_badge(rating)
    html_body = render_markdown_to_html(md_content)

    # Thêm anchor ID cho các thẻ h2 để làm Table of Contents
    h2_matches = list(re.finditer(r"<h2>(.*?)</h2>", html_body))
    toc_links = []
    offset = 0
    modified_body = html_body

    for idx, match in enumerate(h2_matches):
        raw_title = match.group(1)
        clean_title = re.sub(r"<[^>]+>", "", raw_title).strip()
        sec_id = f"muc_{idx + 1}"
        new_tag = f'<h2 id="{sec_id}">{raw_title}</h2>'
        start, end = match.start() + offset, match.end() + offset
        modified_body = modified_body[:start] + new_tag + modified_body[end:]
        offset += len(new_tag) - (end - start)
        toc_links.append(f'<a class="toc-link" href="#{sec_id}">{clean_title}</a>')

    toc_html = ""
    if toc_links:
        toc_html = f"""
        <div class="toc-bar">
          <span class="toc-title">Điều hướng:</span>
          {''.join(toc_links)}
        </div>
        """

    return f"""<!doctype html>
<html lang="vi" data-theme="light">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Báo cáo Phân tích {html.escape(ma)} ({html.escape(ngay)}) · AI Trading</title>
  <style>{CSS_TEMPLATE}</style>
</head>
<body>

  <!-- Top Navigation Bar -->
  <header class="topbar">
    <div class="brand-section">
      <a href="/" class="brand-logo" style="text-decoration:none;">⚡ AI TRADING</a>
      <div class="brand-meta">
        <span class="badge {badge_class}">{html.escape(badge_label)}</span>
        <span class="badge badge-info">📅 {html.escape(ngay)}</span>
      </div>
    </div>
    <div class="top-actions">
      <a href="/" class="btn" title="Về trang tổng hợp">🏠 Danh sách</a>
      <button class="btn" onclick="copyReportLink()" title="Sao chép link mở trên trình duyệt">📋 Sao chép link</button>
      <button class="btn btn-primary" onclick="window.print()" title="In ra giấy hoặc lưu thành PDF">🖨️ Xuất PDF</button>
      <button class="btn" onclick="toggleTheme()" title="Đổi giao diện Sáng / Tối">🌓 Giao diện</button>
      <button class="btn btn-danger" onclick="xoaBaoCaoHienTai()" title="Xoá vĩnh viễn báo cáo này">🗑️ Xoá</button>
    </div>
  </header>

  <main class="container">
    <!-- Hero Summary Card -->
    <div class="hero-card">
      <div class="hero-header">
        <div class="hero-title-group">
          <h1>Báo Cáo Phân Tích: {html.escape(ma)}</h1>
          <div class="hero-subtitle">
            Hệ sinh thái Đa Tác tử (Multi-Agent System) · Thẩm định tự động & Toàn diện
          </div>
        </div>
        <div>
          <span class="badge {badge_class}" style="font-size:14px; padding: 6px 14px;">{html.escape(badge_label)}</span>
        </div>
      </div>

      <div class="hero-stats">
        <div class="stat-box">
          <div class="stat-label">Mã tài sản</div>
          <div class="stat-value">{html.escape(ma)}</div>
        </div>
        <div class="stat-box">
          <div class="stat-label">Ngày phân tích</div>
          <div class="stat-value">{html.escape(ngay)}</div>
        </div>
        <div class="stat-box">
          <div class="stat-label">Bộ não AI</div>
          <div class="stat-value" style="font-size:14px; word-break:break-all;">{html.escape(model)}</div>
        </div>
        <div class="stat-box">
          <div class="stat-label">Thời gian phân tích</div>
          <div class="stat-value">{html.escape(phut_str)} phút</div>
        </div>
      </div>
    </div>

    <!-- Table of Contents -->
    {toc_html}

    <!-- Main Content -->
    <article class="report-content">
      {modified_body}
    </article>

    <footer class="footer">
      <p>Báo cáo được khởi tạo tự động bởi <b>AI Trading Multi-Agent</b> · Cổng máy chủ cục bộ <code>localhost:{server_port}</code></p>
      <p style="margin-top:6px; font-size:12px;">Dữ liệu phân tích chỉ nhằm mục đích nghiên cứu học tập, không cấu thành lời khuyên đầu tư tài chính.</p>
    </footer>
  </main>

  <div id="toast">✅ Đã sao chép link báo cáo vào bộ nhớ tạm!</div>

  <script>{JS_TEMPLATE}</script>
</body>
</html>
"""


def chuyen_doi_md_sang_html(
    tep_md: Path,
    tep_html: Optional[Path] = None,
    server_port: int = 5050
) -> Path:
    """Chuyển đổi một file .md có sẵn thành file .html tương ứng."""
    if not tep_md.exists():
        raise FileNotFoundError(f"Không tìm thấy file: {tep_md}")

    if tep_html is None:
        tep_html = tep_md.with_suffix(".html")

    noi_dung_md = tep_md.read_text(encoding="utf-8")
    html_content = tao_trang_bao_cao_html(noi_dung_md, server_port=server_port)
    tep_html.write_text(html_content, encoding="utf-8")
    return tep_html
