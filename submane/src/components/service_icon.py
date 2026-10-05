"""無料トライアルと解約済みを一貫した見た目で表示する．"""
from zlib import crc32
import flet as ft
import theme


def service_icon(subscription, size=64, color_index=None):
    """解約済みは画像を含めグレー表示，トライアル中は時計を添える．"""
    cancelled = subscription.get("status") == "cancelled"
    if color_index is None:
        identity = str(subscription.get("service_id") or subscription.get("id") or subscription.get("name") or "?")
        color_index = crc32(identity.encode("utf-8"))
    color = theme.OFF_FILL if cancelled else theme.TILE_COLORS[color_index % len(theme.TILE_COLORS)]
    letter = ft.Text((subscription.get("name") or "?")[:1], size=26,
                     weight=ft.FontWeight.BOLD, color=theme.OFF_INK if cancelled else theme.SURFACE)
    visual = letter
    if subscription.get("icon"):
        visual = ft.Image(src=subscription["icon"], width=size, height=size,
                          fit=ft.BoxFit.COVER, border_radius=18, error_content=letter,
                          color=theme.OFF_FILL if cancelled else None,
                          color_blend_mode=ft.BlendMode.SATURATION if cancelled else None,
                          opacity=0.5 if cancelled else 1)
    tile = ft.Container(content=visual, width=size, height=size, bgcolor=color,
                        border_radius=18, alignment=ft.Alignment.CENTER)
    if subscription.get("status") != "trial":
        return tile
    return ft.Stack(width=size + 8, height=size + 8, controls=[
        tile,
        ft.Container(content=ft.Icon(ft.Icons.ACCESS_TIME, color=theme.SURFACE, size=16),
                     width=26, height=26, right=0, top=0, bgcolor=theme.TRIAL,
                     border_radius=13, alignment=ft.Alignment.CENTER),
    ])
