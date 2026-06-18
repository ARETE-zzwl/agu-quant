"""Commercial support plan definitions and access checks."""

SUPPORTER_PLAN = "supporter"
PRO_PLAN = "pro"
PLAN_LEVELS = {SUPPORTER_PLAN: 1, PRO_PLAN: 2}
PLAN_LABELS = {SUPPORTER_PLAN: "支持者版", PRO_PLAN: "Pro 版"}


def normalize_plan(plan: object, default: str = PRO_PLAN) -> str:
    value = str(plan or default).strip().lower()
    if value not in PLAN_LEVELS:
        raise ValueError("套餐必须是 supporter 或 pro")
    return value


def plan_allows(current_plan: object, required_plan: object) -> bool:
    current = normalize_plan(current_plan)
    required = normalize_plan(required_plan)
    return PLAN_LEVELS[current] >= PLAN_LEVELS[required]


def plan_label(plan: object) -> str:
    return PLAN_LABELS[normalize_plan(plan)]
