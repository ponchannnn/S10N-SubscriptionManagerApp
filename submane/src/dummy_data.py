"""APIができるまで使うダミーデータ。

金額・日時・URLはすべて動作確認用の仮の値で、実際のサービスの料金やURLではない。
項目は README 5章「アプリが必要とするサブスク1件のデータ」に合わせている
(+ 無料トライアルの終了日時 trial_end_at)。
"""


def _sub(sub_id, name, cycle, amount, joined_at, status="active", trial_end_at=None, plan_name=None):
    """ダミーのサブスク1件を作る。"""
    slug = f"service-{sub_id}"
    return {
        "id": sub_id,
        "name": name,
        "icon": None,  # APIからアイコンURLを受け取るまでは頭文字のタイルを表示
        "plan_name": plan_name or ("月額プラン" if cycle == "monthly" else "年額プラン"),
        "cycle": cycle,
        "amount": amount,
        "joined_at": joined_at,
        "join_url": f"https://example.com/{slug}/join",
        "cancel_url": f"https://example.com/{slug}/cancel",
        "cancel_memo": "退会手続きにはログイン用のメールアドレスとパスワードの準備が必要です。",
        "status": status,
        "trial_end_at": trial_end_at,
    }


SUBSCRIPTIONS = [
    _sub(1, "Netflix", "monthly", 1500, "2025-04-12T20:15"),
    _sub(2, "Spotify", "monthly", 1000, "2024-11-03T08:40"),
    _sub(3, "Audible", "monthly", 1500, "2025-01-20T22:05", status="cancelled"),
    _sub(4, "U-NEXT", "monthly", 2200, "2026-09-20T21:00", status="trial", trial_end_at="2026-10-20T21:00"),
    _sub(5, "Amazonプライム", "yearly", 6000, "2023-10-18T12:30"),
    _sub(6, "YouTube Premium", "monthly", 1300, "2025-07-01T19:00"),
    _sub(7, "Disney+", "monthly", 1100, "2025-12-24T10:00"),
    _sub(8, "FODプレミアム", "monthly", 1000, "2025-03-08T23:10", status="cancelled"),
    _sub(9, "DAZN", "monthly", 4200, "2026-02-14T18:45"),
    _sub(10, "Apple Music", "monthly", 1100, "2024-06-30T09:20"),
    _sub(11, "Adobe CC", "yearly", 86000, "2025-11-05T14:00"),
    _sub(12, "Hulu", "monthly", 1000, "2026-01-31T21:30"),
    _sub(13, "Kindle Unlimited", "monthly", 1000, "2026-09-28T07:50", status="trial", trial_end_at="2026-10-28T07:50"),
    _sub(14, "Lemino", "monthly", 1000, "2025-05-17T16:25", status="cancelled"),
    _sub(15, "ABEMAプレミアム", "monthly", 1100, "2026-03-22T22:00"),
    _sub(16, "iCloud+", "monthly", 400, "2023-08-09T11:11", plan_name="200GB"),
    _sub(17, "dアニメストア", "monthly", 600, "2026-04-06T00:30"),
    _sub(18, "NHKオンデマンド", "monthly", 1000, "2025-08-15T13:00", status="cancelled"),
]

# 定番サービスのマスタ(名称検索用)。
# 既存のダミー契約から作る分(1件プラン)に加え、料金プランが複数ある例として
# 石井担当が作成したデモサービス(複数プランの選択UI確認用)もそのまま載せている。
SERVICES = [
    {
        "id": sub["id"],
        "name": sub["name"],
        "icon": None,
        "join_url": sub["join_url"],
        "cancel_url": sub["cancel_url"],
        "cancel_memo": sub["cancel_memo"],
        "plans": [{"name": sub["plan_name"], "cycle": sub["cycle"], "amount": sub["amount"]}],
    }
    for sub in SUBSCRIPTIONS
] + [
    {"id": "video-demo", "name": "動画サービス（デモ）",
     "join_url": "https://example.com/video/join", "cancel_url": "https://example.com/video/cancel",
     "cancel_memo": "退会手続きにはメールアドレスとパスワードの準備が必要です．",
     "plans": [{"name": "月額プラン（デモ）", "cycle": "monthly", "amount": 1000},
               {"name": "年額プラン（デモ）", "cycle": "yearly", "amount": 10000}]},
    {"id": "music-demo", "name": "音楽サービス（デモ）",
     "join_url": "https://example.com/music/join", "cancel_url": "https://example.com/music/cancel",
     "cancel_memo": "契約した窓口を確認してください．",
     "plans": [{"name": "個人プラン（デモ）", "cycle": "monthly", "amount": 800}]},
    {"id": "book-demo", "name": "読書サービス（デモ）",
     "join_url": "https://example.com/book/join", "cancel_url": "https://example.com/book/cancel",
     "cancel_memo": "パスワードの準備が必要です．",
     "plans": [{"name": "月額プラン（デモ）", "cycle": "monthly", "amount": 500}]},
]
