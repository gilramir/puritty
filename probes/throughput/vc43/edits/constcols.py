import os, sys; sys.path.insert(0, os.path.dirname(os.path.abspath(__file__))); from edits import ed
ed('Vt.geng', '''        t =
            wrapped t0

        cols =
            t.cols

        end =
            asciiEnd''', '''        t =
            wrapped t0

        cols =
            160

        end =
            asciiEnd''')
ed('Vt/Screen.geng', '''rowOffset s y =
    phys s y * s.stride''', '''rowOffset s y =
    phys s y * 161''')
