"""サービスアイコンと契約状態の見た目を統一する．"""

import flet as ft
import theme


def service_icon(service: dict, *, size: int = 64) -> ft.Control:
    """画像または頭文字を表示し，時計バッジ・グレーアウトを付ける．"""
    cancelled = service.get("status") == "cancelled"
    color = theme.OFF_FILL if cancelled else theme.ACCENT
    fallback = ft.Container(
        content=ft.Text(
            str(service.get("name", "?"))[:1], size=size * 0.42,
            weight=ft.FontWeight.BOLD,
            color=theme.OFF_INK if cancelled else theme.SURFACE,
        ), bgcolor=color, alignment=ft.Alignment.CENTER,
        width=size, height=size, border_radius=16,
    )
    content = fallback
    if service.get("icon"):
        content = ft.Image(
            src=service["icon"], width=size, height=size,
            border_radius=16, fit=ft.BoxFit.COVER,
            error_content=fallback,
            color=theme.OFF_FILL if cancelled else None,
            color_blend_mode=ft.BlendMode.SATURATION if cancelled else None,
        )
    controls = [content]
    if service.get("status") == "trial":
        controls.append(ft.Container(
            content=ft.Icon(ft.Icons.SCHEDULE, size=16, color=theme.SURFACE),
            bgcolor=theme.TRIAL, width=26, height=26, border_radius=13,
            border=ft.Border.all(2, theme.GROUND), alignment=ft.Alignment.CENTER,
            right=-3, top=-3,
        ))
    return ft.Stack(
        controls, width=size, height=size,
        clip_behavior=ft.ClipBehavior.NONE,
    )

