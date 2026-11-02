"""アカウント画面(担当: 西内)。ログイン中の表示とアカウント削除の確認ダイアログを確認する。"""
from types import SimpleNamespace

import flet as ft

import api_client
from ui_helpers import walk
from views.account import account_view


class PageStub:
    width = 390
    window = None
    route = '/'
    def __init__(self):
        self.dialogs = []
        self.tasks = []
        self.session = SimpleNamespace(store={})
    def update(self):
        pass
    def show_dialog(self, dialog):
        self.dialogs.append(dialog)
    def pop_dialog(self):
        return self.dialogs.pop()
    def run_task(self, handler, *args):
        self.tasks.append((handler, args))


def _delete_account_button(view):
    return next(c for c in walk(view) if isinstance(c, ft.OutlinedButton)
                and any(isinstance(t, ft.Text) and t.value == 'アカウントを削除' for t in walk(c)))


def test_signed_in_view_has_a_delete_account_button():
    button = _delete_account_button(account_view(PageStub()))
    assert button.on_click is not None


def test_delete_account_button_opens_a_confirmation_dialog_with_cancel():
    page = PageStub()
    button = _delete_account_button(account_view(page))

    button.on_click(SimpleNamespace())

    assert len(page.dialogs) == 1
    dialog = page.dialogs[0]
    assert [a.content for a in dialog.actions] == ['キャンセル', '削除する']

    dialog.actions[0].on_click(SimpleNamespace())  # キャンセル
    assert page.dialogs == []


def test_sign_in_view_does_not_have_a_delete_account_button(monkeypatch):
    monkeypatch.setattr(api_client, '_logged_in', False)
    view = account_view(PageStub())
    assert not any(isinstance(t, ft.Text) and t.value == 'アカウントを削除' for t in walk(view))
