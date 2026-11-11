#!/usr/bin/env python3
"""src/Fixtures.geng from data/*.raw: each recorded session (record.sh) as
a Bytes value, so that the tests read no files."""
from pathlib import Path
here = Path(__file__).resolve().parent
out = ["module Fixtures exposing (..)", "",
       "{-| The recorded sessions in data/, written by gen-fixtures.py. -}", "",
       "import Bytes exposing (Bytes)", "import UInt8", ""]
for f in sorted((here / "data").glob("*.raw")):
    name = f.stem
    vals = list(f.read_bytes())
    rows = [", ".join(str(v) for v in vals[i:i + 24]) for i in range(0, len(vals), 24)]
    out += ["", f"{name} : Bytes", f"{name} =",
            "    Bytes.fromUInt8s (Array.map UInt8.fromInt",
            "        [ " + "\n        , ".join(rows), "        ]", "    )", ""]
(here / "src" / "Fixtures.geng").write_text("\n".join(out))
