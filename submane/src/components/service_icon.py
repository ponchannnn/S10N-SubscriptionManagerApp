"""サービスのアイコン。状態(無料トライアル中 / 解約済み)の見た目もここでそろえる。

アイコンを表示する画面は必ずこの部品を使う:
    from components.service_icon import service_icon
    service_icon(sub)             # ホームと同じ72px
    service_icon(sub, size=44)    # 一覧の行など小さく出すとき
"""

from zlib import crc32
import flet as ft

import api_client
import theme

BADGE_SIZE = 30      # トライアルの時計バッジ(外周の縁取りを含む)
BADGE_OVERHANG = 8   # バッジがタイルからはみ出す量


def footprint(size: float = 72) -> tuple[float, float]:
    """service_icon が占める (幅, 高さ) を返す。バッジのはみ出し分を含む。"""
    return size + BADGE_OVERHANG * 2, size + BADGE_OVERHANG


def service_icon(sub: dict, size: float = 72, color_index: int | None = None, ring_color: str = theme.GROUND) -> ft.Control:
    """サブスク1件のアイコンを返す。

    sub         : サブスク1件(name / icon / status を使う)
    size        : タイルの一辺(px)
    color_index : アイコン画像がないときのタイル色の番号(theme.TILE_COLORS)
    ring_color  : バッジの縁取り色。アイコンを置く場所の背景色に合わせる
    """
    if color_index is None:
        identity = str(sub.get("service_id") or sub.get("id") or sub.get("name") or "?")
        color_index = crc32(identity.encode("utf-8"))
    cancelled = sub.get("status") == "cancelled"
    trial = sub.get("status") == "trial"
    radius = round(size * 0.28)
    name = sub.get("name") or "?"

    # 画像がない(または読み込めない)ときは、頭文字のタイルを出す
    monogram = ft.Container(
        width=size,
        height=size,
        border_radius=radius,
        bgcolor=theme.OFF_FILL if cancelled else theme.tile_color(color_index),
        alignment=ft.Alignment.CENTER,
        content=theme.text(
            name[0],
            size=round(size * 0.42),
            weight="black",
            color=theme.OFF_INK if cancelled else theme.ON_ACCENT,
        ),
    )

    url = api_client.icon_url(sub.get("icon"))
    if url:
        image = ft.Image(src=url, width=size, height=size, fit=ft.BoxFit.COVER, error_content=monogram)
        if cancelled:  # 解約済みは白黒にして薄くする
            image.color = theme.OFF_FILL
            image.color_blend_mode = ft.BlendMode.SATURATION
            image.opacity = 0.55
        tile = ft.Container(
            width=size,
            height=size,
            border_radius=radius,
            bgcolor=theme.OFF_FILL if cancelled else theme.SURFACE,
            clip_behavior=ft.ClipBehavior.ANTI_ALIAS,
            content=image,
        )
    else:
        tile = monogram

    tile.left = BADGE_OVERHANG
    tile.top = BADGE_OVERHANG
    controls = [tile]

    if trial:
        scale = min(1.0, size / 72)
        badge = round(BADGE_SIZE * max(scale, 0.7))
        controls.append(
            ft.Container(
                width=badge,
                height=badge,
                right=0,
                top=0,
                border_radius=badge / 2,
                bgcolor=theme.TRIAL,
                border=ft.Border.all(3, ring_color),
                alignment=ft.Alignment.CENTER,
                content=ft.Icon(ft.Icons.ACCESS_TIME, size=round(badge * 0.5), color=theme.ON_ACCENT),
            )
        )

    width, height = footprint(size)
    return ft.Stack(width=width, height=height, controls=controls)


def status_label(sub: dict) -> str:
    """状態を表す短い文言を返す(読み上げや補足表示用)。契約中は空文字。"""
    return {"trial": "無料トライアル中", "cancelled": "解約済み"}.get(sub.get("status"), "")
