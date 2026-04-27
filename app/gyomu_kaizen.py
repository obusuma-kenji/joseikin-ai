"""
業務改善助成金 判定エンジン（令和8年度版）

令和8年度の主な変更点：
- コース再編：30円・45円・60円・90円（4コース）→ 50円・70円・90円（3コース）
- 助成率の基準変更：1,000円未満/以上 → 1,050円未満/以上
  ・事業場内最低賃金 1,050円未満：4/5
  ・事業場内最低賃金 1,050円以上：3/4
- 申請受付：2026年9月1日〜11月末日頃（地域別最低賃金改定に連動）
- 対象事業場：事業場内最低賃金が令和8年度地域別最低賃金未満であること
"""
from __future__ import annotations
from typing import Any, Dict

# ─────────────────────────────────────────
# 令和8年度 助成上限額テーブル（見込み）
# コース × 引き上げ人数 × 事業場規模（30人未満/それ以外）
# 単位：円
# ─────────────────────────────────────────

SUBSIDY_LIMIT_R8 = {
    "50円": {
        1:   {"under30": 400_000,  "other": 300_000},
        "2-3": {"under30": 600_000,  "other": 400_000},
        "4-6": {"under30": 700_000,  "other": 500_000},
        "7+":  {"under30": 800_000,  "other": 600_000},
        "10+special": {"under30": 1_000_000, "other": 700_000},
    },
    "70円": {
        1:   {"under30": 500_000,  "other": 400_000},
        "2-3": {"under30": 800_000,  "other": 600_000},
        "4-6": {"under30": 1_000_000, "other": 700_000},
        "7+":  {"under30": 1_100_000, "other": 900_000},
        "10+special": {"under30": 1_500_000, "other": 1_200_000},
    },
    "90円": {
        1:   {"under30": 600_000,  "other": 500_000},
        "2-3": {"under30": 900_000,  "other": 700_000},
        "4-6": {"under30": 1_500_000, "other": 1_000_000},
        "7+":  {"under30": 2_000_000, "other": 1_500_000},
        "10+special": {"under30": 3_000_000, "other": 4_500_000},
    },
}

# 助成率（令和8年度：1,050円を基準に変更）
def get_subsidy_rate(current_min_wage: int) -> float:
    """
    令和8年度基準
    事業場内最低賃金 1,050円未満 → 4/5
    事業場内最低賃金 1,050円以上 → 3/4
    """
    if current_min_wage < 1050:
        return 4 / 5
    else:
        return 3 / 4


def get_person_key(count: int, is_special: bool) -> str:
    if is_special and count >= 10:
        return "10+special"
    elif count >= 7:
        return "7+"
    elif count >= 4:
        return "4-6"
    elif count >= 2:
        return "2-3"
    else:
        return 1


def evaluate_gyomu_kaizen(
    company_name: str,
    employee_count: int,
    current_min_wage: int,
    planned_min_wage: int,
    wage_increase_amount: int,
    investment_type: str,
    investment_amount: int,
    industry: str,
) -> Dict[str, Any]:

    warnings = []
    eligible = True

    # 実際の引き上げ額
    actual_increase = (planned_min_wage - current_min_wage
                       if planned_min_wage and current_min_wage
                       else wage_increase_amount)

    # ─────────────────────────────────────────
    # コース判定（令和8年度：50円・70円・90円）
    # ─────────────────────────────────────────
    if actual_increase <= 0:
        eligible = False
        warnings.append("事業場内最低賃金の引上げが確認できません。令和8年度は50円以上の引上げが必要です。")
        course = "対象外"
    elif actual_increase < 50:
        eligible = False
        warnings.append(
            f"引上げ額が{actual_increase}円です。令和8年度は最低50円以上の引上げが必要です。"
            f"（令和7年度までの30円・45円コースは令和8年度から廃止）"
        )
        course = "対象外"
    elif actual_increase < 70:
        course = "50円"
        warnings.append(f"50円コース（引上げ{actual_increase}円）。70円以上で助成上限額が上がります。")
    elif actual_increase < 90:
        course = "70円"
        warnings.append(f"70円コース（引上げ{actual_increase}円）。90円以上で助成上限額がさらに上がります。")
    else:
        course = "90円"

    # ─────────────────────────────────────────
    # 助成率（令和8年度：1,050円基準）
    # ─────────────────────────────────────────
    rate = get_subsidy_rate(current_min_wage)
    rate_str = "4/5（80%）" if rate == 4/5 else "3/4（75%）"
    rate_basis = (
        f"事業場内最低賃金{current_min_wage}円"
        f"→{'1,050円未満のため4/5' if current_min_wage < 1050 else '1,050円以上のため3/4'}"
    )

    # ─────────────────────────────────────────
    # 設備投資チェック
    # ─────────────────────────────────────────
    if not investment_type:
        warnings.append("生産性向上のための設備投資・システム導入等の内容が未入力です。")
    if investment_amount <= 0:
        warnings.append("設備投資金額が未入力です。助成対象経費の見積もりが必要です。")

    # 重要：交付決定前に設備導入すると対象外
    warnings.append(
        "【重要】設備・機器の購入・導入は必ず交付決定後に行ってください。"
        "交付決定前に導入した場合は助成対象外となります。"
    )

    # ─────────────────────────────────────────
    # 業種チェック
    # ─────────────────────────────────────────
    restricted_industries = ["農業", "林業", "漁業"]
    if any(ind in industry for ind in restricted_industries):
        warnings.append(
            f"業種「{industry}」は一部制限がある場合があります。労働局に事前確認を推奨します。"
        )

    # ─────────────────────────────────────────
    # 申請時期の注意（令和8年度：9月開始）
    # ─────────────────────────────────────────
    warnings.append(
        "令和8年度は申請受付が9月1日開始（〜11月末頃）の見込みです。"
        "例年より申請期間が短いため、8月までに設備選定・見積取得・賃金台帳整備を済ませてください。"
    )

    # ─────────────────────────────────────────
    # 助成額の試算
    # ─────────────────────────────────────────
    is_under30 = employee_count < 30

    # 引き上げ人数は入力から推定（簡易版：1人で計算）
    person_key = 1
    size_key = "under30" if is_under30 else "other"

    if course != "対象外" and course in SUBSIDY_LIMIT_R8:
        limit = SUBSIDY_LIMIT_R8[course].get(person_key, {}).get(size_key, 0)
    else:
        limit = 0

    estimated = min(int(investment_amount * rate), limit) if investment_amount > 0 and limit > 0 else 0

    # ─────────────────────────────────────────
    # レーティング
    # ─────────────────────────────────────────
    if not eligible:
        rating = "C：要件未達（令和8年度は50円以上の引上げが必要）"
    elif len([w for w in warnings if "重要" not in w and "令和8年度" not in w]) > 1:
        rating = "B：要確認事項あり"
    else:
        rating = "A：申請可能性高"

    return {
        "eligible": eligible,
        "rating": rating,
        "summary": (
            f"【{company_name}】{course}コース / 従業員{employee_count}名 / "
            f"助成率{rate_str} / "
            f"上限{limit:,}円（1人・{size_key}） / 試算助成額：{estimated:,}円"
        ),
        "warnings": list(dict.fromkeys(warnings)),
        "estimated_subsidy": f"{estimated:,}円（試算・1人引上げの場合）",
        "subsidy_rate": f"{rate_str}（{rate_basis}）",
        "basis": (
            "令和8年度業務改善助成金（見込み）に基づく簡易試算。"
            "コース：50円・70円・90円の3コース制。"
            "助成率：事業場内最低賃金1,050円未満→4/5、1,050円以上→3/4。"
            "申請受付：2026年9月1日〜11月末頃。最終確認は管轄労働局へ。"
        ),
    }
