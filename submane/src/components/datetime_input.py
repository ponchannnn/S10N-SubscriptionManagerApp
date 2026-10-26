"""日付と時刻を順に選び，確定時だけ登録フォームへ反映する．"""
from datetime import datetime

import flet as ft

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

            def time_selected(event):
                time = event.control.value
                if time is None or field.disabled:
                    return
                field.value = datetime.combine(date.date(), time).strftime("%Y-%m-%dT%H:%M")
                field.error = None
                page.update()

            page.show_dialog(ft.TimePicker(
                value=seed.time(), locale=locale,
                hour_format=ft.TimePickerHourFormat.H24,
                entry_mode=ft.TimePickerEntryMode.INPUT,
                help_text="時刻を選択（日本時間）", hour_label_text="時", minute_label_text="分",
                confirm_text="確定", cancel_text="キャンセル", on_change=time_selected))

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
