from __future__ import annotations

from datetime import date

import streamlit as st

from .engine import evaluate_case
from .models import CaseInput, CompanyInput, DeadlineInput, WageInput, WorkerInput
from .render import render_checklist, render_missing_documents, render_reason


st.set_page_config(page_title="キャリアアップ助成金（正社員化コース）申請支援", layout="wide")
st.title("キャリアアップ助成金（正社員化コース）申請支援AI（ローカル）")

st.caption("入力に基づき、対象判定・不足資料・理由文ドラフト・提出前チェック・NG警告を生成します。")


with st.sidebar:
    st.subheader("会社情報")
    company_name = st.text_input("会社名", value="株式会社サンプル")
    employee_count = st.number_input("従業員数（常時雇用）", min_value=1, value=20, step=1)
    is_large_company = st.toggle("大企業", value=False)

    st.subheader("キャリアアップ計画")
    plan_start = st.date_input("計画開始日", value=date(2026, 4, 1))
    plan_end = st.date_input("計画終了日", value=date(2031, 3, 31))

    st.subheader("就業規則等（有無・整備状況）")
    conversion_rule_exists = st.toggle("正社員転換制度の規定がある", value=True)
    conversion_rule_has_objective = st.toggle("手続き・要件・実施時期が客観的に明記", value=True)
    regular_bonus_or_retirement = st.toggle("正社員に賞与または退職金制度が適用", value=True)
    regular_raise = st.toggle("正社員に昇給が適用", value=True)
    nonregular_wage_diff = st.toggle("非正規は正社員と賃金の額/計算方法が異なる規定がある", value=True)
    work_rules_not_edited = st.toggle("添付は原本/複写（加工・転記物ではない）", value=True)


col1, col2 = st.columns(2, gap="large")

with col1:
    st.subheader("対象労働者")
    worker_name = st.text_input("氏名（表示用）", value="山田 太郎")
    hire_date = st.date_input("雇入日", value=date(2025, 7, 1))
    conversion_date = st.date_input("転換日（正社員化日）", value=date(2026, 4, 1))
    employment_before = st.selectbox("転換前の雇用区分", options=["有期", "無期", "派遣"], index=0)
    employment_after = st.selectbox("転換後の雇用区分", options=["正社員", "多様な正社員"], index=0)
    tenure_months = st.number_input("転換前の雇用期間（月）", min_value=0, value=9, step=1)

    st.markdown("#### 属性（該当時のみ）")
    is_new_graduate = st.toggle("新規学卒者", value=False)
    months_since_grad = st.number_input("（新規学卒者のみ）卒業後〜雇入まで（月）", min_value=0, value=13, step=1) if is_new_graduate else None
    is_foreign_excluded = st.toggle("外国人の除外類型（技能実習/特定技能1号等）", value=False)
    has_probation = st.toggle("転換後に試用期間がある", value=False)
    over_retire = st.toggle("転換日に定年年齢超", value=False)
    social_insurance = st.toggle("転換後、社会保険に加入（適用事業所等）", value=True)

with col2:
    st.subheader("賃金（3%増額の簡易判定）")
    before_total = st.number_input("転換前6か月の賃金総額（円）", min_value=0, value=1200000, step=10000)
    after_total = st.number_input("転換後6か月の賃金総額（円）", min_value=0, value=1250000, step=10000)
    increase_percent = (after_total - before_total) / before_total * 100 if before_total > 0 else 0.0
    st.write(f"増額率（参考）: **{increase_percent:.2f}%**")

    st.subheader("申請期限（2か月）")
    wage_payment_date = st.date_input("6か月分の賃金を支給した日（実際）", value=date(2026, 10, 10))
    submit_date = st.date_input("提出予定日", value=date(2026, 11, 1))

    st.subheader("理由文用メモ")
    background_issue = st.text_area("背景課題", value="非正規雇用者の定着と人材育成が課題であったため。", height=80)
    worker_role_expectation = st.text_area("対象者の役割/期待", value="現場の中核業務を担い、後進育成も期待できるため。", height=80)
    expected_outcome = st.text_area("正社員化で実現したいこと", value="定着率向上と技能継承、サービス品質の安定。", height=80)
    conversion_procedure = st.text_input("手続き", value="面接・評価により判定")
    conversion_requirements = st.text_input("要件", value="勤続年数・人事評価等（客観基準）")
    conversion_timing = st.text_input("実施時期", value="毎年4月・10月")


case = CaseInput(
    company=CompanyInput(
        company_name=company_name,
        employee_count=int(employee_count),
        is_large_company=bool(is_large_company),
        career_up_plan_start=plan_start,
        career_up_plan_end=plan_end,
        conversion_rule_exists=bool(conversion_rule_exists),
        conversion_rule_has_objective_procedure=bool(conversion_rule_has_objective),
        regular_rule_has_bonus_or_retirement=bool(regular_bonus_or_retirement),
        regular_rule_has_raise=bool(regular_raise),
        nonregular_rule_has_wage_diff=bool(nonregular_wage_diff),
        work_rules_not_edited=bool(work_rules_not_edited),
    ),
    worker=WorkerInput(
        worker_name=worker_name,
        hire_date=hire_date,
        conversion_date=conversion_date,
        employment_before=employment_before,  # type: ignore[arg-type]
        employment_after=employment_after,  # type: ignore[arg-type]
        tenure_months_before_conversion=int(tenure_months),
        is_new_graduate=bool(is_new_graduate),
        months_since_graduation_at_hire=int(months_since_grad) if months_since_grad is not None else None,
        is_foreign_trainee_or_specified_skill1=bool(is_foreign_excluded),
        has_probation_after_conversion=bool(has_probation),
        is_over_retirement_age_at_conversion=bool(over_retire),
        social_insurance_applied_after_conversion=bool(social_insurance),
    ),
    wage=WageInput(
        before_total_yen_6m=int(before_total),
        after_total_yen_6m=int(after_total),
        increase_percent=float(increase_percent),
    ),
    deadline=DeadlineInput(
        six_month_wage_payment_date=wage_payment_date,
        application_submit_date=submit_date,
    ),
)

ev = evaluate_case(case)

st.divider()
st.subheader("① 対象判定チェック")
st.write(f"総合判定: **{'OK（可能性高）' if ev.eligible else 'NG（要件未達の可能性）'}**")
st.caption(ev.summary)

for ci in ev.checks:
    if ci.level == "OK":
        st.success(f"{ci.title}：{ci.detail}")
    elif ci.level == "WARN":
        st.warning(f"{ci.title}：{ci.detail}")
    else:
        st.error(f"{ci.title}：{ci.detail}")

st.subheader("⑤ NGになりやすいポイント（警告）")
if ev.ng_warnings:
    for wmsg in ev.ng_warnings:
        st.warning(wmsg)
else:
    st.info("特記事項なし")

st.subheader("② 不足資料一覧")
missing_text = render_missing_documents(ev.missing_documents)
st.text_area("不足資料一覧（コピー用）", value=missing_text, height=260)

st.subheader("④ 提出前チェックリスト")
checklist_text = render_checklist(ev.ng_warnings)
st.text_area("提出前チェックリスト（コピー用）", value=checklist_text, height=260)

st.subheader("③ 申請理由文ドラフト")
reason_text = render_reason(
    {
        "company_name": company_name,
        "background_issue": background_issue,
        "worker_role_expectation": worker_role_expectation,
        "expected_outcome": expected_outcome,
        "conversion_procedure": conversion_procedure,
        "conversion_requirements": conversion_requirements,
        "conversion_timing": conversion_timing,
        "worker_name": worker_name,
        "hire_date": str(hire_date),
        "conversion_date": str(conversion_date),
        "employment_before": employment_before,
        "employment_after": employment_after,
        "regular_benefit_notes": "就業規則等に基づき適用（賞与/退職金・昇給）。",
        "social_insurance_notes": "転換後に社会保険適用。" if social_insurance else "社会保険適用状況は要確認。",
        "wage_increase_percent": f"{increase_percent:.2f}",
        "wage_before_summary": f"{before_total:,}円/6か月",
        "wage_after_summary": f"{after_total:,}円/6か月",
    }
)
st.text_area("理由文ドラフト（コピー用）", value=reason_text, height=360)

