import ctypes
import winreg


def get_windows_theme():
    """Read live Windows taskbar dark/light mode and DWM colorization."""
    is_dark = True
    accent = (37, 99, 235)

    try:
        with winreg.OpenKey(
            winreg.HKEY_CURRENT_USER,
            r"Software\Microsoft\Windows\CurrentVersion\Themes\Personalize",
        ) as key:
            val, _ = winreg.QueryValueEx(key, "SystemUsesLightTheme")
            is_dark = val == 0
    except OSError:
        pass

    # Live DWM colorization (updates automatically when wallpaper/accent changes)
    try:
        color = ctypes.c_uint32()
        opaque = ctypes.c_bool()
        hr = ctypes.windll.dwmapi.DwmGetColorizationColor(
            ctypes.byref(color), ctypes.byref(opaque)
        )
        if hr == 0:
            val = color.value
            r = (val >> 16) & 0xFF
            g = (val >> 8) & 0xFF
            b = val & 0xFF
            accent = (r, g, b)
    except Exception:
        pass

    return {"is_dark": is_dark, "accent": accent}


def resolve_colors(settings):
    """Compute theme palette for Windows, Dark, or Deep Dark."""
    mode = settings.get("mode", "deep_dark")
    neutral_accent = (226, 226, 231)

    if mode == "windows":
        win = get_windows_theme()
        is_dark = win["is_dark"]
        accent = win["accent"]
        acc_r, acc_g, acc_b = accent
        if is_dark:
            bg = (
                int(16 + acc_r * 0.14),
                int(18 + acc_g * 0.14),
                int(24 + acc_b * 0.14),
            )
            alpha = 232
        else:
            bg = (244, 246, 250)
            alpha = 244
    elif mode == "dark":
        is_dark = True
        bg = (12, 13, 17)
        alpha = 250
        accent = neutral_accent
    else:  # deep_dark: nearly black, with readable foreground contrast
        is_dark = True
        bg = (2, 3, 5)
        alpha = 253
        accent = neutral_accent

    return {
        "is_dark": is_dark,
        "bg": bg,
        "alpha": alpha,
        "accent": accent,
    }


def build_dock_qss(colors, drag_highlight=False):
    is_dark = colors["is_dark"]
    r, g, b = colors["bg"]
    alpha = colors["alpha"]
    acc_r, acc_g, acc_b = colors["accent"]

    text_col = "#f5f5f5" if is_dark else "#171717"
    muted_col = "#b3b4bd" if is_dark else "#52525b"
    card_bg = "rgba(255, 255, 255, 25)" if is_dark else "rgba(15, 23, 42, 12)"
    card_border = "rgba(255, 255, 255, 58)" if is_dark else "rgba(15, 23, 42, 34)"
    btn_bg = "rgba(255, 255, 255, 24)" if is_dark else "rgba(15, 23, 42, 18)"
    btn_text = text_col
    active_text = "#111113" if (acc_r * 0.299 + acc_g * 0.587 + acc_b * 0.114) > 155 else "#ffffff"
    cap_bg = "#e4e4e7" if is_dark else "#27272a"
    cap_text = "#18181b" if is_dark else "#ffffff"
    scroll_handle = "rgba(255, 255, 255, 70)" if is_dark else "rgba(15, 23, 42, 70)"
    scroll_hover = "rgba(255, 255, 255, 125)" if is_dark else "rgba(15, 23, 42, 120)"

    if drag_highlight:
        border = f"2px solid rgba({acc_r}, {acc_g}, {acc_b}, 225)"
    else:
        border = f"1px solid {card_border}"

    return f"""
        #DockContainer {{
            background-color: rgba({r}, {g}, {b}, {alpha});
            border: {border};
            border-radius: 20px;
        }}
        QLabel {{
            color: {text_col};
            font-family: 'Segoe UI';
            font-weight: 600;
        }}
        QLabel#BrandTitle {{
            font-size: 18px;
            font-weight: 700;
        }}
        QLabel#CardMeta, QLabel#StatusLabel {{
            color: {muted_col};
            font-size: 10px;
            font-weight: 600;
        }}
        QLabel#EmptyTitle {{
            color: {text_col};
            font-size: 14px;
            font-weight: 600;
        }}
        QLabel#CardText {{
            font-weight: 400;
        }}
        QLabel#SubLabel {{
            color: {muted_col};
            font-size: 11px;
            font-weight: 600;
        }}
        QToolTip {{ background: rgb({max(20,r+18)}, {max(20,g+18)}, {max(22,b+18)}); color: {text_col}; border: 1px solid {card_border}; padding: 5px 7px; }}
        QPlainTextEdit {{ background-color: {card_bg}; color: {text_col}; border: 1px solid {card_border}; border-radius: 10px; padding: 8px; }}
        QComboBox {{ background: {btn_bg}; color: {btn_text}; border: 1px solid {card_border}; border-radius: 9px; padding: 6px; }}
        QLineEdit {{
            background-color: {card_bg};
            color: {text_col};
            border: 1px solid {card_border};
            border-radius: 13px;
            padding: 6px 12px;
            font-size: 12px;
            font-weight: 400;
        }}
        QLineEdit:focus {{
            border-color: rgba({acc_r}, {acc_g}, {acc_b}, 200);
        }}
        QPushButton#HeaderBtn, QPushButton#BackBtn, QPushButton#GearBtn {{
            background: {btn_bg};
            color: {btn_text};
            border: 1px solid {card_border};
            border-radius: 12px;
            padding: 6px 10px;
            font-size: 11px;
            font-weight: 600;
        }}
        QPushButton#HeaderBtn:hover, QPushButton#BackBtn:hover, QPushButton#GearBtn:hover {{
            background: rgba({acc_r}, {acc_g}, {acc_b}, 200);
            border-color: rgba({acc_r}, {acc_g}, {acc_b}, 240);
            color: {active_text};
        }}
        QPushButton#HeaderBtn:checked {{
            background: rgba({acc_r}, {acc_g}, {acc_b}, 225);
            border-color: rgba({acc_r}, {acc_g}, {acc_b}, 255);
            color: {active_text};
        }}
        QPushButton#CaptureBtn {{
            background: {cap_bg};
            color: {cap_text};
            border: 1px solid {card_border};
            border-radius: 12px;
            padding: 4px 10px;
            font-size: 11px;
            font-weight: 600;
        }}
        QPushButton#CaptureBtn:hover {{
            background: #a1a1aa;
            color: #18181b;
        }}
        QPushButton#NoteBtn {{ background: {btn_bg}; color: {btn_text}; border: 1px solid {card_border}; border-radius: 10px; padding: 5px 10px; font-size: 11px; }}
        QPushButton#NoteBtn:hover {{ background: rgba({acc_r}, {acc_g}, {acc_b}, 80); border-color: rgba({acc_r}, {acc_g}, {acc_b}, 170); }}
        QPushButton#CardAction {{ background: transparent; border: 1px solid transparent; border-radius: 8px; }}
        QPushButton#CardAction:hover {{ background: rgba({acc_r}, {acc_g}, {acc_b}, 70); border-color: rgba({acc_r}, {acc_g}, {acc_b}, 110); }}
        QPushButton#CloseBtn {{
            background: {btn_bg};
            color: {btn_text};
            border: none;
            border-radius: 11px;
            font-size: 14px;
            font-weight: 600;
        }}
        QPushButton#CloseBtn:hover {{
            background: #b91c1c;
            color: #ffffff;
        }}
        QPushButton#ModeBtn {{
            background: {btn_bg};
            color: {btn_text};
            border: 1px solid {card_border};
            border-radius: 13px;
            padding: 7px 10px;
            font-size: 11px;
            font-weight: 600;
        }}
        QPushButton#ModeBtn:hover {{
            background: rgba({acc_r}, {acc_g}, {acc_b}, 170);
            border-color: rgba({acc_r}, {acc_g}, {acc_b}, 220);
            color: {active_text};
        }}
        QPushButton#ModeBtn:checked {{
            background: rgba({acc_r}, {acc_g}, {acc_b}, 225);
            color: {active_text};
            border-color: rgba({acc_r}, {acc_g}, {acc_b}, 255);
        }}
        #DragHandle {{
            background: {scroll_handle};
            border-radius: 2px;
        }}
        #DragHandle:hover {{
            background: {scroll_hover};
        }}
        QScrollBar:vertical {{
            background: transparent;
            width: 5px;
            margin: 2px 0px;
        }}
        QScrollBar::handle:vertical {{
            background: {scroll_handle};
            border-radius: 2px;
            min-height: 24px;
        }}
        QScrollBar::handle:vertical:hover {{
            background: {scroll_hover};
        }}
        QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical,
        QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{
            height: 0px;
            background: none;
        }}
    """