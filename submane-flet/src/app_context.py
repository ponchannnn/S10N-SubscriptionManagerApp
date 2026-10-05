"""main.pyが画面へ渡す，共通APIと画面切り替え関数を保持する．"""

from dataclasses import dataclass
from typing import Awaitable, Callable

from api_client import ApiClient


@dataclass
class AppContext:
    """UIのページ1つにつき1つの状態．APIトークンを画面へ渡さない．"""

    api: ApiClient
    navigate: Callable[[str], Awaitable[None]]
    logged_in: bool = False
    route: str = "/account"
    generation: int = 0
    detail_id: str = ""
    auth_busy: bool = False
    account_notice: str = ""
