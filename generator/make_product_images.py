"""Мастер-кадры товара из официальных рендеров брендов.

Запускается руками, когда меняется состав витрины:
`.venv/bin/python generator/make_product_images.py`. Результат — файлы
`sources/img/<image>.jpg`, из которых make_images.py режет webp под лестницу
ширин слота `product_card`. Оба шага коммитятся.

Зачем отдельный шаг, а не «скачал и положил». Рендеры приезжают из двух разных
студий: Davines — JPG на ровном фоне #F5F5F3, флаконы стоят на общей линии пола;
Lebel — PNG с прозрачностью на своём холсте. Положенные рядом как есть, они
рассыпают витрину на два набора. Здесь все двенадцать кадров приводятся к одному
виду: общий фон, одна пропорция 4:5, одна линия пола, одинаковые поля.

Про размер флакона. Внутри Davines масштаб общий, поэтому 50 ml и 135 ml на
витрине отличаются ровно так же, как на полке, — это видно и без подписи.
У Lebel обе съёмки уже нормализованы самим брендом (оба флакона ровно 640 px),
относительный размер оттуда не достать, поэтому им задан свой масштаб — под
250-миллилитровый флакон Davines. Объём в таких случаях читается с карточки.
"""

import sys
import tempfile
import urllib.request
from pathlib import Path

import yaml
from PIL import Image, ImageChops

ROOT = Path(__file__).resolve().parent
SRC_DIR = ROOT / "sources" / "img"
IMG_DIR = ROOT.parent / "th.neva.beauty" / "assets" / "img"

# Превью ссылки для мессенджеров: полка из нескольких флаконов. Пересылают
# именно эту страницу, и в карточке должен быть товар, а не общая обложка салона.
OG_CARD = (1200, 630)
OG_NAME = "og-kosmetika.jpg"
OG_BOTTLE_HEIGHT = 470   # рост самого высокого флакона в карточке
OG_GAP = 38              # промежуток между флаконами
OG_FLOOR = 0.90          # линия пола в долях высоты карточки
OG_SIDE_MARGIN = 0.05    # поля по краям карточки в долях ширины
OG_LINEUP = ["davines-love-curl-shampoo", "davines-minu-mask", "davines-oi-oil-135",
             "davines-oi-liquid-luster", "lebel-viege-shampoo"]

# Кадр витрины: 4:5 с запасом по ширине — мастер режется make_images.py,
# самая большая производная слота `product_card` вдвое меньше.
FRAME = (1000, 1250)
# Фон студии Davines. Тот же цвет стоит фоном медиа-области карточки в CSS,
# поэтому кадр можно свободно вписывать в коробку любой пропорции:
# поля совпадают с фоном и шва не видно.
BACKDROP = (245, 245, 243)
# Поля кадра в долях: по бокам и сверху — воздух, снизу — «пол», на котором
# стоит флакон. Линия пола общая у всех двенадцати кадров.
SIDE_MARGIN, TOP_MARGIN, FLOOR_MARGIN = 0.12, 0.06, 0.06
# Порог отличия от фона, за которым пиксель считается товаром. Восьми хватает,
# чтобы поймать светлую этикетку и не поймать шум JPEG.
CONTENT_THRESHOLD = 8
# Высота флакона Davines 250 ml в готовом кадре — эталон для брендов,
# у которых своего масштаба нет.
REFERENCE_BOTTLE = 820
# Как выбирается масштаб бренда: relative — общий на весь бренд, флаконы
# сохраняют разницу в росте; fixed — заданная высота, когда исходники
# нормализованы студией и разницу восстановить неоткуда.
BRAND_FIT = {
    "davines": {"mode": "relative"},
    "lebel": {"mode": "fixed", "height": REFERENCE_BOTTLE},
}
JPEG_QUALITY = 92  # мастер, а не выдача: пережимать его будет make_images.py


def load_brands():
    data = yaml.safe_load((ROOT / "data/products.yml").read_text(encoding="utf-8"))
    return data["brands"]


def download(url, target):
    request = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(request, timeout=30) as response:
        target.write_bytes(response.read())
    return target


def content_box(image):
    """Прямоугольник самого товара — без фона и без прозрачных полей."""
    if image.mode == "RGBA":
        return image.getchannel("A").getbbox()
    backdrop = Image.new("RGB", image.size, image.convert("RGB").getpixel((0, 0)))
    diff = ImageChops.difference(image.convert("RGB"), backdrop).convert("L")
    return diff.point(lambda value: 255 if value > CONTENT_THRESHOLD else 0).getbbox()


def flatten(image, box):
    """Товар на фоне студии: прозрачность заливается тем же цветом, что и кадр."""
    cut = image.crop(box)
    if cut.mode != "RGBA":
        return cut.convert("RGB")
    plate = Image.new("RGB", cut.size, BACKDROP)
    plate.paste(cut, mask=cut.getchannel("A"))
    return plate


def brand_scale(fit, boxes):
    """Множитель, общий для всех кадров бренда."""
    frame_width, frame_height = FRAME
    if fit["mode"] == "fixed":
        return fit["height"] / max(box[3] - box[1] for box in boxes)
    room_height = frame_height * (1 - TOP_MARGIN - FLOOR_MARGIN)
    room_width = frame_width * (1 - SIDE_MARGIN * 2)
    return min(room_height / max(box[3] - box[1] for box in boxes),
               room_width / max(box[2] - box[0] for box in boxes))


def compose(image, box, scale):
    """Кадр витрины: товар по центру, подошвой на общей линии пола."""
    frame_width, frame_height = FRAME
    product = flatten(image, box)
    size = (max(1, round(product.width * scale)), max(1, round(product.height * scale)))
    product = product.resize(size, Image.LANCZOS)
    frame = Image.new("RGB", FRAME, BACKDROP)
    floor = round(frame_height * (1 - FLOOR_MARGIN))
    frame.paste(product, ((frame_width - product.width) // 2, floor - product.height))
    return frame


def build_brand(brand, cache):
    """Мастер-кадры одного бренда: сначала общий масштаб, потом каждый кадр."""
    sources = [download(item["source"], cache / f"{item['image']}{Path(item['source']).suffix}")
               for item in brand["products"]]
    images = [Image.open(path) for path in sources]
    boxes = [content_box(image) for image in images]
    scale = brand_scale(BRAND_FIT[brand["slug"]], boxes)
    for item, image, box in zip(brand["products"], images, boxes):
        target = SRC_DIR / f"{item['image']}.jpg"
        compose(image, box, scale).save(target, format="JPEG", quality=JPEG_QUALITY)
        print(f"→ {target.name} {FRAME[0]}×{FRAME[1]} "
              f"{target.stat().st_size // 1024} КБ (масштаб {scale:.3f})")


def build_og_card():
    """Карточка превью: несколько флаконов витрины на общей линии пола.

    Собирается из готовых мастер-кадров, а не из исходников: у них уже общий фон
    и одинаковые поля, и полка на карточке выглядит той же полкой, что на сайте."""
    cuts = []
    for stem in OG_LINEUP:
        with Image.open(SRC_DIR / f"{stem}.jpg") as master:
            frame = master.convert("RGB")
            cuts.append(frame.crop(content_box(frame)))
    # Масштаб ограничен и ростом самого высокого флакона, и шириной всего ряда:
    # без второго ограничения широкая банка выталкивает крайний флакон за кадр.
    gaps = OG_GAP * (len(cuts) - 1)
    room = OG_CARD[0] * (1 - OG_SIDE_MARGIN * 2) - gaps
    scale = min(OG_BOTTLE_HEIGHT / max(cut.height for cut in cuts),
                room / sum(cut.width for cut in cuts))
    cuts = [cut.resize((max(1, round(cut.width * scale)),
                        max(1, round(cut.height * scale))), Image.LANCZOS) for cut in cuts]
    card = Image.new("RGB", OG_CARD, BACKDROP)
    floor = round(OG_CARD[1] * OG_FLOOR)
    left = (OG_CARD[0] - sum(cut.width for cut in cuts) - OG_GAP * (len(cuts) - 1)) // 2
    for cut in cuts:
        card.paste(cut, (left, floor - cut.height))
        left += cut.width + OG_GAP
    target = IMG_DIR / OG_NAME
    card.save(target, format="JPEG", quality=88)
    print(f"→ {target.name} {OG_CARD[0]}×{OG_CARD[1]} {target.stat().st_size // 1024} КБ")


def main():
    with tempfile.TemporaryDirectory() as tmp:
        for brand in load_brands():
            build_brand(brand, Path(tmp))
    build_og_card()
    return 0


if __name__ == "__main__":
    sys.exit(main())
