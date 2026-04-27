from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Dict, List, Optional

import anthropic
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from .engine import evaluate_case
from .gyomu_kaizen import evaluate_gyomu_kaizen
from .models import (
    CaseInput, CompanyInput, DeadlineInput, WageInput, WorkerInput
)
from .render import render_checklist, render_missing_documents, render_reason

app = FastAPI(title="助成金診断API v2", version="2.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

LAWS_DIR = Path(__file__).resolve().parents[1] / "laws"
ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")


# ─────────────────────────────────────────
#  リクエスト/レスポンス モデル
# ─────────────────────────────────────────

class CareerUpRequest(BaseModel):
    # 基本
    company_name: str
    employee_count: int = 20
    is_large_company: bool = False
    plan_start: str
    plan_end: str
    # 就業規則等
    conversion_rule_exists: bool = True
    conversion_rule_has_objective: bool = True
    regular_has_bonus_or_retirement: bool = True
    regular_has_raise: bool = True
    nonregular_wage_diff: bool = True
    work_rules_not_edited: bool = True
    # 加算
    new_conversion_rule: bool = False
    new_diverse_regular_rule: bool = False
    info_published: bool = False
    # 対象労働者
    worker_name: str = ""
    hire_date: str
    conversion_date: str
    employment_before: str = "有期"
    employment_after: str = "正社員"
    tenure_months: int = 6
    is_new_graduate: bool = False
    months_since_grad: Optional[int] = None
    foreign_excluded: bool = False
    has_probation: bool = False
    over_retire: bool = False
    social_insurance: bool = True
    # 重点支援対象者
    priority_type: str = "none"   # "none" / "a" / "b" / "c"
    past5y_regular_months: Optional[int] = None
    past1y_regular: bool = False
    is_single_parent: bool = False
    # 賃金
    wage_before: int = 0
    wage_after: int = 0
    use_hourly_compare: bool = False
    hours_before: Optional[float] = None
    hours_after: Optional[float] = None
    # 申請期限
    six_month_pay_date: str
    submit_date: str
    payroll_closing_day: Optional[int] = None
    # 理由文用
    background_issue: str = ""
    worker_role_expectation: str = ""
    expected_outcome: str = ""
    conversion_procedure: str = ""
    conversion_requirements: str = ""
    conversion_timing: str = ""


class GyomuKaizenRequest(BaseModel):
    company_name: str
    employee_count: int = 20
    current_min_wage: int = 0
    planned_min_wage: int = 0
    wage_increase_amount: int = 0
    investment_type: str = ""
    investment_amount: int = 0
    industry: str = ""


class SubsidyInfo(BaseModel):
    base_amount: int
    total_amount: int
    period_count: int
    addition_rule: int
    addition_diverse: int
    addition_info: int
    total_addition: int
    grand_total: int
    breakdown: str


class DiagnoseResponse(BaseModel):
    eligible: bool
    rating: str
    summary: str
    fatal: List[str]
    warnings: List[str]
    checks: List[Dict[str, str]]
    missing_documents: str
    checklist: str
    reason_draft: str
    basis: str
    subsidy: Optional[SubsidyInfo]
    deadline_info: str
    wage_detail: str


class GyomuKaizenResponse(BaseModel):
    eligible: bool
    rating: str
    summary: str
    warnings: List[str]
    estimated_subsidy: str
    subsidy_rate: str
    basis: str


class AIAdviceRequest(BaseModel):
    grant_type: str
    question: str
    context: Dict[str, Any] = {}


class AIAdviceResponse(BaseModel):
    answer: str
    basis: str


# ─────────────────────────────────────────
#  ヘルパー
# ─────────────────────────────────────────

def _parse_date(s: str):
    from datetime import date
    y, m, d = s.split("-")
    return date(int(y), int(m), int(d))


def _rating(eligible: bool, warnings: list) -> str:
    if not eligible:
        return "C：現状では申請困難（要件未達）"
    if warnings:
        return "B：確認・整備後に申請可能"
    return "A：申請準備を進められる状態"


# ─────────────────────────────────────────
#  エンドポイント
# ─────────────────────────────────────────

@app.get("/")
def health():
    return {"status": "ok", "version": "2.0.0"}


@app.post("/api/diagnose/career-up", response_model=DiagnoseResponse)
def diagnose_career_up(req: CareerUpRequest):
    try:
        # 賃金増額率の計算
        if req.use_hourly_compare and req.hours_before and req.hours_after:
            wage = WageInput(
                before_total_yen_6m=req.wage_before,
                after_total_yen_6m=req.wage_after,
                before_hours_6m=req.hours_before,
                after_hours_6m=req.hours_after,
                use_hourly_compare=True,
            )
        else:
            wage = WageInput(
                before_total_yen_6m=req.wage_before,
                after_total_yen_6m=req.wage_after,
                use_hourly_compare=False,
            )

        case = CaseInput(
            company=CompanyInput(
                company_name=req.company_name,
                employee_count=req.employee_count,
                is_large_company=req.is_large_company,
                career_up_plan_start=_parse_date(req.plan_start),
                career_up_plan_end=_parse_date(req.plan_end),
                conversion_rule_exists=req.conversion_rule_exists,
                conversion_rule_has_objective_procedure=req.conversion_rule_has_objective,
                regular_rule_has_bonus_or_retirement=req.regular_has_bonus_or_retirement,
                regular_rule_has_raise=req.regular_has_raise,
                nonregular_rule_has_wage_diff=req.nonregular_wage_diff,
                work_rules_not_edited=req.work_rules_not_edited,
                new_conversion_rule=req.new_conversion_rule,
                new_diverse_regular_rule=req.new_diverse_regular_rule,
                info_published=req.info_published,
            ),
            worker=WorkerInput(
                worker_name=req.worker_name,
                hire_date=_parse_date(req.hire_date),
                conversion_date=_parse_date(req.conversion_date),
                employment_before=req.employment_before,
                employment_after=req.employment_after,
                tenure_months_before_conversion=req.tenure_months,
                is_new_graduate=req.is_new_graduate,
                months_since_graduation_at_hire=req.months_since_grad,
                is_foreign_trainee_or_specified_skill1=req.foreign_excluded,
                has_probation_after_conversion=req.has_probation,
                is_over_retirement_age_at_conversion=req.over_retire,
                social_insurance_applied_after_conversion=req.social_insurance,
                priority_type=req.priority_type,
                past5y_regular_months=req.past5y_regular_months,
                past1y_regular=req.past1y_regular,
                is_single_parent=req.is_single_parent,
            ),
            wage=wage,
            deadline=DeadlineInput(
                six_month_wage_payment_date=_parse_date(req.six_month_pay_date),
                application_submit_date=_parse_date(req.submit_date),
                payroll_closing_day=req.payroll_closing_day,
            ),
        )
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"入力エラー：{e}")

    ev = evaluate_case(case)

    fatal = [c.detail for c in ev.checks if c.level == "NG"]

    ctx = {
        "company_name": req.company_name,
        "background_issue": req.background_issue or "（未入力）",
        "worker_role_expectation": req.worker_role_expectation or "（未入力）",
        "expected_outcome": req.expected_outcome or "（未入力）",
        "conversion_procedure": req.conversion_procedure or "（未入力）",
        "conversion_requirements": req.conversion_requirements or "（未入力）",
        "conversion_timing": req.conversion_timing or "（未入力）",
        "worker_name": req.worker_name or "（未入力）",
        "hire_date": req.hire_date,
        "conversion_date": req.conversion_date,
        "employment_before": req.employment_before,
        "employment_after": req.employment_after,
        "regular_benefit_notes": "就業規則等に基づき賞与/退職金・昇給を適用。",
        "social_insurance_notes": "転換後に社会保険加入済み。" if req.social_insurance else "社会保険の加入状況は要確認。",
        "wage_increase_percent": f"{ev.wage_detail.split('増額率: ')[1].split('%')[0] if '増額率: ' in ev.wage_detail else '—'}",
        "wage_before_summary": f"{req.wage_before:,}円/6か月",
        "wage_after_summary": f"{req.wage_after:,}円/6か月",
    }

    subsidy_info = None
    if ev.subsidy:
        subsidy_info = SubsidyInfo(
            base_amount=ev.subsidy.base_amount,
            total_amount=ev.subsidy.total_amount,
            period_count=ev.subsidy.period_count,
            addition_rule=ev.subsidy.addition_rule,
            addition_diverse=ev.subsidy.addition_diverse,
            addition_info=ev.subsidy.addition_info,
            total_addition=ev.subsidy.total_addition,
            grand_total=ev.subsidy.grand_total,
            breakdown=ev.subsidy.breakdown,
        )

    return DiagnoseResponse(
        eligible=ev.eligible,
        rating=_rating(ev.eligible, ev.ng_warnings),
        summary=ev.summary,
        fatal=fatal,
        warnings=ev.ng_warnings,
        checks=[{"id": c.id, "title": c.title, "level": c.level, "detail": c.detail} for c in ev.checks],
        missing_documents=render_missing_documents(ev.missing_documents),
        checklist=render_checklist(ev.ng_warnings),
        reason_draft=render_reason(ctx),
        basis="令和8年4月8日版 キャリアアップ助成金パンフレット（PL080408 No.16）に基づく判定",
        subsidy=subsidy_info,
        deadline_info=ev.deadline_info,
        wage_detail=ev.wage_detail,
    )


@app.post("/api/diagnose/gyomu-kaizen", response_model=GyomuKaizenResponse)
def diagnose_gyomu_kaizen(req: GyomuKaizenRequest):
    result = evaluate_gyomu_kaizen(
        company_name=req.company_name,
        employee_count=req.employee_count,
        current_min_wage=req.current_min_wage,
        planned_min_wage=req.planned_min_wage,
        wage_increase_amount=req.wage_increase_amount,
        investment_type=req.investment_type,
        investment_amount=req.investment_amount,
        industry=req.industry,
    )
    return GyomuKaizenResponse(**result)


@app.post("/api/ai-advice", response_model=AIAdviceResponse)
def ai_advice(req: AIAdviceRequest):
    if not ANTHROPIC_API_KEY:
        raise HTTPException(status_code=500, detail="ANTHROPIC_API_KEY が設定されていません。")

    pdf_path = LAWS_DIR / f"{req.grant_type}-guideline.pdf"
    pdf_context = f"（{pdf_path.name} を参照）" if pdf_path.exists() else ""

    client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)

    system_prompt = f"""あなたは社会保険労務士の助成金申請支援AIです。
助成金のQ&A資料{pdf_context}に基づいて、正確・慎重に回答してください。

【重要な注意事項】
- 判定根拠となるQ&AのQ番号・ページを可能な限り明示してください
- グレーゾーンは「要確認」「労働局に相談推奨」と明示してください
- 最終判断は必ず社労士・労働局が行うことを常に前提としてください
- 断定的な表現は避け、「〜の可能性があります」「〜が原則です」と表現してください

助成金種別：{req.grant_type}
入力情報：{req.context}"""

    message = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=1500,
        system=system_prompt,
        messages=[{"role": "user", "content": req.question}],
    )

    answer = message.content[0].text
    return AIAdviceResponse(
        answer=answer,
        basis=f"Claude claude-sonnet-4-6 + {pdf_context}",
    )


# ─────────────────────────────────────────
#  両立支援等助成金 リクエスト/レスポンス
# ─────────────────────────────────────────

class PaternityLeaveRequest(BaseModel):
    employee_count: int = 20
    male_ikukyu_days: int = 5
    birth_within_8weeks: bool = True
    env_measures_count: int = 3
    has_business_plan: bool = True
    action_plan_filed: bool = True
    target_person_num: int = 1
    申出期限_超2週間: bool = False
    is_platinum_kurumin: bool = False
    info_published: bool = False

class GyomuDaitaiRequest(BaseModel):
    employee_count: int = 20
    support_type: str = "手当支給_育休"
    ikukyu_days: int = 30
    tanki_months: int = 3
    daitai_months: float = 6.0
    teate_total: int = 90000
    has_rule: bool = True
    has_kaizen: bool = True
    sharoshi_ittaku: bool = False
    is_yukikoyou: bool = False
    info_published: bool = False
    is_platinum: bool = False

class IkukyuShienRequest(BaseModel):
    is_small_company: bool = True
    stage: str = "育休取得時"
    has_mensdan: bool = True
    has_hikitsuki: bool = True
    ikukyu_months: float = 3.0
    fukki_shuro: bool = True
    info_published: bool = False

class KaigoRequest(BaseModel):
    is_small_company: bool = True
    support_type: str = "介護休業"
    has_plan: bool = True
    kaigo_kyugo_days: int = 5
    seido_count: int = 1
    seido_days: int = 30
    yuko_kazan: bool = False
    info_published: bool = False

class FlexibleRequest(BaseModel):
    is_small_company: bool = True
    seido_count: int = 3
    has_plan: bool = True
    has_shuugyou_kisoku: bool = True
    riyo_months: float = 6.0
    info_published: bool = False
    shogaiji_kakucho: bool = False

class FuninRequest(BaseModel):
    is_small_company: bool = True
    support_type: str = "A_funin"   # A_funin / B_gekkei / C_konenki
    has_kyuka_seido: bool = True
    has_shuuchi: bool = True
    has_plan: bool = True
    has_tanto: bool = True          # 両立支援担当者の選任
    riyo_count: int = 5
    chouki_kyuka_days: int = 0

class RyoritsuResponse(BaseModel):
    course_name: str
    eligible: bool
    rating: str
    max_amount: int
    amount_detail: str
    checks: List[Dict[str, str]]
    warnings: List[str]
    missing_docs: List[str]
    sharoshi_merit: str


# ─────────────────────────────────────────
#  両立支援等助成金エンドポイント
# ─────────────────────────────────────────

@app.post("/api/diagnose/paternity-leave", response_model=RyoritsuResponse)
def diagnose_paternity_leave(req: PaternityLeaveRequest):
    from .ryoritsu import evaluate_paternity_leave
    r = evaluate_paternity_leave(
        is_small_company=req.employee_count <= 300,
        employee_count=req.employee_count,
        male_육휴_days=req.male_ikukyu_days,
        birth_within_8weeks=req.birth_within_8weeks,
        env_measures_count=req.env_measures_count,
        has_business_plan=req.has_business_plan,
        action_plan_filed=req.action_plan_filed,
        target_person_num=req.target_person_num,
        申出期限_超2週間=req.申出期限_超2週間,
        is_platinum_kurumin=req.is_platinum_kurumin,
        info_published=req.info_published,
    )
    return RyoritsuResponse(
        course_name=r.course_name, eligible=r.eligible, rating=r.rating,
        max_amount=r.max_amount, amount_detail=r.amount_detail,
        checks=[{"id":c.id,"title":c.title,"level":c.level,"detail":c.detail} for c in r.checks],
        warnings=r.warnings, missing_docs=r.missing_docs, sharoshi_merit=r.sharoshi_merit,
    )

@app.post("/api/diagnose/gyomu-daitai", response_model=RyoritsuResponse)
def diagnose_gyomu_daitai(req: GyomuDaitaiRequest):
    from .ryoritsu import evaluate_gyomu_daitai
    r = evaluate_gyomu_daitai(
        employee_count=req.employee_count, support_type=req.support_type,
        ikukyu_days=req.ikukyu_days, tanki_months=req.tanki_months,
        daitai_months=req.daitai_months, teate_total=req.teate_total,
        has_rule=req.has_rule, has_kaizen=req.has_kaizen,
        sharoshi_委託=req.sharoshi_ittaku, is_yukikoyou=req.is_yukikoyou,
        info_published=req.info_published, is_platinum=req.is_platinum,
    )
    return RyoritsuResponse(
        course_name=r.course_name, eligible=r.eligible, rating=r.rating,
        max_amount=r.max_amount, amount_detail=r.amount_detail,
        checks=[{"id":c.id,"title":c.title,"level":c.level,"detail":c.detail} for c in r.checks],
        warnings=r.warnings, missing_docs=r.missing_docs, sharoshi_merit=r.sharoshi_merit,
    )

@app.post("/api/diagnose/ikukyu-shien", response_model=RyoritsuResponse)
def diagnose_ikukyu_shien(req: IkukyuShienRequest):
    from .ryoritsu import evaluate_ikukyu_shien
    r = evaluate_ikukyu_shien(
        is_small_company=req.is_small_company, stage=req.stage,
        has_mensdan=req.has_mensdan, has_hikitsuki=req.has_hikitsuki,
        ikukyu_months=req.ikukyu_months, fukki_shuro=req.fukki_shuro,
        info_published=req.info_published,
    )
    return RyoritsuResponse(
        course_name=r.course_name, eligible=r.eligible, rating=r.rating,
        max_amount=r.max_amount, amount_detail=r.amount_detail,
        checks=[{"id":c.id,"title":c.title,"level":c.level,"detail":c.detail} for c in r.checks],
        warnings=r.warnings, missing_docs=r.missing_docs, sharoshi_merit=r.sharoshi_merit,
    )

@app.post("/api/diagnose/kaigo", response_model=RyoritsuResponse)
def diagnose_kaigo(req: KaigoRequest):
    from .ryoritsu import evaluate_kaigo
    r = evaluate_kaigo(
        is_small_company=req.is_small_company, support_type=req.support_type,
        has_plan=req.has_plan, kaigo_kyugo_days=req.kaigo_kyugo_days,
        seido_count=req.seido_count, seido_days=req.seido_days,
        yuko_kazan=req.yuko_kazan, info_published=req.info_published,
    )
    return RyoritsuResponse(
        course_name=r.course_name, eligible=r.eligible, rating=r.rating,
        max_amount=r.max_amount, amount_detail=r.amount_detail,
        checks=[{"id":c.id,"title":c.title,"level":c.level,"detail":c.detail} for c in r.checks],
        warnings=r.warnings, missing_docs=r.missing_docs, sharoshi_merit=r.sharoshi_merit,
    )

@app.post("/api/diagnose/flexible", response_model=RyoritsuResponse)
def diagnose_flexible(req: FlexibleRequest):
    from .ryoritsu import evaluate_flexible
    r = evaluate_flexible(
        is_small_company=req.is_small_company, seido_count=req.seido_count,
        has_plan=req.has_plan, has_shuugyou_kisoku=req.has_shuugyou_kisoku,
        riyo_months=req.riyo_months, info_published=req.info_published,
        shogaiji_kakucho=req.shogaiji_kakucho,
    )
    return RyoritsuResponse(
        course_name=r.course_name, eligible=r.eligible, rating=r.rating,
        max_amount=r.max_amount, amount_detail=r.amount_detail,
        checks=[{"id":c.id,"title":c.title,"level":c.level,"detail":c.detail} for c in r.checks],
        warnings=r.warnings, missing_docs=r.missing_docs, sharoshi_merit=r.sharoshi_merit,
    )

@app.post("/api/diagnose/funin", response_model=RyoritsuResponse)
def diagnose_funin(req: FuninRequest):
    from .ryoritsu import evaluate_funin
    r = evaluate_funin(
        is_small_company=req.is_small_company,
        support_type=req.support_type,
        has_kyuka_seido=req.has_kyuka_seido,
        has_shuuchi=req.has_shuuchi,
        has_plan=req.has_plan,
        has_tanto=req.has_tanto,
        riyo_count=req.riyo_count,
        chouki_kyuka_days=req.chouki_kyuka_days,
    )
    return RyoritsuResponse(
        course_name=r.course_name, eligible=r.eligible, rating=r.rating,
        max_amount=r.max_amount, amount_detail=r.amount_detail,
        checks=[{"id":c.id,"title":c.title,"level":c.level,"detail":c.detail} for c in r.checks],
        warnings=r.warnings, missing_docs=r.missing_docs, sharoshi_merit=r.sharoshi_merit,
    )
