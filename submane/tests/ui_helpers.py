"""入れ子になったフォームをユーザが操作する項目で探す．"""
import flet as ft


def walk(root):
    yield root
    content = getattr(root, "content", None)
    if isinstance(content, ft.Control):
        yield from walk(content)
    for control in getattr(root, "controls", []) or []:
        yield from walk(control)


def save_button(view):
    return next(c for c in walk(view) if isinstance(c, ft.Button) and c.content == "この内容で登録する")


def results_column(view):
    return next(c for c in walk(view) if getattr(c, "key", None) == "service-search-results")
