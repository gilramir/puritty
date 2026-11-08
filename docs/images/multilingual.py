import unicodedata, sys
def w(s):
    n=0
    for ch in s:
        if unicodedata.category(ch) in ('Mn','Me','Cf'): continue
        n += 2 if unicodedata.east_asian_width(ch) in ('W','F') else 1
    return n
def pad(s,n): return s+' '*(n-w(s))
E='\\e'
def sgr(c): return f'{E}[{c}m'
R=sgr(0)
lines=[]
def prompt(cmd):
    return f'{sgr("1;32")}you@desktop{R}:{sgr("1;34")}~/여행/travel{R}$ {cmd}'
lines.append(prompt('ls'))
items=[(sgr('1;34'),'写真/'),(sgr('1;34'),'지도/'),('', '旅程表.txt'),('', 'บันทึก.md'),(sgr('1;32'),'予約.sh'),('', 'README.md')]
lines.append('  '.join(c+t+(R if c else '') for c,t in items))
lines.append(prompt('cat greetings.txt'))
rows=[('Language','Hello','Thank you'),
      ('한국어','안녕하세요','감사합니다'),
      ('日本語','こんにちは','ありがとう'),
      ('中文','你好','谢谢'),
      ('ไทย','สวัสดีครับ','ขอบคุณครับ'),
      ('English','Hello','Thank you')]
widths=[max(w(r[i]) for r in rows)+2 for i in range(3)]
H='─'
lines.append('┌'+'┬'.join(H*x for x in widths)+'┐')
for k,r in enumerate(rows):
    cells=[]
    for i,c in enumerate(r):
        txt=' '+pad(c,widths[i]-1)
        if k==0: txt=' '+sgr('1;33')+c+R+' '*(widths[i]-1-w(c))
        elif i==0: txt=' '+sgr('36')+c+R+' '*(widths[i]-1-w(c))
        cells.append(txt)
    lines.append('│'+'│'.join(cells)+'│')
    if k==0: lines.append('├'+'┼'.join(H*x for x in widths)+'┤')
lines.append('└'+'┴'.join(H*x for x in widths)+'┘')
lines.append(prompt('git log --oneline -4'))
log=[('3f9a2c1','지도: 부산 해운대 경로 추가'),('b81e07d','旅程表: 京都の二日目を更新'),('6c4d5e2','บันทึก: เพิ่มร้านอาหารในเชียงใหม่'),('0a7f3b9','README: 上海行程说明')]
for h,m in log: lines.append(f'{sgr("33")}{h}{R} {m}')
lines.append(prompt('▏'.replace('▏','')))
cols=max(w(__import__('re').sub(r'\\e\[[0-9;]*m','',l)) for l in lines)+4
body='\\r\\n'.join(lines)
sys.stdout.write(f'size {cols}x{len(lines)+1} font="Fira Code" points=15 lang=ja\n{body}\n')
