import sys

from PIL import Image, ImageChops

a, b, out = sys.argv[1:4]
A = Image.open(a).convert('RGB')
B = Image.open(b).convert('RGB')
d = ImageChops.difference(A, B).convert('L').point(lambda v: 255 if v > 24 else 0)
bbox = d.getbbox()
n = sum(1 for v in d.getdata() if v)
print('diff pixels', n, 'bbox', bbox)
vis = Image.blend(A, Image.new('RGB', A.size, 'white'), 0.6)
vis.paste((255, 0, 0), mask=d)
vis.save(out)
