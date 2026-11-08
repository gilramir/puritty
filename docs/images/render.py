import sys
sys.path.insert(0, '/home/gram/prj/visiterm/harness')
from pathlib import Path
import importlib.util
spec = importlib.util.spec_from_file_location('pixels', '/home/gram/prj/visiterm/harness/pixels.py')
px = importlib.util.module_from_spec(spec); spec.loader.exec_module(px)
case, out = Path(sys.argv[1]), Path(sys.argv[2])
conf = px.write_fonts_conf()
xvfb, display = px.start_xvfb()
try:
    ppm = out.with_suffix('.ppm')
    s, used = px.draw(case, display, conf, ppm, True)
    w, h, pic = px.read_ppm(ppm.read_bytes())
    px.write_png(out, w, h, pic)
    print(w, h); print('\n'.join(sorted(set(Path(u).name for u in used))))
finally:
    xvfb.kill()
