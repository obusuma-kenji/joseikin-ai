"""
両立支援等助成金 判定エンジン（令和8年度版）
参照：両立支援等助成金支給申請の手引き(2026(令和8)年度版)
     令和8年4月8日時点支給要領・リーフレット
"""
from __future__ import annotations
from dataclasses import dataclass
from typing import List, Literal, Optional

ResultLevel = Literal["OK", "WARN", "NG"]


@dataclass
class CheckItem:
    id: str
    title: str
    level: ResultLevel
    detail: str


@dataclass
class CourseResult:
    course_name: str
    eligible: bool
    rating: str
    max_amount: int
    amount_detail: str
    checks: List[CheckItem]
    warnings: List[str]
    missing_docs: List[str]
    sharoshi_merit: str


# ─────────────────────────────────────────
# 1. 出生時両立支援コース（子育てパパ支援助成金）
# 令和8年度：対象を300人以下に拡大、支給額変更なし
# ─────────────────────────────────────────
def evaluate_paternity_leave(
    is_small_company: bool,
    employee_count: int,
    male_육휴_days: int,
    birth_within_8weeks: bool,
    env_measures_count: int,
    has_business_plan: bool,
    action_plan_filed: bool,
    target_person_num: int,
    申出期限_超2週間: bool,
    is_platinum_kurumin: bool,
    info_published: bool,
) -> CourseResult:
    checks = []
    warnings = []
    missing = []

    # 令和8年度：300人以下に拡大
    size_ok = employee_count <= 300
    checks.append(CheckItem("size", "対象企業規模（300人以下・令和8年度拡大）",
        "OK" if size_ok else "NG",
        f"従業員{employee_count}人（令和8年度から中小企業に限らず300人以下が対象）"))
    if not size_ok:
        warnings.append("従業員300人超のため対象外です。")

    # 出生後8週間以内
    checks.append(CheckItem("birth8w", "出生後8週間以内（57日以内）に育休開始",
        "OK" if birth_within_8weeks else "NG",
        "子の出生後57日以内（出生日当日含む）に育休を開始する必要があります。"))
    if not birth_within_8weeks:
        warnings.append("出生後8週間（57日）以内に育休を開始していない場合は対象外です。")

    # 育休日数（連続日数・所定労働日数の両要件）
    required = {1: (5, 4), 2: (10, 8), 3: (14, 11)}
    req_days, req_workdays = required.get(target_person_num, (5, 4))
    days_ok = male_육휴_days >= req_days
    checks.append(CheckItem("days", f"育休日数（{target_person_num}人目：連続{req_days}日以上・所定労働日{req_workdays}日以上含む）",
        "OK" if days_ok else "NG",
        f"入力：連続{male_육휴_days}日（必要：連続{req_days}日以上かつ所定労働日{req_workdays}日以上）"))
    if not days_ok:
        warnings.append(f"{target_person_num}人目は連続{req_days}日以上（所定労働日{req_workdays}日以上含む）の育休が必要です。")

    # 雇用環境整備措置数
    # 申出期限2週間超の場合は必要数が1つ多くなる
    required_measures = {1: 2, 2: 3, 3: 4}
    req_m = required_measures.get(target_person_num, 2)
    if 申出期限_超2週間:
        req_m += 1
    measures_ok = env_measures_count >= req_m
    checks.append(CheckItem("measures",
        f"雇用環境整備措置（{target_person_num}人目・申出期限{'2週間超' if 申出期限_超2週間 else '2週間前まで'}：{req_m}つ以上）",
        "OK" if measures_ok else "NG",
        f"実施数：{env_measures_count}つ（必要：{req_m}つ以上）\n"
        "①研修実施 ②相談体制整備 ③取得事例収集・提供 ④制度・方針周知 ⑤業務配分・人員配置"))
    if not measures_ok:
        warnings.append(f"雇用環境整備措置が不足（{env_measures_count}つ→{req_m}つ以上必要）。")

    # 業務代替規定・体制整備
    checks.append(CheckItem("business", "業務代替規定・体制整備",
        "OK" if has_business_plan else "NG",
        "育休取得者の業務見直しに係る規定等（就業規則等または育休復帰支援プラン）を策定し、業務体制整備が必要です。"))
    if not has_business_plan:
        warnings.append("業務代替に係る規定の策定（業務整理・引継ぎ・見直し）と体制整備が必要です。")
        missing.append("業務見直しに係る規定（就業規則、内規、育休復帰支援プラン等）")

    # 一般事業主行動計画
    checks.append(CheckItem("action", "一般事業主行動計画の届出・有効",
        "OK" if (action_plan_filed or is_platinum_kurumin) else "WARN",
        "次世代育成支援対策推進法に基づく行動計画を策定・届出・公表・周知している必要があります（プラチナくるみん認定事業主は不要）。"))
    if not action_plan_filed and not is_platinum_kurumin:
        warnings.append("一般事業主行動計画の届出が必要です（申請日時点で有効期間内）。")
        missing.append("一般事業主行動計画（労働局届出済・申請日時点で有効期間内のもの）")

    # 支給額計算（令和8年度：支給額変更なし）
    base = {1: 200_000, 2: 100_000, 3: 100_000}.get(target_person_num, 200_000)
    notes = []

    # 1人目で4つ以上措置→30万円
    if target_person_num == 1 and env_measures_count >= 4:
        base = 300_000
        notes.append("1人目・雇用環境整備措置4つ以上実施：30万円")
    else:
        notes.append(f"{target_person_num}人目基本額：{base:,}円")

    addition = 0
    if is_platinum_kurumin:
        addition += 150_000
        notes.append("プラチナくるみん加算：+15万円")
    if info_published:
        addition += 20_000
        notes.append("育児休業等情報公表加算：+2万円（1回限り）")

    total = base + addition
    notes.append(f"合計：{total:,}円")
    notes.append("※第2種（男性育休取得率30ポイント上昇＆50%以上達成）：最大60万円（別途申請）")

    eligible = all(c.level != "NG" for c in checks)

    missing += [
        "育児休業申出書・育児休業期間変更申出書",
        "就業規則等（育児休業制度・短時間勤務制度の規定）",
        "雇用環境整備措置の実施証明書類（研修記録、相談窓口周知文書等）",
        "業務代替に係る規定等（就業規則、内規または育休復帰支援プラン）",
        "出勤簿・タイムカードおよび賃金台帳（育休前後）",
        "母子健康手帳（出生証明部分）または健康保険証（被扶養者）",
        "一般事業主行動計画（届出済・有効期間内のもの）",
    ]

    return CourseResult(
        course_name="出生時両立支援コース（子育てパパ支援助成金）",
        eligible=eligible,
        rating="A：申請可" if eligible else "C：要件未達",
        max_amount=total,
        amount_detail="\n".join(notes),
        checks=checks,
        warnings=list(dict.fromkeys(warnings)),
        missing_docs=list(dict.fromkeys(missing)),
        sharoshi_merit="業務代替規定の整備・一般事業主行動計画の策定・就業規則改定を社労士がサポートします。雇用環境整備措置4つ以上で1人目が30万円に増額されるため、事前準備が重要です。",
    )


# ─────────────────────────────────────────
# 2. 育休中等業務代替支援コース
# 令和8年度：新規雇用の最長区分を「1年以上→最大81万円」に改定
#            （令和7年度：6か月以上→67.5万円）
#            プラチナくるみん：1年以上→99万円
#            手当支給（育休）：最大140万円、手当支給（短時間）：最大128万円
# ─────────────────────────────────────────
def evaluate_gyomu_daitai(
    employee_count: int,
    support_type: str,
    ikukyu_days: int,
    tanki_months: int,
    daitai_months: float,
    teate_total: int,
    has_rule: bool,
    has_kaizen: bool,
    sharoshi_委託: bool,
    is_yukikoyou: bool,
    info_published: bool,
    is_platinum: bool,
) -> CourseResult:
    checks = []
    warnings = []
    missing = []

    # 対象規模（手当支給等は300人以下、新規雇用は中小企業）
    size_ok = employee_count <= 300
    checks.append(CheckItem("size", "対象企業規模",
        "OK" if size_ok else "NG",
        f"従業員{employee_count}人（手当支給等：300人以下、新規雇用：中小企業のみ）"))
    if not size_ok:
        warnings.append("従業員300人超は対象外です。")

    # 就業規則規定
    checks.append(CheckItem("rule", "手当制度等の就業規則等への規定",
        "OK" if has_rule else "NG",
        "業務代替者への手当支給制度を就業規則または労働協約に規定している必要があります。"))
    if not has_rule:
        warnings.append("手当支給制度の就業規則等への規定が必要です。")
        missing.append("就業規則等（業務代替手当の規定箇所）")

    # 業務見直し・効率化
    checks.append(CheckItem("kaizen", "業務代替の見直し・効率化実施",
        "OK" if has_kaizen else "NG",
        "育休取得者の業務の整理・引継ぎ・見直し（休廃止・効率化・外注等）に係る規定の策定と実施が必要です。"))
    if not has_kaizen:
        warnings.append("業務見直しに係る規定の策定と実施が必要です。")
        missing.append("業務見直しに係る規定等（就業規則、内規、育休復帰支援プラン）")

    # 育休日数チェック
    if support_type in ("手当支給_育休", "新規雇用"):
        days_ok = ikukyu_days >= 7
        checks.append(CheckItem("days", "育休7日以上取得",
            "OK" if days_ok else "NG",
            f"育休日数：{ikukyu_days}日（7日以上必要）"))
        if not days_ok:
            warnings.append("育休7日以上の取得が必要です。")

    # 短時間勤務期間
    if support_type == "手当支給_短時間":
        months_ok = tanki_months >= 1
        checks.append(CheckItem("tanki", "短時間勤務1か月以上利用",
            "OK" if months_ok else "NG",
            f"短時間勤務期間：{tanki_months}か月（1か月以上必要）"))
        if not months_ok:
            warnings.append("短時間勤務1か月以上の利用が必要です。")

    # 支給額計算
    total = 0
    notes = []

    if support_type == "手当支給_育休":
        # 業務体制整備経費（令和8年度：社労士委託で最大20万円）
        seiri_cost = 200_000 if sharoshi_委託 else 50_000
        notes.append(f"業務体制整備経費：{seiri_cost:,}円（{'社労士委託：最大20万円' if sharoshi_委託 else '自社実施：最大5万円'}）")
        # 手当助成：支給総額の3/4（上限3万円/月）
        months_est = max(ikukyu_days // 30, 1)
        teate_josho = min(int(teate_total * 0.75), 30_000 * months_est)
        # プラチナくるみんは4/5に割増
        if is_platinum:
            teate_josho = min(int(teate_total * 0.8), 30_000 * months_est)
            notes.append(f"業務代替手当助成（プラチナくるみん割増：支給総額×4/5）：{teate_josho:,}円")
        else:
            notes.append(f"業務代替手当助成（支給総額{teate_total:,}円×3/4、上限3万円/月）：{teate_josho:,}円")
        total = seiri_cost + teate_josho
        # 有期雇用労働者加算（代替期間1か月以上の場合）
        if is_yukikoyou and ikukyu_days >= 30:
            total += 100_000
            notes.append("有期雇用労働者加算：+10万円（代替期間1か月以上）")
        notes.append("※最大140万円（業務体制整備費20万円＋業務代替手当120万円）")

    elif support_type == "手当支給_短時間":
        seiri_cost = 200_000 if sharoshi_委託 else 50_000
        notes.append(f"業務体制整備経費：{seiri_cost:,}円")
        teate_josho = min(int(teate_total * 0.75), 30_000 * max(tanki_months, 1))
        notes.append(f"業務代替手当助成（支給総額×3/4、上限3万円/月）：{teate_josho:,}円")
        total = seiri_cost + teate_josho
        if is_yukikoyou and tanki_months >= 1:
            total += 100_000
            notes.append("有期雇用労働者加算：+10万円")
        notes.append("※最大128万円（業務体制整備費20万円＋業務代替手当108万円）")

    elif support_type == "新規雇用":
        # 令和8年度改定：1年以上→最大81万円（令和7年度：6か月以上→67.5万円）
        if daitai_months >= 12:
            if is_platinum:
                base_amount = 990_000
                notes.append(f"新規雇用（1年以上・プラチナくるみん）：{base_amount:,}円")
            else:
                base_amount = 810_000
                notes.append(f"新規雇用（1年以上）：{base_amount:,}円【令和8年度改定：67.5万→81万円】")
        elif daitai_months >= 0.5:  # 7日以上
            base_amount = 90_000
            notes.append(f"新規雇用（7日以上）：{base_amount:,}円")
            if daitai_months < 12:
                warnings.append(
                    f"代替期間が{daitai_months}か月です。令和8年度から最長区分は「1年以上：81万円」に変更されました。"
                    "（令和7年度の「6か月以上：67.5万円」区分は令和8年度から廃止）代替期間を1年以上確保できると助成額が大幅に上がります。"
                )
        else:
            base_amount = 0
            warnings.append("代替期間が7日未満のため助成対象外です。")
        total = base_amount
        if is_yukikoyou and daitai_months >= 1:
            total += 100_000
            notes.append("有期雇用労働者加算：+10万円（代替期間1か月以上）")

    # 情報公表加算（1回限り）
    if info_published:
        total += 20_000
        notes.append("育児休業等情報公表加算：+2万円（1回限り）")

    notes.append(f"\n合計試算額：{total:,}円")

    eligible = all(c.level != "NG" for c in checks)

    missing += [
        "就業規則等（業務代替手当・業務見直し規定）",
        "業務体制整備を実施したことを確認できる書類（業務整理・引継ぎの記録等）",
        "業務代替者の氏名・手当支給額・支給期間が分かる書類",
        "育児休業申出書・育休期間が確認できる書類",
        "出勤簿・賃金台帳（育休取得者・代替者）",
    ]
    if sharoshi_委託:
        missing.append("社労士との業務体制整備委託契約書および委託費用の領収書・支払証明")

    return CourseResult(
        course_name="育休中等業務代替支援コース",
        eligible=eligible,
        rating="A：申請可" if eligible else "C：要件未達",
        max_amount=total,
        amount_detail="\n".join(notes),
        checks=checks,
        warnings=list(dict.fromkeys(warnings)),
        missing_docs=list(dict.fromkeys(missing)),
        sharoshi_merit="【重要】社労士に業務体制整備を委託した場合、業務体制整備経費が最大20万円に増額（自社実施は最大5万円）。社労士関与が直接助成額アップにつながる唯一のコースです。令和8年度から新規雇用の最長区分が「1年以上→81万円」に改定。",
    )


# ─────────────────────────────────────────
# 3. 育児休業等支援コース
# 令和8年度：支給額変更なし（育休取得時30万円・職場復帰時30万円）
# ─────────────────────────────────────────
def evaluate_ikukyu_shien(
    is_small_company: bool,
    stage: str,
    has_mensdan: bool,
    has_hikitsuki: bool,
    ikukyu_months: float,
    fukki_shuro: bool,
    info_published: bool,
) -> CourseResult:
    checks = []
    warnings = []
    missing = []

    if not is_small_company:
        checks.append(CheckItem("size", "中小企業要件", "NG",
            "育児休業等支援コースは中小企業のみ対象です。"))
        warnings.append("育児休業等支援コースは中小企業のみ対象です。")

    checks.append(CheckItem("mensdan", "面談・育休復帰支援プラン作成",
        "OK" if has_mensdan else "NG",
        "育休開始前に上司または人事担当者が面談を実施し、面談シートと育休復帰支援プランを作成する必要があります。"))
    if not has_mensdan:
        warnings.append("育休開始前の面談・育休復帰支援プランの作成が必要です。")
        missing.append("面談シート（厚生労働省所定様式）")
        missing.append("育休復帰支援プラン（業務引継ぎ・復帰後支援の内容含む）")

    checks.append(CheckItem("hikitsuki", "業務引継ぎの実施",
        "OK" if has_hikitsuki else "NG",
        "プランに基づき育休開始前日までに業務引継ぎを実施する必要があります。"))
    if not has_hikitsuki:
        warnings.append("業務引継ぎの実施と記録が必要です。")

    months_ok = ikukyu_months >= 3
    checks.append(CheckItem("months", "育休3か月以上取得",
        "OK" if months_ok else "NG",
        f"育休期間：{ikukyu_months}か月（連続3か月以上必要・産後休業から継続の場合を含む）"))
    if not months_ok:
        warnings.append("連続3か月以上の育休取得が必要です（産後休業から継続の場合を含む）。")

    if stage == "職場復帰時":
        checks.append(CheckItem("fukki", "職場復帰後6か月継続就業",
            "OK" if fukki_shuro else "NG",
            "育休後に原職等に復帰し、6か月以上継続就業していることが必要です。"))
        if not fukki_shuro:
            warnings.append("職場復帰後6か月継続就業が必要です。")

    base = 300_000
    addition = 20_000 if info_published else 0
    total = base + addition
    notes = [
        f"{stage}：{base:,}円",
        "情報公表加算：+2万円" if info_published else "",
        f"合計：{total:,}円",
        "※育休取得時・職場復帰時を合わせると最大60万円＋加算（各1事業主2名まで：無期・有期各1名）",
    ]

    eligible = all(c.level != "NG" for c in checks)

    missing += [
        "育休復帰支援プラン・面談シート（厚生労働省所定様式）",
        "育児休業申出書",
        "出勤簿・賃金台帳（育休前後）",
        "母子健康手帳（出生証明部分）",
        "一般事業主行動計画（届出済・有効期間内のもの）",
    ]

    return CourseResult(
        course_name=f"育児休業等支援コース（{stage}）",
        eligible=eligible,
        rating="A：申請可" if eligible else "C：要件未達",
        max_amount=total,
        amount_detail="\n".join(filter(None, notes)),
        checks=checks,
        warnings=list(dict.fromkeys(warnings)),
        missing_docs=list(dict.fromkeys(missing)),
        sharoshi_merit="社労士が面談シート・育休復帰支援プランの作成・就業規則整備をサポートします。育休取得時と職場復帰時の2段階申請で合計60万円を確実に取りに行けます。",
    )


# ─────────────────────────────────────────
# 4. 介護離職防止支援コース
# 令和8年度改定：
#   介護休業：取得時＋職場復帰時合計40万円（令和8年度版リーフレット）
#   介護両立支援制度：1制度20万円・2つ以上25万円
#   業務代替支援（新規雇用）：20万円
#   業務代替支援（手当支給）：介護休業5万円・短時間勤務3万円
#   介護休暇有給化：新設（令和8年度）
# ─────────────────────────────────────────
def evaluate_kaigo(
    is_small_company: bool,
    support_type: str,
    has_plan: bool,
    kaigo_kyugo_days: int,
    seido_count: int,
    seido_days: int,
    yuko_kazan: bool,
    info_published: bool,
) -> CourseResult:
    checks = []
    warnings = []
    missing = []

    if not is_small_company:
        checks.append(CheckItem("size", "中小企業要件", "NG",
            "介護離職防止支援コースは中小企業のみ対象です。"))
        warnings.append("介護離職防止支援コースは中小企業のみ対象です。")

    checks.append(CheckItem("plan", "介護支援プランの作成・面談実施",
        "OK" if has_plan else "NG",
        "対象労働者との面談実施（面談シート記録）・介護支援プランの作成が必要です。"))
    if not has_plan:
        warnings.append("介護支援プランの面談・作成が必要です。")
        missing.append("介護支援プラン・面談シート（厚生労働省所定様式）")

    # 介護休業日数チェック（連続5日以上の所定労働日）
    if support_type in ("介護休業", "業務代替支援_新規雇用", "業務代替支援_手当"):
        days_ok = kaigo_kyugo_days >= 5
        checks.append(CheckItem("days", "介護休業5日以上取得（所定労働日）",
            "OK" if days_ok else "NG",
            f"介護休業日数：{kaigo_kyugo_days}日（連続5日・所定労働日以上必要）"))
        if not days_ok:
            warnings.append("介護休業の取得は所定労働日で連続5日以上必要です。")

    # 支給額計算（令和8年度版）
    total = 0
    notes = []

    if support_type == "介護休業":
        # 令和8年度：取得時40万円（取得時と復帰時の合計）
        total = 400_000
        notes.append("介護休業：取得時＋職場復帰時合計：40万円（1人あたり・1事業主5人まで）")
        notes.append("※休業取得時に申請→職場復帰後に追加申請の2段階")

    elif support_type == "介護両立支援制度":
        if seido_count >= 2:
            base = 250_000
            notes.append(f"介護両立支援制度（2つ以上導入・利用）：{base:,}円")
        else:
            base = 200_000
            notes.append(f"介護両立支援制度（1制度導入・利用）：{base:,}円")
        total = base
        notes.append("※1事業主5人まで。制度利用期間に応じて増額あり")

    elif support_type == "業務代替支援_新規雇用":
        total = 200_000
        notes.append("業務代替支援（新規雇用）：20万円")
        notes.append("※介護休業取得者の業務代替要員を新規雇用または派遣受入で確保")

    elif support_type == "業務代替支援_手当":
        # 介護休業取得者5万円＋短時間勤務者3万円（組み合わせ可）
        total = 50_000
        notes.append("業務代替支援（手当支給等：介護休業取得者）：5万円")
        notes.append("※短時間勤務者の業務代替手当を支給した場合は別途3万円")

    elif support_type == "有給化":
        # 令和8年度新設
        total = 200_000
        notes.append("介護休暇有給化（令和8年度新設）：20万円（1事業主1回限り）")

    if info_published:
        total += 20_000
        notes.append("情報公表加算：+2万円（1回限り）")

    notes.append(f"\n合計試算額：{total:,}円")
    notes.append("※複数取組の組み合わせで最大143万円も可能")
    notes.append("※令和8年度から介護休暇有給化への助成が新設されました")

    eligible = all(c.level != "NG" for c in checks)

    missing += [
        "介護支援プラン・面談シート（厚生労働省所定様式）",
        "介護休業申出書（介護休業の場合）",
        "就業規則等（介護両立支援制度の規定箇所）",
        "出勤簿・賃金台帳",
        "介護が必要な家族の状態を確認できる書類（診断書等）",
    ]

    return CourseResult(
        course_name="介護離職防止支援コース",
        eligible=eligible,
        rating="A：申請可" if eligible else "C：要件未達",
        max_amount=total,
        amount_detail="\n".join(notes),
        checks=checks,
        warnings=list(dict.fromkeys(warnings)),
        missing_docs=list(dict.fromkeys(missing)),
        sharoshi_merit="介護支援プランの作成・就業規則への介護両立制度の規定整備を社労士がサポートします。令和8年度から介護休暇有給化への助成が新設され、就業規則改定のニーズが高まっています。",
    )


# ─────────────────────────────────────────
# 5. 柔軟な働き方選択制度等支援コース
# 令和8年度：3つ以上導入で25万円（変更なし）
#           障害のある子等・18歳年度末まで延長加算20万円（継続）
#           子の看護等休暇有給化でも申請可能
# ─────────────────────────────────────────
def evaluate_flexible(
    is_small_company: bool,
    seido_count: int,
    has_plan: bool,
    has_shuugyou_kisoku: bool,
    riyo_months: float,
    info_published: bool,
    shogaiji_kakucho: bool,
) -> CourseResult:
    checks = []
    warnings = []
    missing = []

    if not is_small_company:
        checks.append(CheckItem("size", "中小企業要件", "NG",
            "柔軟な働き方選択制度等支援コースは中小企業のみ対象です。"))
        warnings.append("本コースは中小企業のみ対象です。")

    seido_ok = seido_count >= 2
    checks.append(CheckItem("seido", f"柔軟な働き方制度の導入数（{seido_count}つ）",
        "OK" if seido_ok else "NG",
        "①フレックスタイム/時差出勤 ②育児テレワーク ③短時間勤務 ④保育サービス費用補助 "
        "⑤子の養育を容易にする休暇/法を上回る看護等休暇のうち2つ以上導入・就業規則等に規定が必要（3つ以上で25万円）"))
    if not seido_ok:
        warnings.append("柔軟な働き方制度を少なくとも2つ導入・就業規則等に規定する必要があります。")
        missing.append("就業規則等（柔軟な働き方制度の規定箇所）")

    checks.append(CheckItem("plan", "柔軟な働き方支援プラン・面談実施",
        "OK" if has_plan else "NG",
        "対象労働者との面談実施（面談シート記録）・柔軟な働き方支援プランの作成が必要です。"))
    if not has_plan:
        warnings.append("面談シートと柔軟な働き方支援プランの作成が必要です。")
        missing.append("面談シート・柔軟な働き方支援プラン")

    checks.append(CheckItem("kisoku", "制度の就業規則等への規定",
        "OK" if has_shuugyou_kisoku else "NG",
        "柔軟な働き方制度を就業規則または労働協約に規定している必要があります。"))
    if not has_shuugyou_kisoku:
        warnings.append("就業規則等への規定が必要です。")

    # 支給額
    base = 250_000 if seido_count >= 3 else 200_000
    notes = [f"{'3つ以上' if seido_count >= 3 else '2つ'}の制度導入・利用：{base:,}円/人（1年度5人まで）"]

    addition = 0
    if info_published:
        addition += 20_000
        notes.append("情報公表加算：+2万円（1回限り）")
    if shogaiji_kakucho:
        addition += 200_000
        notes.append("障害のある子等・18歳年度末まで利用期間延長加算：+20万円（1事業主1回限り）")

    total = base + addition
    notes.append(f"合計（1人分）：{total:,}円")
    notes.append("※年度5人×25万円=最大125万円（加算除く）")
    notes.append("※3歳〜小学校就学前の子を育てる労働者が対象。制度利用開始から6か月間で一定基準以上利用が必要")

    eligible = all(c.level != "NG" for c in checks)

    missing += [
        "就業規則等（柔軟な働き方制度の規定箇所）",
        "面談シート・柔軟な働き方支援プラン",
        "対象労働者の制度利用実績確認書類（勤務記録・利用申出書等）",
        "育児をしていることを確認できる書類（母子健康手帳等）",
    ]

    return CourseResult(
        course_name="柔軟な働き方選択制度等支援コース",
        eligible=eligible,
        rating="A：申請可" if eligible else "C：要件未達",
        max_amount=total,
        amount_detail="\n".join(notes),
        checks=checks,
        warnings=list(dict.fromkeys(warnings)),
        missing_docs=list(dict.fromkeys(missing)),
        sharoshi_merit="社労士が就業規則への制度規定・柔軟な働き方支援プランの作成をサポートします。制度3つ以上の整備で25万円/人。障害のある子等への延長加算（+20万円）は就業規則改定が必要です。",
    )


# ─────────────────────────────────────────
# 6. 不妊治療及び女性の健康課題対応両立支援コース
# 令和8年度改定：
#   A：不妊治療のための両立支援制度利用 → 30万円
#   B：月経に起因する症状への対応支援制度利用 → 30万円（令和8年度改定）
#   C：更年期に起因する症状への対応支援制度利用 → 30万円（令和8年度改定）
#   長期休暇加算：連続20日以上 → +20万円
#   ※令和7年度までは「環境整備・休暇取得等28万円」のみ
# ─────────────────────────────────────────
def evaluate_funin(
    is_small_company: bool,
    support_type: str,          # "A_funin" / "B_gekkei" / "C_konenki"
    has_kyuka_seido: bool,
    has_shuuchi: bool,
    has_plan: bool,
    has_tanto: bool,            # 両立支援担当者の選任
    riyo_count: int,
    chouki_kyuka_days: int,
) -> CourseResult:
    checks = []
    warnings = []
    missing = []

    if not is_small_company:
        checks.append(CheckItem("size", "中小企業要件", "NG",
            "本コースは中小企業のみ対象です。"))
        warnings.append("本コースは中小企業のみ対象です。")

    checks.append(CheckItem("seido", "両立支援制度の就業規則等への規定",
        "OK" if has_kyuka_seido else "NG",
        "対応する両立支援制度（休暇制度・所定外労働制限・時差出勤・短時間勤務・フレックス・在宅勤務等）を就業規則等に規定し、制度利用手続きや賃金の取扱いも規定している必要があります。"))
    if not has_kyuka_seido:
        warnings.append("両立支援制度の就業規則等への規定が必要です。")
        missing.append("就業規則等（不妊治療・月経・更年期対応の両立支援制度の規定箇所）")

    checks.append(CheckItem("shuuchi", "支援する旨の社内周知",
        "OK" if has_shuuchi else "NG",
        "会社が不妊治療等を支援する旨を社内周知している必要があります（通達・社内報・イントラネット等）。"))
    if not has_shuuchi:
        warnings.append("不妊治療等支援の社内周知が必要です。")

    checks.append(CheckItem("tanto", "両立支援担当者の選任",
        "OK" if has_tanto else "NG",
        "労働者の相談に対応する両立支援担当者を選任している必要があります（令和8年度から必須要件）。"))
    if not has_tanto:
        warnings.append("両立支援担当者の選任が必要です（管理職・人事・総務等から選任）。")
        missing.append("両立支援担当者の選任を証明する書類（辞令等）")

    riyo_ok = riyo_count >= 5
    checks.append(CheckItem("riyo", "制度利用5日（回）以上（1年度内）",
        "OK" if riyo_ok else "NG",
        f"制度利用回数：{riyo_count}回（1年度内に合計5日/5回以上必要）"))
    if not riyo_ok:
        warnings.append("1年度内に5回（5日）以上の制度利用が必要です。")

    # 支給額（令和8年度：A/B/Cそれぞれ30万円）
    type_labels = {
        "A_funin": "A：不妊治療のための両立支援制度利用",
        "B_gekkei": "B：月経に起因する症状への対応支援制度利用（令和8年度）",
        "C_konenki": "C：更年期に起因する症状への対応支援制度利用（令和8年度）",
    }
    label = type_labels.get(support_type, "A：不妊治療のための両立支援制度利用")
    base = 300_000
    notes = [f"{label}：{base:,}円（1事業主1回限り）"]

    addition = 0
    if support_type == "A_funin" and chouki_kyuka_days >= 20:
        addition = 200_000
        notes.append(f"長期休暇加算（連続{chouki_kyuka_days}日≥20日）：+20万円")

    total = base + addition
    notes.append(f"合計：{total:,}円")
    notes.append("※A・B・Cは各1事業主1回限りの支給（合計最大3回申請可能）")
    notes.append("※令和8年度からB（月経）・C（更年期）が追加され、各30万円に改定")

    eligible = all(c.level != "NG" for c in checks)

    missing += [
        "就業規則等（両立支援制度の規定・利用手続き・賃金取扱い規定）",
        "社内周知文書（通達・社内報等）",
        "両立支援担当者の選任書類",
        "制度利用実績確認書類（利用申出書・出勤簿等）",
    ]
    if support_type == "A_funin" and chouki_kyuka_days >= 20:
        missing.append("長期休暇取得・職場復帰を確認できる書類（出勤簿等）")

    return CourseResult(
        course_name=f"不妊治療及び女性の健康課題対応両立支援コース（{label[:10]}…）",
        eligible=eligible,
        rating="A：申請可" if eligible else "C：要件未達",
        max_amount=total,
        amount_detail="\n".join(notes),
        checks=checks,
        warnings=list(dict.fromkeys(warnings)),
        missing_docs=list(dict.fromkeys(missing)),
        sharoshi_merit="令和8年度から月経・更年期対応も助成対象に追加（各30万円）。社労士が就業規則への両立支援制度規定・両立支援担当者の体制整備・プラン作成をサポートします。女性活躍推進との相乗効果も期待できます。",
    )
