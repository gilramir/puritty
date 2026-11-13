"""The panes' text for tmux-on-windows.png (README.md beside it): Chinese
(李白's 静夜思, 王之涣's 登鹳雀楼, a table) and Thai, as zh.ans and th.ans in
the directory named."""
import unicodedata, sys
from pathlib import Path
D = Path(sys.argv[1])
E = "\x1b["
def sgr(*c): return E + ";".join(map(str, c)) + "m"
R = sgr(0)
def w(s):
    return sum(0 if unicodedata.category(ch) in ("Mn", "Me", "Cf") else (2 if unicodedata.east_asian_width(ch) in ("W", "F") else 1) for ch in s)
title, dim, accent = sgr(1, 33), sgr(2, 3), sgr(1, 36)
curly = E + "4:3m" + E + "58:2::120:200:255m"
zh = ["",
      f" {title}静夜思{R}  {dim}李白{R}",
      "",
      "   床前明月光，",
      "   疑是地上霜。",
      f"   举头望{curly}明月{R}，",
      "   低头思故乡。",
      "",
      f" {title}登鹳雀楼{R}  {dim}王之涣{R}",
      "",
      "   白日依山尽，黄河入海流。",
      f"   欲穷千里目，{sgr(1,36)}更上一层楼。{R}",
      "",
      f" {accent}天气{R}  {dim}全角字符，整齐对齐{R}"]
rows = [("城市", "天空", "气温"), ("北京", "晴 ☀", "16°C"), ("上海", "多云 ⛅", "20°C"), ("台北", "小雨 🌧", "23°C")]
ws = [max(w(r[i]) for r in rows) + 2 for i in range(3)]
zh.append("   ┌" + "┬".join("─" * x for x in ws) + "┐")
for k, r in enumerate(rows):
    cells = []
    for i, c in enumerate(r):
        st = sgr(1, 33) if k == 0 else (sgr(36) if i == 0 else "")
        cells.append(" " + st + c + (R if st else "") + " " * (ws[i] - 1 - w(c)))
    zh.append("   │" + "│".join(cells) + "│")
    if k == 0:
        zh.append("   ├" + "┼".join("─" * x for x in ws) + "┤")
zh.append("   └" + "┴".join("─" * x for x in ws) + "┘")
zh.append("")
(D / "zh.ans").write_text("\r\n".join(zh) + "\r\n")
th = [f" {title}สวัสดีครับ{R} 🙏  {dim}ภาษาไทย, shaped as it should be{R}",
      "",
      f" {accent}สุภาษิต{R}",
      "   น้ำขึ้นให้รีบตัก",
      "   ช้า ๆ ได้พร้าเล่มงาม",
      f"   {sgr(3)}ไม่มีใครแก่เกินเรียน{R}",
      "",
      f" {accent}เมนู{R}  ต้มยำกุ้ง · ผัดไทย · ส้มตำ · ข้าวเหนียวมะม่วง",
      ""]
(D / "th.ans").write_text("\r\n".join(th) + "\r\n")
