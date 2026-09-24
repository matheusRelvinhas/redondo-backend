"""
Reduz as imagens de img/ para o tamanho em que realmente aparecem no front.

    python script/optimize_imgs.py

Motivo: as imagens vem da fonte em 500-3000px, mas os logos aparecem entre
14px e 52px. Servir o original custa ~2.6 MB por tela de jogos.

Idempotente: nao aumenta imagem ja pequena, entao pode rodar sempre depois
do download_imgs.py.

Requer Pillow:  pip install pillow
"""
import os
import io
from PIL import Image

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
IMG_DIR = os.path.join(BASE_DIR, 'img')
TARGETS = [
    ('imgs/teams', 128, None),
    ('imgs/leagues', 160, None),
    ('imgs/players', 200, None),
    ('maps', 360, None),
    ('maps', 64, 'maps/thumb'),
]
EXTS = ('.png', '.jpg', '.jpeg', '.webp')


def to_webp(path: str, box: int) -> bytes:
    with Image.open(path) as im:
        im = im.convert('RGBA')
        im.thumbnail((box, box), Image.LANCZOS)
        buf = io.BytesIO()
        im.save(buf, 'WEBP', quality=82, method=4)
        return buf.getvalue()


def process(folder: str, box: int, out: str | None):
    src = os.path.join(IMG_DIR, folder)
    dst = os.path.join(IMG_DIR, out) if out else src
    if not os.path.isdir(src):
        return None
    os.makedirs(dst, exist_ok=True)
    files = [f for f in os.listdir(src) if f.lower().endswith(EXTS)]
    before = after = 0
    for name in files:
        from_path = os.path.join(src, name)
        if os.path.isdir(from_path):
            continue
        size = os.path.getsize(from_path)
        before += size
        webp_name = os.path.splitext(name)[0] + '.webp'
        to_path = os.path.join(dst, webp_name)
        try:
            data = to_webp(from_path, box)
        except Exception as exc:
            print(f'  falhou {name}: {exc}')
            after += size
            continue
        if out is None and len(data) >= size:
            after += size
            continue
        with open(to_path, 'wb') as f:
            f.write(data)
        after += len(data)
        if out is None and webp_name != name:
            try:
                os.remove(from_path)
            except OSError:
                pass
    return len(files), before, after


def mb(n: int) -> str:
    return f'{n / 1048576:.1f} MB'


if __name__ == '__main__':
    total_before = total_after = 0
    for folder, box, out in TARGETS:
        result = process(folder, box, out)
        if not result:
            continue
        count, before, after = result
        total_before += before
        total_after += after
        label = out or folder
        print(f'{label:<14} {count:>5} arq  {mb(before):>9} -> {mb(after):>9}')
    if total_before:
        saved = 100 - (total_after / total_before * 100)
        print(f'\ntotal {mb(total_before)} -> {mb(total_after)}  (-{saved:.0f}%)')
