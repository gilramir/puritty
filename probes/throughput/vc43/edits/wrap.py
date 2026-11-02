import os, sys; sys.path.insert(0, os.path.dirname(os.path.abspath(__file__))); from edits import ed
ed('Vt.geng', '''printAscii bytes n i b t0 =
    let
        t =
            wrapped t0
''', '''printAscii bytes n i b t0 =
    let
        t =
            if t0.wrapNext then
                wrapNow t0

            else
                t0
''')
