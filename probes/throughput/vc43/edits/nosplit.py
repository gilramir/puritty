import os, sys; sys.path.insert(0, os.path.dirname(os.path.abspath(__file__))); from edits import ed
ed('Vt.geng', '''        cut =
            if x < old then
                splitWide erase o x xEnd old cells

            else
                cells''', '''        cut =
            cells''')
