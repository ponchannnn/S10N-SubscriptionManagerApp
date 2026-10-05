"""サブスク一覧の並び替え。どの並び順でも解約済みは末尾にまとめる。"""

ORDER_FREQUENCY = "frequency"    # 更新頻度順(月額 → 年額)
ORDER_REGISTERED = "registered"  # 登録順
ORDER_LABELS = {ORDER_FREQUENCY: "更新頻度順", ORDER_REGISTERED: "登録順"}

_CYCLE_RANK = {"weekly": 0, "monthly": 1, "yearly": 2}  # 小さいほど更新頻度が高い


def sort_subscriptions(subs: list[dict], order: str = ORDER_FREQUENCY) -> list[dict]:
    """並び替えた新しいリストを返す(元のリストは変えない)。同順位は元の並びを保つ。"""

    def key(pair):
        index, sub = pair
        cancelled = 1 if sub.get("status") == "cancelled" else 0
        rank = _CYCLE_RANK.get(sub.get("cycle"), 9) if order == ORDER_FREQUENCY else 0
        return (cancelled, rank, index)

    return [sub for _, sub in sorted(enumerate(subs), key=key)]


def count_by_status(subs: list[dict]) -> dict:
    """件数を数える。active は「契約中(トライアル中を含む)」。"""
    cancelled = sum(1 for sub in subs if sub.get("status") == "cancelled")
    trial = sum(1 for sub in subs if sub.get("status") == "trial")
    return {"active": len(subs) - cancelled, "trial": trial, "cancelled": cancelled}
