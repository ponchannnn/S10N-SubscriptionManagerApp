"""日付と時刻を順に選び，確定時だけ登録フォームへ反映する．"""
from datetime import datetime

import flet as ft
import theme

from logic.subscriptions import JST, parse_time


def attach_datetime_picker(page, field, *, minimum=None):
    """日本時間の入力欄に，カレンダーと24時間表記の時刻選択を付ける．"""
    def open_picker(event=None):
        if field.disabled:
            return
        now = datetime.now(JST).replace(tzinfo=None, second=0, microsecond=0)
        lower = datetime(1900, 1, 1)
        if minimum:
            try:
                lower = parse_time(minimum()).astimezone(JST).replace(tzinfo=None)
            except (ValueError, TypeError):
                pass
        try:
            seed = parse_time(field.value).astimezone(JST).replace(tzinfo=None)
        except (ValueError, TypeError):
            seed = now
        seed = min(max(seed, lower), datetime(2100, 12, 31, 23, 59))
        locale = ft.Locale(language_code="ja", country_code="JP")

        def date_selected(event):
            date = event.control.value
            if date is None:
                return

            initial = datetime.combine(date.date(), seed.time())
            earliest = lower if date.date() == lower.date() else None
            if earliest is not None:
                initial = max(initial, earliest)
            selected = {"value": initial}

            def time_changed(event):
                # スワイプ中は仮選択だけを更新し，登録欄にはまだ反映しない．
                if event.control.value is not None:
                    selected["value"] = event.control.value

            def confirm_time(event):
                if field.disabled:
                    return
                field.value = datetime.combine(date.date(), selected["value"].time()).strftime("%Y-%m-%dT%H:%M")
                field.error = None
                page.pop_dialog()
                page.update()

            wheel = ft.CupertinoDatePicker(
                value=initial, locale=locale, date_picker_mode=ft.CupertinoDatePickerMode.TIME,
                use_24h_format=True, minute_interval=1, first_date=earliest,
                item_extent=40, on_change=time_changed)
            page.show_dialog(ft.AlertDialog(
                modal=True, title=theme.text("時刻を選択", size=18, weight="bold"),
                inset_padding=ft.Padding.symmetric(horizontal=16, vertical=24),
                content_padding=ft.Padding.symmetric(horizontal=12, vertical=8),
                content=ft.Column(width=240, tight=True, spacing=8, controls=[
                    theme.text("時・分を上下にスワイプ（日本時間）", size=12, color=theme.INK_SUB),
                    ft.Container(height=200, content=wheel)]),
                actions=[ft.TextButton("キャンセル", height=44, on_click=lambda e: page.pop_dialog()),
                         ft.TextButton("確定", height=44, on_click=confirm_time)]))

        page.show_dialog(ft.DatePicker(
            value=seed, first_date=lower.date(), last_date=datetime(2100, 12, 31),
            locale=locale, help_text=field.label.replace(" *", "") + "の日付を選択",
            confirm_text="時刻を選ぶ", cancel_text="キャンセル", on_change=date_selected))

    field.read_only = True
    field.on_click = open_picker
    field.helper = "タップして日付と時刻を選択（日本時間）"
    field.suffix_icon = ft.IconButton(
        icon=ft.Icons.CALENDAR_MONTH_OUTLINED, tooltip="日付と時刻を選択",
        width=44, height=44, on_click=open_picker)
