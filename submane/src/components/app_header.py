"""画面幅を取りすぎない共通ヘッダー．追加操作はホームの主操作にまとめる．"""
import flet as ft
import api_client
import navigation
import theme
from logic.notifications import upcoming_notices


def _bell(page):
    """お知らせのベル．近いお知らせがあれば件数のバッジを付ける(通信はしない)．"""
    count = len(upcoming_notices(api_client.cached_subscriptions()))
    return ft.IconButton(
        icon=ft.Icons.NOTIFICATIONS_ACTIVE_OUTLINED if count else ft.Icons.NOTIFICATIONS_NONE_ROUNDED,
        icon_color=theme.INK, width=44, height=44, bgcolor=theme.SURFACE,
        tooltip=f'お知らせ {count}件' if count else 'お知らせ',
        badge=ft.Badge(label=str(count), bgcolor=theme.DANGER, text_color=theme.ON_ACCENT) if count else None,
        on_click=lambda e: navigation.go(page, navigation.NOTIFICATIONS))


def app_header(page, title=None, show_back=False, show_actions=True):
    controls = []
    if show_back:
        controls.append(ft.IconButton(icon=ft.Icons.ARROW_BACK_ROUNDED,
            width=44, height=44, icon_color=theme.INK, tooltip='戻る',
            on_click=lambda e: navigation.go_back(page)))
    else:
        controls.append(ft.Container(width=34, height=34, border_radius=11, bgcolor=theme.ACCENT,
            alignment=ft.Alignment.CENTER,
            content=ft.Icon(ft.Icons.SUBSCRIPTIONS_OUTLINED, color=theme.ON_ACCENT, size=19)))
    controls.append(theme.text(title or 'サブマネ', size=18 if title else 21, weight='bold',
        expand=True, max_lines=1, overflow=ft.TextOverflow.ELLIPSIS))
    if show_actions:
        controls.append(_bell(page))
        controls.append(ft.IconButton(icon=ft.Icons.PERSON_OUTLINE_ROUNDED, icon_color=theme.INK,
            width=44, height=44, tooltip='アカウント', bgcolor=theme.SURFACE,
            on_click=lambda e: navigation.go(page, navigation.ACCOUNT)))
    return ft.Container(bgcolor=theme.GROUND,
        padding=ft.Padding.only(left=8 if show_back else 16, right=16, top=8, bottom=4),
        content=ft.Row(spacing=10, vertical_alignment=ft.CrossAxisAlignment.CENTER, controls=controls))
