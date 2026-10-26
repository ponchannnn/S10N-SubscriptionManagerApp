"""授業用に同梱したサービスロゴの参照．画像の原本・出典はassets/iconsに保存．"""
import json
from functools import lru_cache
from pathlib import Path
import unicodedata


def normalize_name(value):
    return unicodedata.normalize('NFKC', str(value or '')).casefold().replace(' ', '').replace('　', '')


@lru_cache(maxsize=1)
def logo_catalog():
    path = Path(__file__).parent / 'assets/icons/sources.json'
    return json.loads(path.read_text(encoding='utf-8'))


def bundled_icon(subscription):
    """サービスIDの有無に依存せず，slugか名称から同梱画像を返す．"""
    catalog = logo_catalog()
    slug = subscription.get('slug')
    if slug in catalog and catalog[slug].get('filename'):
        return 'icons/' + catalog[slug]['filename']
    name = normalize_name(subscription.get('name'))
    aliases = {'adobecreativecloud': 'adobe-cc', 'amazonprime': 'amazon-prime',
               'amazonプライム': 'amazon-prime', 'youtube': 'youtube-premium',
               'fod': 'fod-premium', 'abema': 'abema-premium'}
    slug = aliases.get(name)
    if slug is None:
        slug = next((key for key, item in catalog.items() if normalize_name(item.get('name')) == name), None)
    item = catalog.get(slug, {})
    return 'icons/' + item['filename'] if item.get('filename') else None
