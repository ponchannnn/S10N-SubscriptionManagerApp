"""スマホ表示のロゴ・操作領域・フッター構成を確認する．"""
from pathlib import Path
import json
import xml.etree.ElementTree as ET
from types import SimpleNamespace
import flet as ft
import httpx
import pytest
import api_client
import config
from components.service_icon import service_icon
from service_assets import bundled_icon, logo_catalog
from views.home import _build_pages, home_view
from views.register import register_view
from ui_helpers import walk, save_button


class PageStub:
    width = 390
    def update(self):
        pass


def test_all_catalog_images_are_valid_and_mirrored_to_server():
    root = Path(__file__).resolve().parents[2]
    assets = root / 'submane/src/assets/icons'
    catalog = logo_catalog()
    assert len(catalog) == 19
    for slug, item in catalog.items():
        image = assets / item['filename']
        data = image.read_bytes()
        assert item['source_url'].startswith('https://')
        if image.suffix == '.png':
            assert data.startswith(b'\x89PNG\r\n\x1a\n')
        else:
            assert ET.fromstring(data).tag.endswith('svg')
        assert data == (root / 'mane_server/public/icons' / image.name).read_bytes()
        assert bundled_icon({'slug': slug}) == 'icons/' + image.name
        assert bundled_icon({'name': item['name']}) == 'icons/' + image.name


def test_remote_logo_keeps_aspect_and_has_offline_fallback(monkeypatch):
    monkeypatch.setattr(config, 'USE_DUMMY_DATA', False)
    icon = service_icon({'name': 'Netflix', 'icon': 'https://example.com/logo.png', 'status': 'trial'})
    image = icon.controls[0].content
    assert image.src == 'https://example.com/logo.png'
    assert image.fit == ft.BoxFit.CONTAIN
    assert image.error_content.src == 'icons/netflix.png'
    assert len(icon.controls) == 2  # 状態をロゴと別のバッジで示す．
    unknown = service_icon({'name': '独自サービス'})
    assert isinstance(unknown.controls[0].content, ft.Container)


@pytest.mark.parametrize('width', [320, 390, 430])
def test_home_has_three_columns_readable_names_and_accessible_add(width):
    page = PageStub()
    page.width = width
    view = home_view(page)
    pager = next(c for c in walk(view) if isinstance(c, ft.PageView))
    for screen in pager.controls:
        assert len(screen.controls) <= 4
        for row in screen.controls:
            assert len(row.controls) == 3
            for tile in row.controls:
                if tile.content:
                    semantics = tile.content
                    assert semantics.button and '詳細を開く' in semantics.label
                    name = semantics.content.controls[1].content
                    assert name.max_lines == 2
    add = next(c for c in walk(view) if isinstance(c, ft.IconButton) and c.tooltip == 'サブスクを追加')
    assert add.width >= 44 and add.height >= 44


def test_registration_save_stays_outside_scrolling_fields():
    view = register_view(PageStub(), on_back=lambda: None)
    body, footer = view.controls
    assert body.expand and body.scroll == ft.ScrollMode.AUTO
    save = save_button(view)
    assert save in list(walk(footer)) and save not in list(walk(body))
    assert save.height >= 44 and save.expand
    amount = next(c for c in walk(body) if isinstance(c, ft.TextField) and c.label.startswith('1回の支払額'))
    assert any(isinstance(c, ft.Column) and amount in c.controls for c in walk(body))


def test_common_api_preserves_server_field_errors(monkeypatch):
    payload = {'error': {'code': 'validation_error', 'message': '入力内容を確認してください．',
                         'details': {'custom_name': ['名称を入力してください．']}}}
    with httpx.Client(base_url='https://example.com', transport=httpx.MockTransport(
            lambda request: httpx.Response(422, json=payload))) as client:
        monkeypatch.setattr(api_client, '_client', client)
        with pytest.raises(api_client.ApiError) as info:
            api_client._request('POST', '/api/v1/subscriptions', json={})
    assert info.value.status_code == 422
    assert info.value.details == payload['error']['details']
