"""Inputs for the font survey (docs/phase2-window.md §13), seeded:
   cjk.txt   20,000 lines of 70 ideographs and kana, from 6,000 distinct
             code points, so a screen is mostly glyphs not seen before
   thai.txt  20,000 lines of Thai words with stacked marks
usage: gen.py DIR"""
import random, sys, os
r = random.Random(1045)
d = sys.argv[1]
han = [chr(0x4E00 + i) for i in r.sample(range(0x5000), 6000)]
kana = [chr(c) for c in range(0x3041, 0x3097)]
with open(os.path.join(d, "cjk.txt"), "w") as f:
    for _ in range(20000):
        f.write("".join(r.choice(han) if r.random() < 0.7 else r.choice(kana) for _ in range(70)) + "\n")
words = ["กี้", "ปั๊ม", "น้ำ", "ภาษาไทย", "สวัสดีครับ", "ผู้ใหญ่", "กำลัง", "ญุ", "ฐุ", "ที่", "เป็น", "ไม่", "ได้", "จะ", "มี", "ให้", "แล้ว", "ความ"]
with open(os.path.join(d, "thai.txt"), "w") as f:
    for _ in range(20000):
        line = ""
        while True:
            w = r.choice(words)
            if len(line) + len(w) + 1 > 150:
                break
            line += w + " "
        f.write(line + "\n")
