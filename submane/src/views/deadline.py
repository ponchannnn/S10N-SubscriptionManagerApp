"""期限画面(担当: 小湊)。

いまは画面の切り替えを確認するための仮置き。担当者がこのファイルを書き換える。
関数名 deadline_view と引数(page)は main.py が使うので変えないこと。
"""

import flet as ft

from components import feedback


def deadline_view(page: ft.Page) -> ft.Control:
    """期限画面の中身を返す。"""
    return feedback.message_panel("期限画面は準備中です。\n(担当: 小湊)", icon=ft.Icons.CONSTRUCTION)
