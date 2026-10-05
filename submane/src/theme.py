"""色・フォント・余白(全画面共通)。画面ごとに色コードを直接書かず、ここの定数を使う。"""

import flet as ft

# ---- 色 ----
GROUND = "#F3F5F4"       # 画面の地色
SURFACE = "#FFFFFF"      # ボタン、タブバー、カード
INK = "#14201C"          # 本文
INK_SUB = "#4A5552"      # 補足テキスト
LINE = "#D3D8D6"         # 枠線
ACCENT = "#0E6B5C"       # 主要ボタン、選択中の表示
ACCENT_SOFT = "#DCEBE7"  # 選択中タブの背景
TRIAL = "#B45309"        # 無料トライアルのバッジ
OFF_FILL = "#D3D8D6"     # 解約済みアイコンの面
OFF_INK = "#5A6360"      # 解約済みの文字
DOT = "#AEB6B3"          # ページ位置の点(非選択)
DANGER = "#A23B2A"       # エラー表示
ON_ACCENT = "#FFFFFF"    # ACCENT や TRIAL の上に載せる文字

# アイコン画像がないサービスのタイル色、円グラフの色(白文字が読める濃さ)
TILE_COLORS = [
    "#7A2E3A", "#2F5D50", "#1F3A5F", "#8A4B14", "#2B4C7E", "#3D4A1F",
    "#6B2D5C", "#23515E", "#4A3728", "#36594A", "#5B3F8C", "#5E2A4F",
]

# ---- 寸法 ----
GUTTER = 24        # 画面左右の余白
TAP_MIN = 44       # タップできる要素の最小サイズ
BASE_WIDTH = 390   # 基準の画面幅
BASE_HEIGHT = 844

# ---- フォント(assets/fonts/ に同梱) ----
FONT = "ZenKaku"             # 本文
FONT_BOLD = "ZenKakuBold"    # 見出し、強調
FONT_BLACK = "ZenKakuBlack"  # アプリ名、アイコンの頭文字
FONTS = {
    FONT: "/fonts/ZenKakuGothicNew-Regular.ttf",
    FONT_BOLD: "/fonts/ZenKakuGothicNew-Bold.ttf",
    FONT_BLACK: "/fonts/ZenKakuGothicNew-Black.ttf",
}
_FAMILY_BY_WEIGHT = {"regular": FONT, "bold": FONT_BOLD, "black": FONT_BLACK}


def apply(page: ft.Page) -> None:
    """ページ全体にフォントと配色を設定する(main.py が起動時に1回呼ぶ)。"""
    page.fonts = FONTS
    page.theme = ft.Theme(color_scheme_seed=ACCENT, font_family=FONT)
    page.theme_mode = ft.ThemeMode.LIGHT
    page.bgcolor = GROUND
    page.padding = 0


def text(value: str, size: float = 14, weight: str = "regular", color: str = INK, **kwargs) -> ft.Text:
    """共通フォントの文字を作る。weight は "regular" / "bold" / "black"。"""
    return ft.Text(value, size=size, color=color, font_family=_FAMILY_BY_WEIGHT[weight], **kwargs)


def tile_color(index: int) -> str:
    """番号に応じたタイル色を返す(色数を超えたら最初に戻る)。"""
    return TILE_COLORS[index % len(TILE_COLORS)]


def yen(amount: int) -> str:
    """金額を「¥1,234」の形にする。"""
    return f"¥{amount:,}"
