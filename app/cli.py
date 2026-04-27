from __future__ import annotations

import argparse
import json
from datetime import date
from pathlib import Path

from .engine import evaluate_case
from .models import CaseInput, CompanyInput, DeadlineInput, WageInput, WorkerInput
from .render import render_checklist, render_missing_documents, render_reason


def _parse_date(s: str) -> date:
    y, m, d = s.split("-")
    return date(int(y), int(m), int(d))


def load_case_from_json(path: Path) -> CaseInput:
    data = json.loads(path.read_text(encoding="utf-8"))

    c = data["company"]
    w = data["worker"]
    wage = data["wage"]
    dl = data["deadline"]

    return CaseInput(
        company=CompanyInput(
            company_name=c["company_name"],
            employee_count=int(c["employee_count"]),
            is_large_company=bool(c.get("is_large_company", False)),
            career_up_plan_start=_parse_date(c["career_up_plan_start"]),
            career_up_plan_end=_parse_date(c["career_up_plan_end"]),
            conversion_rule_exists=bool(c["conversion_rule_exists"]),
            conversion_rule_has_objective_procedure=bool(c["conversion_rule_has_objective_procedure"]),
            regular_rule_has_bonus_or_retirement=bool(c["regular_rule_has_bonus_or_retirement"]),
            regular_rule_has_raise=bool(c["regular_rule_has_raise"]),
            nonregular_rule_has_wage_diff=bool(c["nonregular_rule_has_wage_diff"]),
            work_rules_not_edited=bool(c.get("work_rules_not_edited", True)),
        ),
        worker=WorkerInput(
            worker_name=w["worker_name"],
            hire_date=_parse_date(w["hire_date"]),
            conversion_date=_parse_date(w["conversion_date"]),
            employment_before=w["employment_before"],
            employment_after=w["employment_after"],
            tenure_months_before_conversion=int(w["tenure_months_before_conversion"]),
            is_new_graduate=bool(w.get("is_new_graduate", False)),
            months_since_graduation_at_hire=w.get("months_since_graduation_at_hire"),
            is_foreign_trainee_or_specified_skill1=bool(w.get("is_foreign_trainee_or_specified_skill1", False)),
            has_probation_after_conversion=bool(w.get("has_probation_after_conversion", False)),
            is_over_retirement_age_at_conversion=bool(w.get("is_over_retirement_age_at_conversion", False)),
            social_insurance_applied_after_conversion=bool(w.get("social_insurance_applied_after_conversion", True)),
        ),
        wage=WageInput(
            before_total_yen_6m=int(wage["before_total_yen_6m"]),
            after_total_yen_6m=int(wage["after_total_yen_6m"]),
            increase_percent=float(wage["increase_percent"]),
        ),
        deadline=DeadlineInput(
            six_month_wage_payment_date=_parse_date(dl["six_month_wage_payment_date"]),
            application_submit_date=_parse_date(dl["application_submit_date"]),
        ),
    )


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", required=True, help="入力JSONへのパス")
    args = ap.parse_args()

    case = load_case_from_json(Path(args.input))
    ev = evaluate_case(case)

    print("=== 対象判定 ===")
    print("総合:", "OK（可能性高）" if ev.eligible else "NG（要件未達の可能性）")
    print(ev.summary)
    print()
    for ci in ev.checks:
        print(f"[{ci.level}] {ci.title} - {ci.detail}")

    print("\n=== NG警告 ===")
    for w in ev.ng_warnings:
        print(f"- {w}")

    print("\n=== 不足資料一覧 ===")
    print(render_missing_documents(ev.missing_documents))

    print("\n=== 提出前チェックリスト ===")
    print(render_checklist(ev.ng_warnings))

    print("\n=== 申請理由文ドラフト ===")
    print(
        render_reason(
            {
                "company_name": case.company.company_name,
                "background_issue": "（入力JSONのbackground_issueを入れてください）",
                "worker_role_expectation": "（入力JSONのworker_role_expectationを入れてください）",
                "expected_outcome": "（入力JSONのexpected_outcomeを入れてください）",
                "conversion_procedure": "（入力JSONのconversion_procedureを入れてください）",
                "conversion_requirements": "（入力JSONのconversion_requirementsを入れてください）",
                "conversion_timing": "（入力JSONのconversion_timingを入れてください）",
                "worker_name": case.worker.worker_name,
                "hire_date": str(case.worker.hire_date),
                "conversion_date": str(case.worker.conversion_date),
                "employment_before": case.worker.employment_before,
                "employment_after": case.worker.employment_after,
                "regular_benefit_notes": "就業規則等に基づき適用（賞与/退職金・昇給）。",
                "social_insurance_notes": "転換後に社会保険適用。" if case.worker.social_insurance_applied_after_conversion else "社会保険適用状況は要確認。",
                "wage_increase_percent": f"{case.wage.increase_percent:.2f}",
                "wage_before_summary": f"{case.wage.before_total_yen_6m:,}円/6か月",
                "wage_after_summary": f"{case.wage.after_total_yen_6m:,}円/6か月",
            }
        )
    )


if __name__ == "__main__":
    main()

