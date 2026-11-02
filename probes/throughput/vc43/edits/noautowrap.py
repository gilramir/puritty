import os, sys; sys.path.insert(0, os.path.dirname(os.path.abspath(__file__))); from edits import ed
ed('Vt.geng', '''wrapped t =
    if t.wrapNext && t.autowrap then''', '''wrapped t =
    if t.wrapNext then''')
