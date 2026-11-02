import os, sys; sys.path.insert(0, os.path.dirname(os.path.abspath(__file__))); from edits import ed
ed('Vt.geng', '''        if b >= 0x20 && b < 0x7F then
            if t.plain then
                printAscii bytes n i b t''', '''        if b >= 0x20 && b < 0x7F then
            if True then
                printAscii bytes n i b t''')
