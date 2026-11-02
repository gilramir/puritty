import os, sys; sys.path.insert(0, os.path.dirname(os.path.abspath(__file__))); from edits import ed
ed('Vt.geng', '''            , wrapNext = x >= cols
            , lastPoint =
                if end == i + 1 then
                    b

                else
                    byteAt bytes (end - 1)
        }''', '''            , wrapNext = x >= cols
        }''')
