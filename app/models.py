from __future__ import annotations
from dataclasses import dataclass, field
from datetime import date
from typing import Literal, Optional
import math

EmploymentType = Literal["有期", "無期", "派遣"]
EmploymentAfter = Literal["正社員", "勤務地限定正社員", "職務限定正社員", "短時間正社員"]
PriorityType = Literal["a", "b", "c", "none"]


@dataclass(frozen=True)
class CompanyInput:
    company_name: str
    employee_count: int
    is_large_company: bool
    career_up_plan_start: date
    career_up_plan_end: date
    conversion_rule_exists: bool
    conversion_rule_has_objective_procedure: bool
    regular_rule_has_bonus_or_retirement: bool
    regular_rule_has_raise: bool
    nonregular_rule_has_wage_diff: bool
    work_rules_not_edited: bool
    new_conversion_rule: bool = False
    new_diverse_regular_rule: bool = False
    info_published: bool = False


@dataclass(frozen=True)
class WorkerInput:
    worker_name: str
    hire_date: date
    conversion_date: date
    employment_before: EmploymentType
    employment_after: EmploymentAfter
    tenure_months_before_conversion: int
    is_new_graduate: bool
    months_since_graduation_at_hire: Optional[int]
    is_foreign_trainee_or_specified_skill1: bool
    has_probation_after_conversion: bool
    is_over_retirement_age_at_conversion: bool
    social_insurance_applied_after_conversion: bool
    priority_type: PriorityType = "none"
    past5y_regular_months: Optional[int] = None
    past1y_regular: bool = False
    is_single_parent: bool = False


@dataclass(frozen=True)
class WageInput:
    before_total_yen_6m: int
    after_total_yen_6m: int
    before_hours_6m: Optional[float] = None
    after_hours_6m: Optional[float] = None
    use_hourly_compare: bool = False

    @property
    def increase_percent(self) -> float:
        if self.use_hourly_compare:
            if not self.before_hours_6m or not self.after_hours_6m:
                return 0.0
            rate_before = self.before_total_yen_6m / self.before_hours_6m
            rate_after = self.after_total_yen_6m / self.after_hours_6m
            if rate_before == 0:
                return 0.0
            return math.floor((rate_after - rate_before) / rate_before * 1000) / 10
        else:
            if self.before_total_yen_6m == 0:
                return 0.0
            return math.floor(
                (self.after_total_yen_6m - self.before_total_yen_6m)
                / self.before_total_yen_6m * 1000
            ) / 10

    @property
    def before_hourly(self) -> Optional[float]:
        if self.before_hours_6m:
            return self.before_total_yen_6m / self.before_hours_6m
        return None

    @property
    def after_hourly(self) -> Optional[float]:
        if self.after_hours_6m:
            return self.after_total_yen_6m / self.after_hours_6m
        return None


@dataclass(frozen=True)
class DeadlineInput:
    six_month_wage_payment_date: date
    application_submit_date: date
    payroll_closing_day: Optional[int] = None


@dataclass(frozen=True)
class CaseInput:
    company: CompanyInput
    worker: WorkerInput
    wage: WageInput
    deadline: DeadlineInput
