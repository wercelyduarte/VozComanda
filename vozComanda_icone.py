# Gera icone.ico (microfone) - rode se quiser recriar/alterar o icone
from PIL import Image, ImageDraw

S = 1024  # desenha grande e reduz (suaviza as bordas)
img = Image.new("RGBA", (S, S), (0, 0, 0, 0))
d = ImageDraw.Draw(img)

# fundo: quadrado arredondado azul
d.rounded_rectangle((32, 32, S - 32, S - 32), radius=220, fill=(24, 90, 200, 255))

BR = (255, 255, 255, 255)
# capsula do microfone
d.rounded_rectangle((372, 170, 652, 600), radius=140, fill=BR)
# arco em "U" ao redor
d.arc((268, 330, 756, 800), start=0, end=180, fill=BR, width=46)
# haste e base
d.rectangle((489, 790, 535, 860), fill=BR)
d.rounded_rectangle((372, 840, 652, 886), radius=23, fill=BR)

# ondas sonoras (voz)
for off, w in ((0, 0),):
    pass
img.save("icone.png")
sizes = [(256, 256), (128, 128), (64, 64), (48, 48), (32, 32), (16, 16)]
img.save("icone.ico", sizes=sizes)
print("ok")
