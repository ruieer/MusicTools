"""Палитра тёмной темы, оттенки которой строятся от выбранного акцента."""
BG = "#14161b"
SIDEBAR = "#101216"
CARD = "#1d2027"
CARD_BORDER = "#2a2e37"
ACCENT = "#3b82f6"
ACCENT_HOVER = "#2f6fd8"
NAV_ACTIVE = "#1e3a5f"
NAV_HOVER = "#1b1f27"
SCROLL_HOVER = "#3a3f4a"
TEXT = "#e6e8ec"
MUTED = "#8b93a1"
DANGER = "#d9564f"
DANGER_HOVER = "#c0453f"
PRESETS = (("Синий", "#3b82f6"), ("Голубой", "#06b6d4"), ("Зелёный", "#22c55e"),
           ("Фиолетовый", "#8b5cf6"), ("Розовый", "#ec4899"), ("Оранжевый", "#f97316"),
           ("Красный", "#ef4444"), ("Жёлтый", "#eab308"))
BUTTON_TEXT = "#ffffff"
OPTION_HOVER = "#2a5fb8"
# второстепенные кнопки (не акцентные): светлее фона карточки, но тише основной кнопки
BUTTON_SOFT = "#4a3f6e"
BUTTON_SOFT_HOVER = "#5a4d85"
SOFT_TEXT = "#ffffff"   # мягкие кнопки всегда тёмные по фону - текст белый при любом акценте
TEXT_DISABLED = "#bda9f0"
ICONS = {"download": "⤓", "link": "↗", "manual": "✎", "retag": "♯", "covers": "▣",
         "gain": "◐", "ipod": "⇪", "library": "≣", "settings": "⚙"}

_BASE_BG = BG
_BASE_SIDEBAR = SIDEBAR
_BASE_CARD = CARD
_BASE_CARD_BORDER = CARD_BORDER
_BASE_NAV_HOVER = NAV_HOVER


def _rgb(color):
    color = color.lstrip("#")
    return tuple(int(color[i:i + 2], 16) for i in (0, 2, 4))


def _mix(color, other, share):
    """color с долей share, остальное - other."""
    a, b = _rgb(color), _rgb(other)
    return "#" + "".join(f"{round(x * share + y * (1 - share)):02x}" for x, y in zip(a, b))


def _luminance(color):
    channels = [value / 255 for value in _rgb(color)]
    channels = [value / 12.92 if value <= 0.04045 else ((value + 0.055) / 1.055) ** 2.4
                for value in channels]
    return sum(value * weight for value, weight in zip(channels, (0.2126, 0.7152, 0.0722)))


def valid(color) -> bool:
    return isinstance(color, str) and len(color) == 7 and color[0] == "#" and all(
        c in "0123456789abcdefABCDEF" for c in color[1:])


def set_accent(color):
    """Построить тёмную палитру оттенков выбранного цвета."""
    global BG, SIDEBAR, CARD, CARD_BORDER, NAV_ACTIVE, NAV_HOVER, SCROLL_HOVER
    global ACCENT, ACCENT_HOVER, OPTION_HOVER, BUTTON_TEXT
    global BUTTON_SOFT, BUTTON_SOFT_HOVER, TEXT_DISABLED
    if not valid(color):
        return
    ACCENT = color.lower()
    ACCENT_HOVER = _mix(ACCENT, "#000000", 0.82)
    OPTION_HOVER = _mix(ACCENT, "#000000", 0.7)
    BG = _mix(ACCENT, _BASE_BG, 0.08)
    SIDEBAR = _mix(ACCENT, _BASE_SIDEBAR, 0.08)
    CARD = _mix(ACCENT, _BASE_CARD, 0.16)
    CARD_BORDER = _mix(ACCENT, _BASE_CARD_BORDER, 0.28)
    NAV_HOVER = _mix(ACCENT, _BASE_NAV_HOVER, 0.18)
    NAV_ACTIVE = _mix(ACCENT, BG, 0.36)
    SCROLL_HOVER = _mix(ACCENT, CARD_BORDER, 0.42)
    luminance = _luminance(ACCENT)
    dark_contrast = (luminance + 0.05) / (_luminance("#111318") + 0.05)
    light_contrast = 1.05 / (luminance + 0.05)
    BUTTON_TEXT = "#111318" if dark_contrast >= light_contrast else "#ffffff"
    BUTTON_SOFT = _mix(ACCENT, CARD, 0.52)
    BUTTON_SOFT_HOVER = _mix(ACCENT, CARD, 0.68)
    TEXT_DISABLED = _mix(TEXT, ACCENT, 0.70)


def apply(ctk):
    """Обновить палитру CustomTkinter для новых виджетов."""
    t = ctk.ThemeManager.theme

    def put(widget, **values):
        for key, value in values.items():
            if key in t.get(widget, {}):
                t[widget][key] = value if isinstance(value, (int, float)) else [value, value]

    put("CTkButton", fg_color=ACCENT, hover_color=ACCENT_HOVER, text_color=BUTTON_TEXT,
        text_color_disabled=TEXT_DISABLED, corner_radius=8)
    put("CTkEntry", fg_color=BG, border_color=CARD_BORDER, corner_radius=8)
    put("CTkTextbox", fg_color=BG, border_color=CARD_BORDER, corner_radius=8)
    put("CTkOptionMenu", fg_color=ACCENT, button_color=ACCENT_HOVER, button_hover_color=OPTION_HOVER,
        text_color=BUTTON_TEXT,
        corner_radius=8)
    put("CTkCheckBox", fg_color=ACCENT, hover_color=ACCENT_HOVER, border_color=MUTED, corner_radius=5)
    put("CTkSegmentedButton", fg_color=BG, selected_color=ACCENT, selected_hover_color=ACCENT_HOVER,
        unselected_color=CARD, unselected_hover_color=NAV_HOVER, text_color=TEXT, corner_radius=8)
    put("CTkSwitch", progress_color=ACCENT)
    put("CTkSlider", button_color=ACCENT, button_hover_color=ACCENT_HOVER, progress_color=ACCENT)
    put("CTkScrollbar", button_color=CARD_BORDER, button_hover_color=SCROLL_HOVER)
    put("CTkScrollableFrame", label_fg_color=CARD)
