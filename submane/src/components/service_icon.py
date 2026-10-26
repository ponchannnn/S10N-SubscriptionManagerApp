"""ロゴの全体と色を保ち，契約状態は外側のバッジで表示する．"""
from zlib import crc32
import flet as ft
import api_client
import theme
from service_assets import bundled_icon

BADGE_SIZE = 24
BADGE_OVERHANG = 6


def footprint(size=72):
    return size + BADGE_OVERHANG, size + BADGE_OVERHANG


def service_icon(sub, size=72, color_index=None, ring_color=theme.GROUND):
    """API画像を優先し，通信失敗時も同梱ロゴか頭文字を表示する．"""
    cancelled = sub.get('status') == 'cancelled'
    trial = sub.get('status') == 'trial'
    name = sub.get('name') or '?'
    if color_index is None:
        color_index = crc32(str(sub.get('id') or name).encode('utf-8'))
    letter = ft.Container(width=size, height=size, border_radius=18,
        bgcolor=theme.tile_color(color_index), alignment=ft.Alignment.CENTER,
        content=theme.text(name[0], size=round(size * .4), weight='bold', color=theme.ON_ACCENT))
    local = bundled_icon(sub)
    local_image = ft.Image(src=local, width=size - 12, height=size - 12,
                          fit=ft.BoxFit.CONTAIN, error_content=letter) if local else letter
    remote = sub.get('icon')
    # ダミー中はサーバ不要で使える同梱画像を優先する．
    import config
    if remote and not (config.USE_DUMMY_DATA and local):
        image = ft.Image(src=api_client.icon_url(remote), width=size - 12, height=size - 12,
                         fit=ft.BoxFit.CONTAIN, error_content=local_image)
    else:
        image = local_image
    tile = ft.Container(width=size, height=size, bgcolor=theme.SURFACE,
        border_radius=18, border=ft.Border.all(1, theme.LINE), alignment=ft.Alignment.CENTER,
        content=image, tooltip=name)
    controls = [tile]
    if trial or cancelled:
        controls.append(status_badge(sub['status'], ring_color, right=0, bottom=0))
    width, height = footprint(size)
    return ft.Stack(width=width, height=height, controls=controls)


def status_badge(status, ring_color=theme.GROUND, **position):
    """カードと凡例で同じ時計・チェックと配色を使う．"""
    return ft.Container(width=BADGE_SIZE, height=BADGE_SIZE,
        bgcolor=theme.OFF_INK if status == 'cancelled' else theme.TRIAL,
        border_radius=12, border=ft.Border.all(2, ring_color), alignment=ft.Alignment.CENTER,
        content=ft.Icon(ft.Icons.CHECK if status == 'cancelled' else ft.Icons.ACCESS_TIME,
                        size=13, color=theme.ON_ACCENT), **position)


def status_label(sub):
    return {'trial': '無料トライアル中', 'cancelled': '解約済み'}.get(sub.get('status'), '')
