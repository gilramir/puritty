import os, sys; sys.path.insert(0, os.path.dirname(os.path.abspath(__file__))); from edits import ed
ed('Vt.geng', '''            t.heads && t.x <= 1 && t.y > 0 && (cellWide (peekCell o 0 s)''', '''            False && t.heads && t.x <= 1 && t.y > 0 && (cellWide (peekCell o 0 s)''')
