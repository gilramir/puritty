import re, sys
src = open('/home/gram/prj/puritty/vt/src/Vt/Charset.geng').read().split('\n')
first, last = 81, 126
lines = src[first-1:last]
assert not any('puritty' in l for l in lines)
E='\\e'
def fg(h): return f'{E}[38;2;{int(h[0:2],16)};{int(h[2:4],16)};{int(h[4:6],16)}m'
def bg(h): return f'{E}[48;2;{int(h[0:2],16)};{int(h[2:4],16)};{int(h[4:6],16)}m'
C=dict(text='c5c8c6', kw='b294bb', type='f0c674', num='de935f', str='b5bd68', com='969896', op='8abeb7', defn='81a2be', field='cc6666', punc='c5c8c6')
KW={'let','in','if','then','else','when','is','type','alias','module','import','exposing','as','moved'}
tok = re.compile(r'(?P<com>--.*$)|(?P<str>"[^"]*")|(?P<num>0x[0-9A-Fa-f]+|\d+)|(?P<word>[A-Za-z_][A-Za-z0-9_.]*)|(?P<op>[-+*/<>=|&]+|//)|(?P<other>.)')
incomment=False
def hl(line, defs):
    global incomment
    out=''
    if incomment or line.lstrip().startswith('{-|') or line.lstrip().startswith('{-'):
        if '-}' in line: incomment=False
        else: incomment=True
        return fg(C['com'])+f'{E}[3m'+line+f'{E}[23m'
    first=True
    for m in tok.finditer(line):
        k=m.lastgroup; t=m.group()
        if k=='com': out+=fg(C['com'])+f'{E}[3m'+t+f'{E}[23m'
        elif k=='str': out+=fg(C['str'])+t
        elif k=='num': out+=fg(C['num'])+t
        elif k=='word':
            if t in KW: out+=fg(C['kw'])+t
            elif t[0].isupper(): out+=fg(C['type'])+t
            elif first and line[0]!=' ' : out+=fg(C['defn'])+t
            else: out+=fg(C['text'])+t
        elif k=='op': out+=fg(C['op'])+t
        else: out+=fg(C['punc'])+t
        if k!='other' or t!=' ': first=False if k=='word' else first
    return out
cur = 104  # cursor line in file numbering
cols = 106
rows=[]
for i,l in enumerate(lines):
    n=first+i
    iscur = n==cur
    base = bg('282a2e') if iscur else bg('1d1f21')
    num = (fg('f0c674') if iscur else fg('5c6066'))+f'{n:>4} '
    body = hl(l, None)
    rows.append(base+num+body+f'{E}[K'+f'{E}[0m')
status = bg('81a2be')+fg('1d1f21')+f'{E}[1m NORMAL {E}[22m'+bg('373b41')+fg('c5c8c6')+' vt/src/Vt/Charset.geng '
right = ' geng │ utf-8 │ 104:12 │ 43% '
status += bg('282a2e')+' '*(cols-8-len(' vt/src/Vt/Charset.geng ')-len(right))+bg('373b41')+fg('c5c8c6')+right+f'{E}[0m'
rows.append(status)
rows.append(fg('969896')+'"vt/src/Vt/Charset.geng" 242L, 7480B'+f'{E}[0m')
# position cursor at line 104 col 13 (after the number gutter of 5)
crow = cur-first+1; ccol = 5+12
body='\\r\\n'.join(rows)+f'{E}[{crow};{ccol}H'
sys.stdout.write(f'size {cols}x{len(rows)} font="Fira Code" points=13 lang=ko\n{body}\n')
