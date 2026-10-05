"""一覧画面へ組み込める並び順選択部品．"""
import flet as ft
from logic.subscriptions import SORT_LABELS


def sort_selector(on_select, value="frequency", include_deadline=True):
    """解約済みを末尾にするsort_subscriptionsと合わせて使用する．"""
    return ft.Dropdown(label="並び順", value=value, on_select=on_select,
                       options=[ft.DropdownOption(key=key, text=text)
                                for key, text in SORT_LABELS.items()
                                if include_deadline or key != "deadline"])
