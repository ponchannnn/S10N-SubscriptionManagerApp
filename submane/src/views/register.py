"""サブスク登録画面(担当: 石井)。

いまは画面の切り替えを確認するための仮置き。担当者がこのファイルを書き換える。
関数名 register_view と引数(page)は main.py が使うので変えないこと。
"""

import flet as ft

from components import feedback


def register_view(page: ft.Page) -> ft.Control:
    """サブスク登録画面の中身を返す。"""
    return feedback.message_panel("サブスク登録画面は準備中です。\n(担当: 石井)", icon=ft.Icons.CONSTRUCTION)
