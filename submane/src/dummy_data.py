"""定番サービスの仮マスタ．料金とURLは実サービスの現行情報ではない．"""
SERVICES = [
    {"id": "video-demo", "name": "動画サービス（デモ）", "aliases": ["動画", "video"],
     "join_url": "https://example.com/video/join", "cancel_url": "https://example.com/video/cancel",
     "cancel_memo": "退会手続きにはメールアドレスとパスワードの準備が必要です．",
     "plans": [{"name": "月額プラン（デモ）", "cycle": "monthly", "amount": 1000},
               {"name": "年額プラン（デモ）", "cycle": "yearly", "amount": 10000}]},
    {"id": "music-demo", "name": "音楽サービス（デモ）", "aliases": ["音楽", "music"],
     "join_url": "https://example.com/music/join", "cancel_url": "https://example.com/music/cancel",
     "cancel_memo": "契約した窓口を確認してください．",
     "plans": [{"name": "個人プラン（デモ）", "cycle": "monthly", "amount": 800}]},
    {"id": "book-demo", "name": "読書サービス（デモ）", "aliases": ["読書", "book"],
     "join_url": "https://example.com/book/join", "cancel_url": "https://example.com/book/cancel",
     "cancel_memo": "パスワードの準備が必要です．",
     "plans": [{"name": "月額プラン（デモ）", "cycle": "monthly", "amount": 500}]},
]
