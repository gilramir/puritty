"""PPM to PNG, cropped to the first N rows of cells: topng.py IN OUT ROWS CH"""
import sys
from PIL import Image
im = Image.open(sys.argv[1])
rows, ch = int(sys.argv[3]), int(sys.argv[4])
im = im.crop((0, 0, im.width, rows * ch))
im.save(sys.argv[2])
