from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from typing import List, Literal, Optional, Tuple

from dateutil.relativedelta import relativedelta

from .models import CaseInput, EmploymentAfter

ResultLevel = Literal["OK", "WARN", "NG"]


@dataclass(frozen=True)
class CheckItem:
    id: str
    title: str
    level: ResultLevel
    detail: str


@dataclass(frozen=True)
class SubsidyEstimate:
    base_amount: int               # 基本支給額（1期分）
    total_amount: int              # 最大合計（重点2期含む）
    period_count: int              # 申請可能期数
    addition_rule: int             # 加算①転換制度新設
    addition_diverse: int          # 加算②多様な正社員
    addition_info: int             # 加算③情報公表
    total_addition: int            # 加算合計
    grand_total: int               # 本体＋加算
    breakdown: str                 # 内訳説明


@dataclass(frozen=True)
class Evaluation:
    eligible: bool
    summary: str
    checks: List[CheckItem]
    missing_documents: List[str]
    ng_warnings: List[str]
    subsidy: Optional[SubsidyEstimate]
    deadline_info: str
    wage_detail: str


# ─────────────────────────────────────────
#  補助関数
# ─────────────────────────────────────────

def _between(d: date, start: date, end: date) -> bool:
    return start <= d <= end


def _application_deadline(payment_date: date) -> date:
    """6か月賃金支払日の翌日から2か月以内の末日"""
    start = payment_date + timedelta(days=1)
    return start + relativedelta(months=2) - timedelta(days=1)


def _is_diverse_regular(emp_after: EmploymentAfter) -> bool:
    return emp_after in ("勤務地限定正社員", "職務限定正社員", "短時間正社員")


# ─────────────────────────────────────────
#  支給額計算
# ─────────────────────────────────────────

def _calc_base_amount(
    is_large: bool,
    emp_before: str,
    is_priority: bool,
    period: int,  # 1 or 2
) -> int:
    """
    令和8年度版 正社員化コース基本支給額
    有期→正規 重点: 中小40万×2期, 大企業30万×2期
    有期→正規 通常: 中小40万×1期, 大企業30万×1期
    無期→正規 重点: 中小20万×2期, 大企業15万×2期
    無期→正規 通常: 中小20万×1期, 大企業15万×1期
    """
    is_kikou = emp_before in ("有期", "派遣")  # 有期・派遣→正規

    if is_kikou:
        unit = 300_000 if is_large else 400_000
    else:
        unit = 150_000 if is_large else 200_000

    if not is_priority:
        return unit if period == 1 else 0
    else:
        return unit  # 各期ごとの単価


def _calc_subsidy(case: CaseInput) -> SubsidyEstimate:
    c = case.company
    w = case.worker

    is_priority = w.priority_type != "none"
    periods = 2 if is_priority else 1

    unit = _calc_base_amount(c.is_large_company, w.employment_before, is_priority, 1)
    base_per_period = unit
    total_base = unit * periods

    # 加算①転換制度新設
    add1 = (150_000 if c.is_large_company else 200_000) if c.new_conversion_rule else 0

    # 加算②多様な正社員制度新設
    add2 = (300_000 if c.is_large_company else 400_000) if c.new_diverse_regular_rule else 0

    # 加算③情報公表
    add3 = (150_000 if c.is_large_company else 200_000) if c.info_published else 0

    total_add = add1 + add2 + add3
    grand = total_base + total_add

    # 内訳文
    emp_label = "有期→正規" if w.employment_before in ("有期", "派遣") else "無期→正規"
    size_label = "大企業" if c.is_large_company else "中小企業"
    priority_label = f"重点支援対象者({w.priority_type})" if is_priority else "通常"

    parts = [
        f"【基本】{size_label}×{emp_label}×{priority_label}",
        f"　1期: {base_per_period:,}円" + (f" × {periods}期 = {total_base:,}円" if periods > 1 else ""),
    ]
    if add1:
        parts.append(f"【加算①転換制度新設】+{add1:,}円")
    if add2:
        parts.append(f"【加算②多様な正社員制度新設】+{add2:,}円")
    if add3:
        parts.append(f"【加算③情報公表】+{add3:,}円")
    if total_add:
        parts.append(f"【加算合計】{total_add:,}円")
    parts.append(f"【合計（最大）】{grand:,}円")

    return SubsidyEstimate(
        base_amount=base_per_period,
        total_amount=total_base,
        period_count=periods,
        addition_rule=add1,
        addition_diverse=add2,
        addition_info=add3,
        total_addition=total_add,
        grand_total=grand,
        breakdown="\n".join(parts),
    )


# ─────────────────────────────────────────
#  メイン評価
# ─────────────────────────────────────────

def evaluate_case(case: CaseInput) -> Evaluation:
    checks: List[CheckItem] = []
    missing: List[str] = []
    warnings: List[str] = []

    c = case.company
    w = case.worker
    wage = case.wage
    dl = case.deadline

    # ① 計画期間
    in_plan = _between(w.conversion_date, c.career_up_plan_start, c.career_up_plan_end)
    checks.append(CheckItem(
        id="company.plan_period",
        title="キャリアアップ計画期間内の転換",
        level="OK" if in_plan else "NG",
        detail=f"転換日={w.conversion_date} / 計画期間={c.career_up_plan_start}〜{c.career_up_plan_end}",
    ))
    if not in_plan:
        warnings.append("転換日がキャリアアップ計画期間外のため、原則対象外です。")
        missing.append("キャリアアップ計画書（転換日を含む計画期間のもの）")

    # ② 転換制度の規定
    if not c.conversion_rule_exists:
        checks.append(CheckItem(
            id="company.conversion_rule",
            title="正社員転換制度の規定（就業規則等）",
            level="NG",
            detail="転換制度の規定が確認できません。",
        ))
        warnings.append("就業規則等に転換制度の規定がない場合は支給対象外です。")
        missing.append("就業規則等（転換制度の規定が確認できるもの）")
    else:
        checks.append(CheckItem(
            id="company.conversion_rule",
            title="正社員転換制度の規定（就業規則等）",
            level="OK",
            detail="転換制度の規定あり。",
        ))
        if not c.conversion_rule_has_objective_procedure:
            checks.append(CheckItem(
                id="company.conversion_objective",
                title="手続き・要件・実施時期の客観性",
                level="NG",
                detail="転換の手続き/要件（勤続年数・人事評価等）/実施時期が就業規則等に明示されていない可能性があります。",
            ))
            warnings.append("転換要件の客観性が不十分な場合は対象外になります（口頭明示は不可）。")
        else:
            checks.append(CheckItem(
                id="company.conversion_objective",
                title="手続き・要件・実施時期の客観性",
                level="OK",
                detail="客観的な転換制度として確認。",
            ))

    # ③ 正社員定義（賞与/退職金＋昇給）
    regular_ok = c.regular_rule_has_bonus_or_retirement and c.regular_rule_has_raise
    checks.append(CheckItem(
        id="company.regular_definition",
        title="正社員定義（賞与/退職金 + 昇給）",
        level="OK" if regular_ok else "NG",
        detail="転換後の正社員区分に、賞与または退職金制度と昇給の規定が必要です。",
    ))
    if not regular_ok:
        warnings.append("正社員の定義（賞与/退職金＋昇給）が就業規則等で確認できないと不支給リスクがあります。")
        missing.append("就業規則等（正社員の賞与/退職金・昇給の規定箇所）")

    # ④ 非正規の賃金差
    if not c.nonregular_rule_has_wage_diff:
        checks.append(CheckItem(
            id="company.nonregular_wage_diff",
            title="非正規雇用区分の賃金差（就業規則等）",
            level="NG",
            detail="正社員と異なる賃金の額または計算方法が就業規則等で確認できません。",
        ))
        warnings.append("就業規則等で正規・非正規の賃金差が規定されていないと対象外になります（実態差だけでは不可）。")
        missing.append("就業規則等（非正規雇用区分の適用範囲・賃金規定）")
    else:
        checks.append(CheckItem(
            id="company.nonregular_wage_diff",
            title="非正規雇用区分の賃金差（就業規則等）",
            level="OK",
            detail="正社員と異なる賃金の額/計算方法の差が確認できます。",
        ))

    # ⑤ 添付書類の品質
    if not c.work_rules_not_edited:
        checks.append(CheckItem(
            id="company.documents_original",
            title="添付書類（原本/複写）",
            level="WARN",
            detail="加工・転記した書類は不正受給認定リスクになり得ます。原本または原本の複写を提出してください。",
        ))
        warnings.append("添付書類の加工・転記は不正受給リスクです（原本/複写が原則）。")

    # ⑥ 外国人除外類型
    if w.is_foreign_trainee_or_specified_skill1:
        checks.append(CheckItem(
            id="worker.foreign_excluded",
            title="外国人除外類型（技能実習・特定技能1号等）",
            level="NG",
            detail="技能実習生・特定技能1号等は正社員化コースの対象外になります。",
        ))
        warnings.append("外国人技能実習生・特定技能1号等は対象外です。在留資格を確認してください。")
    else:
        checks.append(CheckItem(
            id="worker.foreign_excluded",
            title="外国人除外類型",
            level="OK",
            detail="除外類型に該当しない前提。",
        ))

    # ⑦ 新規学卒者（雇入れから1年）
    if w.is_new_graduate and (w.months_since_graduation_at_hire is not None) and (w.months_since_graduation_at_hire < 12):
        checks.append(CheckItem(
            id="worker.new_graduate_1y",
            title="新規学卒者（雇入れから1年未満）",
            level="NG",
            detail=f"新規学卒者で雇入れから{w.months_since_graduation_at_hire}か月未満のため対象外になります（1年経過が必要）。",
        ))
        warnings.append("新規学卒者は雇入れから1年経過するまで支給対象外です（令和8年4月1日雇用者は令和9年3月31日まで対象外）。")
    else:
        checks.append(CheckItem(
            id="worker.new_graduate_1y",
            title="新規学卒者（1年要件）",
            level="OK",
            detail="新規学卒者1年要件に抵触なし。",
        ))

    # ⑧ 定年超
    if w.is_over_retirement_age_at_conversion:
        checks.append(CheckItem(
            id="worker.retirement_age",
            title="定年超の正社員転換",
            level="NG",
            detail="転換日から定年までの期間が1年未満の場合は対象外になります。",
        ))
        warnings.append("定年までの期間が1年未満の場合は対象外です。")
    else:
        checks.append(CheckItem(
            id="worker.retirement_age",
            title="定年要件（転換日〜定年まで1年以上）",
            level="OK",
            detail="定年要件を充足。",
        ))

    # ⑨ 試用期間
    if w.has_probation_after_conversion:
        checks.append(CheckItem(
            id="worker.probation",
            title="転換後の試用期間",
            level="WARN",
            detail="転換後に試用期間を設けると、賃金比較・申請期間の起算日が「試用期間終了日の翌日」にズレます。就業規則に試用期間の定めがある場合は要注意。",
        ))
        warnings.append("転換後の試用期間は無期→正規とみなされる場合があります。申請期間の起算日がずれる点を確認してください。")

    # ⑩ 転換前雇用期間（6か月）
    is_dispatch = w.employment_before == "派遣"
    if not is_dispatch and w.tenure_months_before_conversion < 6:
        checks.append(CheckItem(
            id="worker.tenure_6m",
            title="転換前の雇用期間（通算6か月以上）",
            level="NG",
            detail=f"転換前の有期/無期雇用期間が{w.tenure_months_before_conversion}か月です（6か月以上の適用が必要）。",
        ))
        warnings.append("有期雇用等の適用を通算6か月以上受けていない場合は対象外です。空白期間（6か月以上）があると通算されない点も注意。")
    else:
        label = "派遣受入6か月以上" if is_dispatch else f"{w.tenure_months_before_conversion}か月"
        checks.append(CheckItem(
            id="worker.tenure_6m",
            title="転換前雇用期間",
            level="OK",
            detail=f"雇用期間：{label}（要件充足）。",
        ))

    # ⑪ 社会保険
    if not w.social_insurance_applied_after_conversion:
        checks.append(CheckItem(
            id="worker.social_insurance",
            title="転換後の社会保険加入",
            level="WARN",
            detail="適用事業所では正社員転換後に社会保険への加入が必要です。",
        ))
        warnings.append("適用事業所の場合、転換後に社会保険の加入がないと対象外になります。")
        missing.append("社会保険の加入が確認できる資料（標準報酬月額決定通知書等）")
    else:
        checks.append(CheckItem(
            id="worker.social_insurance",
            title="転換後の社会保険加入",
            level="OK",
            detail="社会保険加入確認済み。",
        ))

    # ⑫ 重点支援対象者の自動推定
    if w.priority_type == "none":
        # 雇入れから3年以上 → a
        hire_to_conv = relativedelta(w.conversion_date, w.hire_date)
        months_tenure = hire_to_conv.years * 12 + hire_to_conv.months
        if months_tenure >= 36:
            checks.append(CheckItem(
                id="worker.priority_auto",
                title="重点支援対象者（自動判定）",
                level="WARN",
                detail=f"雇入れから{months_tenure}か月経過しており、重点支援対象者a（3年以上の有期）に該当する可能性があります。重点支援フラグを「a」に変更すると支給額が上がります。",
            ))
            warnings.append(f"雇入れから{months_tenure}か月 → 重点支援対象者a（有期3年以上）の可能性。確認して重点フラグを設定してください。")
    elif w.priority_type == "b":
        # b の要件確認
        if w.past5y_regular_months is not None and w.past5y_regular_months > 12:
            checks.append(CheckItem(
                id="worker.priority_b",
                title="重点支援対象者b：過去5年間の正規期間",
                level="NG",
                detail=f"過去5年間の正規雇用期間が{w.past5y_regular_months}か月（1年＝12か月超）のため、bの要件①を満たしません。",
            ))
            warnings.append("重点支援b：過去5年間の正規雇用期間が合計1年超の場合はbに該当しません。")
        if w.past1y_regular:
            checks.append(CheckItem(
                id="worker.priority_b2",
                title="重点支援対象者b：過去1年以内の正規雇用",
                level="NG",
                detail="過去1年以内に正規雇用労働者として雇用されていた場合、bの要件②を満たしません（事業主都合・正当な理由ある自己都合退職を除く）。",
            ))
            warnings.append("重点支援b：過去1年以内に正規雇用されていた場合はbに該当しません（一部例外あり）。")
    elif w.priority_type == "a":
        # a：5年超は無期とみなすため注意
        hire_to_conv = relativedelta(w.conversion_date, w.hire_date)
        months_tenure = hire_to_conv.years * 12 + hire_to_conv.months
        if months_tenure > 60:
            checks.append(CheckItem(
                id="worker.priority_a_over5y",
                title="重点支援対象者a：通算5年超",
                level="WARN",
                detail=f"通算雇用期間が{months_tenure}か月（5年超）のため、無期雇用労働者とみなされます。重点支援aには該当せず、転換前雇用形態が「無期」として扱われる点を確認してください。",
            ))
            warnings.append("有期雇用期間が通算5年超 → 無期雇用労働者とみなされます（重点aには非該当）。支給単価が無期→正規の単価になります。")

    # ⑬ 多様な正社員への転換時の追加確認
    if _is_diverse_regular(w.employment_after):
        checks.append(CheckItem(
            id="worker.diverse_regular",
            title=f"{w.employment_after}への転換：通常の正社員の同時雇用",
            level="WARN",
            detail=f"多様な正社員（{w.employment_after}）への転換の場合、転換日において対象労働者以外に通常の正社員（多様な正社員を除く）を1名以上雇用していることが必要です。",
        ))
        warnings.append(f"{w.employment_after}への転換：転換日時点で通常の正社員が在籍しているか確認してください。")
        missing.append(f"{w.employment_after}の雇用区分が規定されている就業規則等（制度導入前後）")
        missing.append("転換日時点の正社員雇用を確認できる雇用契約書等")

    # ⑭ 賃金3%増額
    pct = wage.increase_percent
    wage_ok = pct >= 3.0

    if wage.use_hourly_compare:
        wage_detail = (
            f"【時給換算比較】\n"
            f"  転換前: {wage.before_total_yen_6m:,}円 ÷ {wage.before_hours_6m:.1f}時間 = {wage.before_hourly:,.1f}円/時\n"
            f"  転換後: {wage.after_total_yen_6m:,}円 ÷ {wage.after_hours_6m:.1f}時間 = {wage.after_hourly:,.1f}円/時\n"
            f"  増額率: {pct:.1f}%（小数点第1位以下切捨）"
        )
    else:
        wage_detail = (
            f"【総額比較（所定労働時間・支給形態に変更なし）】\n"
            f"  転換前6か月: {wage.before_total_yen_6m:,}円\n"
            f"  転換後6か月: {wage.after_total_yen_6m:,}円\n"
            f"  増額率: {pct:.1f}%（小数点第1位以下切捨）"
        )

    checks.append(CheckItem(
        id="wage.3percent",
        title="賃金3%以上の増額（四捨五入不可・切捨）",
        level="OK" if wage_ok else "NG",
        detail=f"増額率={pct:.1f}%（3.0%以上が必要。小数点第1位以下切捨）",
    ))
    if not wage_ok:
        warnings.append(f"賃金増額率が{pct:.1f}%で要件未達（3.0%以上が必要）。通勤手当・残業代・賞与を含めていないか確認してください。")
        missing.append("転換前後6か月の賃金台帳・給与明細（賃金上昇要件確認ツール記入済み）")

    # ⑮ 固定残業代チェック警告
    checks.append(CheckItem(
        id="wage.fixed_ot",
        title="固定残業代の変動確認",
        level="WARN",
        detail="固定残業代の総額または時間相当数を転換前後で減らしている場合は、含めた場合/含めない場合の両方で3%以上を確認する必要があります。",
    ))

    # ⑯ 申請期限
    deadline_end = _application_deadline(dl.six_month_wage_payment_date)
    within = dl.application_submit_date <= deadline_end
    checks.append(CheckItem(
        id="deadline.within_2m",
        title="支給申請期間（6か月賃金支払日翌日から2か月以内）",
        level="OK" if within else "NG",
        detail=(
            f"6か月賃金支払日={dl.six_month_wage_payment_date} / "
            f"申請期限={deadline_end} / 提出予定日={dl.application_submit_date}"
        ),
    ))
    if not within:
        warnings.append(
            f"申請期間超過です。期限：{deadline_end}。郵送の場合は到着日基準なので余裕を持って提出してください。"
        )

    deadline_info = (
        f"申請期限（目安）: {deadline_end}\n"
        f"6か月賃金支払日: {dl.six_month_wage_payment_date}\n"
        f"提出予定日: {dl.application_submit_date}\n"
        f"状態: {'✅ 期限内' if within else '❌ 期限超過'}"
    )

    # ⑰ 必須書類（共通）
    base_docs = [
        "支給申請書（所定様式第3号・別添様式1-1、1-2）",
        "支給要件確認申立書（共通要領様式第1号）",
        "キャリアアップ計画書（管轄労働局受理済み写し・変更届含む）",
        "就業規則等（正社員定義・非正規区分・転換制度・賃金規定が確認できるもの）",
        "対象労働者の雇用契約書/労働条件通知書（転換前・転換後）",
        "賃金台帳（転換前6か月・転換後6か月）＋賃金上昇要件確認ツール",
        "対象労働者が雇用された日付が分かる雇用契約書等（有期の場合）",
    ]
    for d in base_docs:
        if d not in missing:
            missing.append(d)

    # 重点支援bの場合
    if w.priority_type == "b":
        missing.append("様式第3号別添様式1-5（キャリアアップ助成金対象者確認票）※対象労働者本人署名原本")

    # 新規学卒者対応
    if w.is_new_graduate:
        missing.append("対象労働者の応募書類等または本人署名入り申立書（最終学歴卒業年月日・入社までの就労経験なし）")

    def dedupe(xs):
        seen = set()
        out = []
        for x in xs:
            if x not in seen:
                seen.add(x)
                out.append(x)
        return out

    eligible = all(ci.level != "NG" for ci in checks)

    subsidy = _calc_subsidy(case) if eligible else None

    summary = (
        f"{'✅ 申請できる可能性が高い' if eligible else '❌ 要件未達/要確認'}（入力情報ベース）"
    )

    return Evaluation(
        eligible=eligible,
        summary=summary,
        checks=checks,
        missing_documents=dedupe(missing),
        ng_warnings=dedupe(warnings),
        subsidy=subsidy,
        deadline_info=deadline_info,
        wage_detail=wage_detail,
    )
