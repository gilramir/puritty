import os, sys; sys.path.insert(0, os.path.dirname(os.path.abspath(__file__))); from edits import ed
s=open('Vt.geng').read()
a=s.index('printAscii : Bytes')
b=s.index('\n\n\n', a)
f=s[a:b]
g=f.replace('printAscii', 'printAsciiPlain')
old_t='''        t =
            wrapped t0
'''
new_t='''        t =
            if t0.wrapNext then
                wrapNow t0

            else
                t0
'''
assert g.count(old_t)==1; g=g.replace(old_t,new_t)
i=g.index('        -- tested only once a spacer head')
j=g.index('    in\n', i)
g=g[:i].rstrip('\n')+'\n'+g[j:]
old_s='screen = unheadIf stale t.y { s | cells ='
assert g.count(old_s)==1
g=g.replace(old_s,'screen = { s | cells =')
s=s[:b]+'\n\n\n{-| `printAscii` before any spacer head was written: no `stale` test, and\n`plain` says autowrap is on. -}\n'+g+s[b:]
old_c='''            if t.plain then
                printAscii bytes n i b t
'''
new_c='''            if t.plain then
                if t.heads then
                    printAscii bytes n i b t

                else
                    printAsciiPlain bytes n i b t
'''
assert s.count(old_c)==1; s=s.replace(old_c,new_c)
open('Vt.geng','w').write(s)
