"""詳細画面(担当: 小湊)。

いまは画面の切り替えを確認するための仮置き。担当者がこのファイルを書き換える。
関数名 detail_view と引数(page)は main.py が使うので変えないこと。
"""

import flet as ft

import navigation
from components import feedback


def detail_view(page: ft.Page) -> ft.Control:
    """詳細画面の中身を返す。"""
    sub_id = navigation.get_sub_id(page)  # 表示するサブスクのID(文字列)

    return feedback.message_panel(f"詳細画面は準備中です。\n(担当: 小湊 / サブスクID: {sub_id})", icon=ft.Icons.CONSTRUCTION)
