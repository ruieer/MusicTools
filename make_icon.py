"""Генерирует иконку MusicTools (пиксель-арт iPod) и сохраняет как .ico.

Запуск: python make_icon.py
Результат: icon.ico (многоразмерный: 16..256)
"""
from PIL import Image, ImageDraw

# Базовое разрешение пиксель-арта — потом масштабируется без сглаживания.
BASE = 64


def draw_ipod_base() -> Image.Image:
    """Рисуем iPod в базовом разрешении BASE x BASE (пиксель-арт)."""
    img = Image.new("RGBA", (BASE, BASE), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)

    def px(x, y, w, h, color):
        d.rectangle([x, y, x + w - 1, y + h - 1], fill=color)

    BLACK = (18, 18, 18, 255)
    WHITE = (255, 255, 255, 255)
    GRAY = (170, 170, 170, 255)
    DARK = (205, 205, 205, 255)
    SCREEN = (215, 215, 215, 255)
    BLUE = (30, 110, 235, 255)
    RED = (210, 45, 45, 255)
    ORANGE = (235, 120, 30, 255)
    YELLOW = (235, 200, 40, 255)
    GREEN = (80, 160, 60, 255)
    DARKRED = (150, 30, 30, 255)

    # Корпус iPod: белый с чёрной обводкой
    px(8, 6, 48, 54, BLACK)          # внешняя чёрная рамка
    px(10, 8, 44, 50, WHITE)        # белый корпус

    # Серая полоса слева (объём)
    px(10, 8, 5, 50, GRAY)

    # Экран: чёрная рамка, серый фон
    px(18, 12, 32, 20, BLACK)
    px(20, 14, 28, 16, SCREEN)

    # Обложка альбома в экране (цветные квадраты 5x5)
    cover_x, cover_y = 21, 15
    # 2x2 квадрата обложки
    px(cover_x,     cover_y,     3, 3, GREEN)
    px(cover_x + 3, cover_y,     3, 3, DARKRED)
    px(cover_x,     cover_y + 3, 3, 3, RED)
    px(cover_x + 3, cover_y + 3, 3, 3, ORANGE)

    # Текстовые строки (две чёрные полоски)
    px(cover_x + 7, cover_y + 1, 12, 2, BLACK)
    px(cover_x + 7, cover_y + 4, 9, 2, BLACK)

    # Прогресс-бар внизу экрана
    px(20, 27, 28, 2, DARK)
    px(20, 27, 16, 2, BLUE)

    # Колесо управления (click wheel): серый круг с чёрной обводкой
    cx, cy, r = 32, 43, 11
    d.ellipse([cx - r, cy - r, cx + r, cy + r], fill=BLACK)
    d.ellipse([cx - r + 2, cy - r + 2, cx + r - 2, cy + r - 2], fill=GRAY)

    # Белая центральная кнопка
    cr = 4
    d.ellipse([cx - cr, cy - cr, cx + cr, cy + cr], fill=WHITE)

    # Чёрные сегменты колеса (up/down/left/right)
    px(cx - 1, cy - r + 1, 2, 3, BLACK)        # вверх
    px(cx - 1, cy + r - 4, 2, 3, BLACK)        # вниз
    px(cx - r + 1, cy - 1, 3, 2, BLACK)        # влево
    px(cx + r - 4, cy - 1, 3, 2, BLACK)        # вправо

    return img


def main():
    sizes = [16, 24, 32, 48, 64, 128, 256]
    base = draw_ipod_base()
    images = [base.resize((sz, sz), Image.NEAREST) for sz in sizes]
    # В .ico первым должно идти наибольшее изображение, остальные — в append_images
    out = "icon.ico"
    images[-1].save(out, format="ICO",
                    sizes=[(sz, sz) for sz in sizes],
                    append_images=images[:-1])
    print(f"Сохранено: {out}")
    # Проверка
    from PIL import Image as _I
    check = _I.open(out)
    print("размеры в иконке:", sorted(check.ico.sizes()))


if __name__ == "__main__":
    main()
