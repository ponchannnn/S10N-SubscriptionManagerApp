"""会員登録・ログイン画面(担当: 西内)。

いまは画面の切り替えを確認するための仮置き。担当者がこのファイルを書き換える。
関数名 account_view と引数(page)は main.py が使うので変えないこと。
"""

import flet as ft

from components import feedback


def account_view(page: ft.Page) -> ft.Control:
    """会員登録・ログイン画面の中身を返す。"""
    return feedback.message_panel("会員登録・ログイン画面は準備中です。\n(担当: 西内)", icon=ft.Icons.CONSTRUCTION)
