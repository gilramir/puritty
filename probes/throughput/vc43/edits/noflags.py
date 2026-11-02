import os, sys; sys.path.insert(0, os.path.dirname(os.path.abspath(__file__))); from edits import ed
ed('Vt.geng', '''    Builder.set (o + cols) (Bitwise.or (Bitwise.and rowFlags m) (Int64.fromInt (max xEnd old))) (writeAscii''', '''    Builder.set (o + cols) (Int64.fromInt (max xEnd old)) (writeAscii''')
