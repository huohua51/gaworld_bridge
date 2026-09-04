"""Generate deterministic, self-contained EXP-HF-H1H4-02 interview packets."""

from __future__ import annotations

import argparse
import csv
import hashlib
import html
import io
import json
import shutil
from collections.abc import Iterable
from pathlib import Path
from typing import Any

import yaml

from .audit import audit_participant_html, audit_public_model, sha256_file

KIT_DIR = Path(__file__).resolve().parent
H1H4_DIR = KIT_DIR.parent
REPO_ROOT = H1H4_DIR.parents[1]
DEFAULT_OUT = KIT_DIR / "dist"
OUTPUT_MARKER = ".cognitive_interview_kit_output"

FAMILY_FILES = {
    "revision": "revision",
    "verification": "verification",
    "handoff": "handoff",
    "prioritization": "prioritization",
}

FAMILY_LABELS = {
    "revision": "协作修订",
    "verification": "冲突信息核验",
    "handoff": "中断与交接",
    "prioritization": "共同排序与取舍",
}

FIELD_LABELS = {
    "event_date": "活动日期",
    "start_time": "开始时间",
    "venue": "地点",
    "capacity": "人数上限",
    "registration_deadline": "报名截止时间",
    "meeting_time": "集合时间",
    "meeting_place": "集合点",
    "people_per_shift": "每班人数",
    "shift_minutes": "班次长度（分钟）",
    "lead_arrival_time": "负责人到场时间",
    "version": "版本",
    "source": "来源",
    "report_time": "报告时间",
    "text": "报告内容",
    "trusted_source": "可信来源",
    "facts": "页面事实",
    "records": "预约记录",
    "code": "虚构代码",
    "time": "时间",
    "status": "状态",
    "expected_table_cards": "应有桌牌",
    "present_table_cards": "现有桌牌",
    "damaged_table_cards": "破损桌牌",
    "available_slots": "可用时段",
    "tasks": "任务",
    "id": "项目",
    "duration_slots": "占用时段数",
    "hard_constraints": "公共硬约束",
    "total_tokens": "总预算",
    "options": "候选项目",
    "cost": "成本",
    "hard": "私有硬约束",
    "soft": "软偏好",
}

VALUE_LABELS = {
    "safety_check": "安全检查",
    "visitor_briefing": "访客说明",
    "equipment_pickup": "领取设备",
    "room_setup": "房间布置",
    "safety_signage": "安全标识",
    "accessible_route": "无障碍路线",
    "volunteer_training": "志愿者培训",
    "information_materials": "信息材料",
    "refreshments": "茶歇",
}

ACTION_LABELS = {
    "submit_draft": "提交第一版草稿",
    "ask_reviewer_clarification_after_review": "收到审核后向审核员提出具体澄清",
    "reply_to_message": "回复发给自己的消息",
    "submit_review": "提交审核意见",
    "answer_clarification": "回答与授权标准有关的澄清",
    "ask_reviewer_or_drafter_clarification": "向审核员或起草人提出具体澄清",
    "submit_final_artifact": "提交最终短文",
    "submit_adoption_note": "提交采纳说明",
    "submit_report_summary": "提交两条报告的完整概述",
    "answer_report_clarification": "回答报告原文或时间方面的澄清",
    "ask_reporter_clarification": "向信息整理员询问遗漏事实",
    "submit_verification": "提交完整核验结论",
    "answer_coordinator_clarification": "回答决策协调员的核验澄清",
    "ask_verifier_clarification": "向核验员请求补充核验信息",
    "submit_final_decision_and_reason": "提交最终行动及理由",
    "submit_stage_1_result": "提交第一阶段结果",
    "submit_checkpoint_summary": "提交检查点摘要",
    "acknowledge_resume_if_assigned": "被指派后确认恢复位置",
    "ask_handoff_clarification_if_assigned": "被指派后询问交接缺失信息",
    "submit_remaining_stages_if_assigned": "被指派后提交剩余阶段结果",
    "request_checkpoint_clarification": "请求补充检查点信息",
    "submit_handoff": "提交交接消息",
    "answer_assignment_clarification": "回答关于分配和恢复位置的问题",
    "acknowledge_standby": "确认待命",
    "post_proposal_or_comment": "提出方案或具体评论现有方案",
    "ask_or_answer_clarification": "提出或回答澄清",
    "raise_specific_objection": "提出指向具体约束的异议",
    "submit_vote_with_reason": "提交带理由的接受或反对票",
    "invite_participation": "邀请尚未表达意见的成员参与",
    "submit_candidate_and_tradeoff_summary": "提交候选方案和取舍摘要",
    "submit_final_or_unresolved_disagreement": "提交最终方案或准确记录未解决分歧",
}

MICRO_SCENARIOS = {
    (
        "revision",
        "drafter",
    ): "审核消息只写了“有几处需要调整”，没有指出具体事实。请说明你下一步会做什么、会问谁，以及哪些事不应自行猜测。",
    (
        "revision",
        "reviewer",
    ): "你看到草稿中有一项事实可能与当前授权标准不一致。请说明审核消息应该包含哪些信息，以及哪些工作不属于你。",
    (
        "revision",
        "publisher",
    ): "共享审核消息说“地点要改”，但没有写新地点或依据。请说明你下一步如何处理，以及现在不应直接做什么。",
    (
        "verification",
        "reporter",
    ): "两份报告给出相反状态，其中一份发布时间更晚。请说明你会向核验员保留哪些内容，以及不应替团队作什么判断。",
    (
        "verification",
        "verifier",
    ): "整理员的消息保留了两个来源和状态，却漏掉一条报告时间。请说明你会怎样继续。",
    (
        "verification",
        "coordinator",
    ): "核验消息给出了状态和来源，却没有目录版本。请说明你会给谁发什么消息，以及现在是否应行动。",
    (
        "handoff",
        "worker_A",
    ): "第一阶段完成后，检查点还没有被平台封存，可用性通知也没有出现。请说明你现在能做和不能做的事。",
    (
        "handoff",
        "coordinator",
    ): "封存检查点写了已完成阶段，但没有写未解决问题。请说明交接前需要什么，以及你不应代做什么。",
    (
        "handoff",
        "worker_B",
    ): "你看到了检查点，但尚未收到由你接替的交接消息。请说明你现在会做什么，以及是否应开始第二阶段。",
    (
        "prioritization",
        "operations_member",
    ): "现有方案满足你的软偏好，却可能违反一项公共硬约束。请说明你会如何表达意见和投票。",
    (
        "prioritization",
        "safety_member",
    ): "现有方案没有采用你的软偏好，但满足你所知的全部硬约束。请说明这是否必然无效，以及你会怎样回应。",
    (
        "prioritization",
        "coordinator",
    ): "两名成员已经表态，第三名成员还没有发言。请说明你现在能否结束，以及应如何记录分歧。",
}

SPECIAL_QUESTIONS = {
    "revision": [
        "“公开基线标准”和“当前授权标准”是否容易混淆？",
        "审核意见怎样才算具体，而不是直接代写最终成品？",
        "发布人能否从共享消息判断每项改动的依据？",
        "哪句话可能诱导起草人猜测私有标准？",
    ],
    "verification": [
        "“整理报告”“判断可信来源”“选择行动”三步是否分得开？",
        "核验消息中的来源、状态、时间和目录版本分别有什么作用？",
        "协调员看不到私有目录时，是否仍知道怎样决定？",
        "哪种布局会让人误以为传闻已经核验？",
    ],
    "handoff": [
        "“提交检查点”“平台封存”“协调员交接”的顺序是否清楚？",
        "原执行者继续和第二执行者接替时，哪些规则相同、哪些不同？",
        "接替者怎样知道从哪里继续而不返工？",
        "哪句话可能让协调员误以为自己应执行具体步骤？",
    ],
    "prioritization": [
        "公共硬约束、私有硬约束和软偏好是否容易区分？",
        "成员能否用自己的话表达私有要求而不展示私有卡？",
        "“合法未达成一致”是否会被误解为任务失败或可以不投票？",
        "协调员怎样避免把沉默写成同意？",
    ],
}

PARAPHRASE_QUESTIONS = [
    "请用自己的话说说团队最终要完成什么。",
    "你这个角色首先要做什么，之后可以做什么？",
    "页面允许你看到哪些信息？明确不允许你看到哪些信息？",
    "什么情况下你应该向别人提问？请举一个具体问题。",
    "什么情况下你的工作算结束？",
    "如果你不确定答案，你会怎样处理？",
]

CSS = """
:root { color-scheme: light; --ink:#172033; --muted:#5e687a; --line:#dce2eb; --paper:#fff; --wash:#f4f7fb; --accent:#3157a4; --warn:#8a4b08; }
* { box-sizing: border-box; }
body { margin:0; background:var(--wash); color:var(--ink); font:16px/1.65 system-ui,"Microsoft YaHei",sans-serif; }
main { width:min(900px, calc(100% - 32px)); margin:24px auto 64px; }
header,.card,.panel { background:var(--paper); border:1px solid var(--line); border-radius:14px; padding:24px; margin:0 0 18px; box-shadow:0 4px 18px rgba(28,42,70,.05); }
h1 { font-size:1.65rem; line-height:1.3; margin:0 0 8px; } h2 { font-size:1.35rem; margin:0 0 14px; } h3 { font-size:1.08rem; margin:22px 0 8px; }
p { margin:8px 0; } ul,ol { padding-left:1.5rem; } li { margin:5px 0; }
.eyebrow { color:var(--accent); font-weight:700; letter-spacing:.04em; font-size:.86rem; }
.muted { color:var(--muted); } .warning { border-left:5px solid #e69a3a; background:#fff8eb; padding:12px 15px; color:var(--warn); margin:16px 0; }
.facts { background:#f7f9fc; border:1px solid var(--line); border-radius:10px; padding:12px 16px; }
dl { margin:0; } dt { font-weight:700; margin-top:8px; } dd { margin:2px 0 8px 18px; }
.tag { display:inline-block; padding:2px 9px; border-radius:999px; background:#e8eefc; color:#244888; font-size:.86rem; margin-right:6px; }
.question { border-left:3px solid #9badcf; padding-left:12px; }
.trace { border-left:3px solid #87a78c; padding:7px 0 7px 14px; margin:8px 0; }
.role { font-weight:700; } footer { color:var(--muted); font-size:.82rem; text-align:center; margin-top:24px; overflow-wrap:anywhere; }
@media print { body { background:#fff; } main { width:100%; margin:0; } header,.card,.panel { box-shadow:none; break-inside:avoid; } }
""".strip()


def load_yaml(path: Path) -> dict[str, Any]:
    value = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise TypeError(f"YAML root must be a mapping: {path}")
    return value


def source_paths() -> list[Path]:
    paths = [
        KIT_DIR / "assignments.yaml",
        KIT_DIR / "generate.py",
        KIT_DIR / "audit.py",
        H1H4_DIR / "COGNITIVE_INTERVIEW.md",
        REPO_ROOT / "exp_hf_h1_01" / "rubric.yaml",
    ]
    for directory in FAMILY_FILES.values():
        paths.extend(
            [
                H1H4_DIR / "tasks" / directory / "task_card.yaml",
                H1H4_DIR / "tasks" / directory / "participant_instructions.yaml",
            ]
        )
    return paths


def relative_to_repo(path: Path) -> str:
    return path.resolve().relative_to(REPO_ROOT.resolve()).as_posix()


def material_fingerprint() -> tuple[str, dict[str, str]]:
    hashes = {relative_to_repo(path): sha256_file(path) for path in source_paths()}
    canonical = json.dumps(
        hashes, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest(), hashes


def leaf_strings(value: Any) -> set[str]:
    values: set[str] = set()
    if isinstance(value, dict):
        for child in value.values():
            values.update(leaf_strings(child))
    elif isinstance(value, list):
        for child in value:
            values.update(leaf_strings(child))
    elif isinstance(value, str):
        values.add(value.strip())
    return {item for item in values if item}


def scalar_label(value: Any) -> str:
    if isinstance(value, bool):
        return "是" if value else "否"
    if value is None:
        return "暂无"
    return VALUE_LABELS.get(str(value), str(value))


def render_value(value: Any) -> str:
    if isinstance(value, dict):
        parts = ["<dl>"]
        for key, child in value.items():
            label = FIELD_LABELS.get(str(key), VALUE_LABELS.get(str(key), str(key)))
            parts.append(f"<dt>{html.escape(label)}</dt><dd>{render_value(child)}</dd>")
        parts.append("</dl>")
        return "".join(parts)
    if isinstance(value, list):
        return (
            "<ul>"
            + "".join(f"<li>{render_value(item)}</li>" for item in value)
            + "</ul>"
        )
    return html.escape(scalar_label(value))


def surface_for(task: dict[str, Any], surface_id: str) -> dict[str, Any]:
    for surface in task["surfaces"]:
        if surface["surface_id"] == surface_id:
            return surface
    raise ValueError(f"Unknown surface {surface_id}")


def role_for(instructions: dict[str, Any], role_id: str) -> dict[str, Any]:
    for role in instructions["role_cards"]:
        if role["role_id"] == role_id:
            return role
    raise ValueError(f"Unknown role {role_id}")


def condition_for(
    family: str, task: dict[str, Any], surface: dict[str, Any], code: str
) -> dict[str, Any]:
    conditions = task["conditions"] if family == "handoff" else surface["conditions"]
    condition = conditions.get(code)
    if not isinstance(condition, dict):
        raise TypeError(f"Unknown condition {code} for {surface['surface_id']}")
    return condition


def visible_sections(
    family: str,
    role_id: str,
    surface: dict[str, Any],
    condition: dict[str, Any],
) -> list[dict[str, Any]]:
    sections: list[dict[str, Any]] = []
    if family == "revision":
        sections.append({"title": "公开任务说明", "value": surface["public_brief"]})
        if role_id == "drafter":
            sections.append(
                {"title": "公开基线标准", "value": surface["public_baseline_standard"]}
            )
        elif role_id == "reviewer":
            sections.extend(
                [
                    {
                        "title": "当前草稿栏",
                        "value": "正式任务中显示起草人提交的文字；认知访谈不提供完整任务答案。",
                    },
                    {
                        "title": "仅你可见的当前授权标准",
                        "value": condition["reviewer_private_authorized_standard"],
                    },
                ]
            )
        else:
            sections.extend(
                [
                    {
                        "title": "草稿与版本历史栏",
                        "value": "正式任务中显示已提交版本；认知访谈只检查你是否理解怎样使用它。",
                    },
                    {
                        "title": "共享审核与澄清栏",
                        "value": "正式任务中显示团队共享消息；这里不预填正确改动。",
                    },
                ]
            )
    elif family == "verification":
        sections.append(
            {
                "title": "公开情境与行动规则",
                "value": surface["public_situation_and_action_rule"],
            }
        )
        if role_id == "reporter":
            sections.append({"title": "两条原始报告", "value": condition["reports"]})
        elif role_id == "verifier":
            sections.extend(
                [
                    {
                        "title": "信息整理员消息栏",
                        "value": "正式任务中显示整理员提交的两条报告摘要；这里不预填核验答案。",
                    },
                    {
                        "title": "仅你可见的可信来源目录",
                        "value": surface["private_trusted_source_directory"],
                    },
                ]
            )
        else:
            sections.append(
                {
                    "title": "共享整理与核验消息栏",
                    "value": "正式任务中显示前两名成员的消息；这里不预填核验结论或行动答案。",
                }
            )
    elif family == "handoff":
        sections.append(
            {
                "title": "公开目标与阶段顺序",
                "value": surface["public_goal_and_stage_order"],
            }
        )
        if role_id == "worker_A":
            sections.extend(
                [
                    {
                        "title": "第一阶段材料",
                        "value": surface["materials"]["stage_1"]["facts"],
                    },
                    {
                        "title": "检查点状态",
                        "value": "第一阶段提交后由平台生成并封存版本；参与者不能自行填写版本号。",
                    },
                    {
                        "title": "平台可用性通知",
                        "value": condition["availability_event"],
                    },
                ]
            )
        elif role_id == "coordinator":
            sections.extend(
                [
                    {
                        "title": "封存检查点栏",
                        "value": {
                            "已完成阶段": "第一阶段",
                            "其余内容": "由第一执行者提交，平台封存后显示",
                        },
                    },
                    {
                        "title": "平台可用性通知",
                        "value": condition["availability_event"],
                    },
                ]
            )
        else:
            sections.extend(
                [
                    {
                        "title": "封存检查点栏",
                        "value": {
                            "已完成阶段": "第一阶段",
                            "其余内容": "正式任务中由平台显示",
                        },
                    },
                    {
                        "title": "交接消息栏",
                        "value": "只有协调员完成合法指派后才显示；认知访谈不预填指派答案。",
                    },
                    {
                        "title": "后续材料栏",
                        "value": "只有在你被指派接替后才释放；当前不显示。",
                    },
                ]
            )
    elif family == "prioritization":
        sections.append(
            {
                "title": "公开选项与硬约束",
                "value": {
                    key: value
                    for key, value in surface[
                        "public_options_and_hard_constraints"
                    ].items()
                    if key != "feasible_plan_example_for_rule_calibration_only"
                },
            }
        )
        private_key = {
            "operations_member": "operations_private_constraints_and_preferences",
            "safety_member": "safety_private_constraints_and_preferences",
            "coordinator": "coordinator_private_constraints_and_preferences",
        }[role_id]
        sections.append(
            {"title": "仅你可见的职责约束与偏好", "value": condition[private_key]}
        )
    else:
        raise ValueError(f"Unknown family {family}")
    return sections


def private_literals(
    family: str,
    role_id: str,
    task: dict[str, Any],
    instructions: dict[str, Any],
    surface: dict[str, Any],
    condition_code: str,
    public_card: dict[str, Any],
) -> set[str]:
    sensitive: set[str] = set()
    sensitive.update(leaf_strings(task.get("oracle", {})))
    sensitive.update(leaf_strings(instructions.get("pre_task_comprehension", {})))
    sensitive.update(leaf_strings(task.get("control", {})))
    sensitive.update(leaf_strings(task.get("variant", {})))
    sensitive.update(
        leaf_strings(surface.get("feasible_plan_example_for_rule_calibration_only", {}))
    )

    conditions = task["conditions"] if family == "handoff" else surface["conditions"]
    for code, values in conditions.items():
        if code != condition_code:
            sensitive.update(leaf_strings(values))

    current = conditions[condition_code]
    if family == "revision" and role_id != "reviewer":
        sensitive.update(
            leaf_strings(current.get("reviewer_private_authorized_standard", {}))
        )
    elif family == "verification":
        sensitive.update(leaf_strings(current.get("correct_action", "")))
        if role_id != "reporter":
            sensitive.update(leaf_strings(current.get("reports", [])))
        if role_id != "verifier":
            sensitive.update(
                leaf_strings(surface.get("private_trusted_source_directory", {}))
            )
    elif family == "handoff":
        for stage in surface.get("materials", {}).values():
            sensitive.update(leaf_strings(stage.get("expected_result", "")))
        sensitive.update(leaf_strings(surface.get("materials", {}).get("stage_2", {})))
        sensitive.update(leaf_strings(surface.get("materials", {}).get("stage_3", {})))
        if role_id == "worker_B":
            sensitive.update(leaf_strings(current.get("availability_event", "")))
    elif family == "prioritization":
        allowed_key = {
            "operations_member": "operations_private_constraints_and_preferences",
            "safety_member": "safety_private_constraints_and_preferences",
            "coordinator": "coordinator_private_constraints_and_preferences",
        }[role_id]
        for key, value in current.items():
            if key != allowed_key:
                sensitive.update(leaf_strings(value))

    allowed = leaf_strings(public_card)
    return {
        literal
        for literal in sensitive
        if not any(literal in value for value in allowed)
    }


def validate_assignments(
    config: dict[str, Any],
    tasks: dict[str, dict[str, Any]],
    instructions: dict[str, dict[str, Any]],
) -> None:
    if config.get("formal_data_collection_allowed") is not False:
        raise ValueError("Cognitive kit must remain non-formal")
    assignments = config.get("assignments", [])
    if len(assignments) != 6:
        raise ValueError("Exactly six interview assignments are required")
    if [item.get("interview_id") for item in assignments] != [
        f"CI{index:02d}" for index in range(1, 7)
    ]:
        raise ValueError("Interview IDs must be CI01..CI06 in order")

    seen: list[tuple[str, str]] = []
    condition_counts = {"A": 0, "B": 0}
    for assignment in assignments:
        cards = assignment.get("cards", [])
        if len(cards) != 2 or len({card["family"] for card in cards}) != 2:
            raise ValueError(
                f"{assignment['interview_id']} must have two different families"
            )
        for card in cards:
            family = card["family"]
            if family not in tasks:
                raise ValueError(f"Unknown family: {family}")
            task = tasks[family]
            instruction = instructions[family]
            if (
                task.get("formal_data_collection_allowed") is not False
                or instruction.get("formal_data_collection_allowed") is not False
            ):
                raise ValueError(f"Formal collection unexpectedly enabled: {family}")
            role_ids = {role["role_id"] for role in instruction["role_cards"]}
            if card["role_id"] not in role_ids:
                raise ValueError(f"Unknown role: {family}/{card['role_id']}")
            surface = surface_for(task, card["surface_id"])
            condition_for(family, task, surface, card["condition"])
            seen.append((family, card["role_id"]))
            condition_counts[card["condition"]] += 1

    expected = {
        (family, role["role_id"])
        for family, instruction in instructions.items()
        for role in instruction["role_cards"]
    }
    if len(seen) != 12 or len(set(seen)) != 12 or set(seen) != expected:
        raise ValueError(
            "Assignments must cover each of the twelve family-role cards exactly once"
        )
    if condition_counts != {"A": 6, "B": 6}:
        raise ValueError(
            f"Conditions must be administratively balanced: {condition_counts}"
        )


def make_public_card(
    family: str,
    role_id: str,
    task: dict[str, Any],
    instructions: dict[str, Any],
    surface: dict[str, Any],
    condition: dict[str, Any],
) -> dict[str, Any]:
    role = role_for(instructions, role_id)
    unknown_actions = sorted(set(role["available_actions"]) - ACTION_LABELS.keys())
    if unknown_actions:
        raise ValueError(f"Missing action labels: {unknown_actions}")
    return {
        "family_label": FAMILY_LABELS[family],
        "task_title": instructions["common_intro"]["title"],
        "surface_label": surface["label"],
        "purpose": instructions["common_intro"]["purpose_text"],
        "privacy": instructions["common_intro"]["privacy_text"],
        "interaction_rules": list(instructions["common_intro"]["interaction_rules"]),
        "role_title": role["screen_title"],
        "visible_sections": visible_sections(family, role_id, surface, condition),
        "participant_text": list(role["participant_text"]),
        "available_actions": [
            ACTION_LABELS[action] for action in role["available_actions"]
        ],
        "completion_check": list(role["completion_check"]),
        "knowledge_questions": [
            item["prompt"] for item in instructions["pre_task_comprehension"]["items"]
        ],
        "micro_scenario": MICRO_SCENARIOS[(family, role_id)],
        "special_questions": SPECIAL_QUESTIONS[family],
    }


def render_list(items: Iterable[Any]) -> str:
    return (
        "<ul>"
        + "".join(f"<li>{html.escape(str(item))}</li>" for item in items)
        + "</ul>"
    )


def render_participant_packet(
    interview_id: str,
    material_version: str,
    cards: list[dict[str, Any]],
    blind_trace: dict[str, Any],
    rubric: dict[str, Any],
) -> str:
    card_html: list[str] = []
    for index, card in enumerate(cards, start=1):
        visible = "".join(
            f'<h3>{html.escape(section["title"])}</h3><div class="facts">{render_value(section["value"])}</div>'
            for section in card["visible_sections"]
        )
        questions = "".join(
            f'<li class="question">{html.escape(question)}</li>'
            for question in PARAPHRASE_QUESTIONS
        )
        knowledge = "".join(
            f'<li class="question">{html.escape(question)}</li>'
            for question in card["knowledge_questions"]
        )
        special = "".join(
            f"<li>{html.escape(question)}</li>"
            for question in card["special_questions"]
        )
        card_html.append(
            f"""
<article class="card">
  <p class="eyebrow">角色卡 {index} · {html.escape(card["family_label"])}</p>
  <h2>{html.escape(card["task_title"])}</h2>
  <p><span class="tag">任务表面</span>{html.escape(card["surface_label"])}</p>
  <p>{html.escape(card["purpose"])}</p>
  <p class="warning">{html.escape(card["privacy"])}</p>
  <h3>共同互动规则</h3>{render_list(card["interaction_rules"])}
  <h3>{html.escape(card["role_title"])}</h3>{render_list(card["participant_text"])}
  {visible}
  <h3>页面允许的动作</h3>{render_list(card["available_actions"])}
  <h3>完成前自查</h3>{render_list(card["completion_check"])}
  <h3>请先用自己的话回答</h3><ol>{questions}</ol>
  <h3>角色知识检查</h3><p class="muted">主持人不会在第一次回答前提示答案。第一次不确定时请重新阅读角色说明。</p><ol>{knowledge}</ol>
  <h3>微型情境推演</h3><p class="facts">{html.escape(card["micro_scenario"])}</p>
  <h3>说明反馈</h3><ol>{special}</ol>
</article>""".strip()
        )

    trace_html = "".join(
        f'<div class="trace"><span class="role">{html.escape(event["role"])}：</span>{html.escape(event["message"])}</div>'
        for event in blind_trace["events"]
    )
    grouped: dict[str, list[str]] = {}
    dimension_labels = {
        key: value["label"] for key, value in rubric["dimensions"].items()
    }
    for item in rubric["rubric"]:
        grouped.setdefault(dimension_labels[item["dimension"]], []).append(
            item["prompt"]
        )
    rubric_html = "".join(
        f"<h3>{html.escape(label)}</h3>{render_list(prompts)}"
        for label, prompts in grouped.items()
    )

    return f"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width,initial-scale=1">
  <meta name="robots" content="noindex,nofollow,noarchive">
  <meta http-equiv="Content-Security-Policy" content="default-src 'none'; style-src 'unsafe-inline'; img-src data:; connect-src 'none'; form-action 'none'; base-uri 'none'">
  <title>{interview_id} · H1/H4认知访谈材料</title>
  <style>{CSS}</style>
</head>
<body><main>
<header>
  <p class="eyebrow">EXP-HF-H1H4-02 · 认知访谈，不是正式实验</p>
  <h1>{interview_id} 参与者材料</h1>
  <p>我们正在检查多人协作任务的说明是否容易理解，不考察你的能力。请在主持人通知后依次阅读两张角色卡，并把不清楚之处直接说出来。</p>
  <div class="warning">本文件只供代号 {interview_id} 使用。请勿转发、搜索其他角色材料或填写姓名、学校、学号、电话、邮箱等身份信息。你可以随时停止或跳过问题。</div>
  <p class="muted">本页不上传数据、不自动保存，也不包含其他角色卡、知识检查答案、条件名称或来源标签。</p>
</header>
{"".join(card_html)}
<section class="panel">
  <p class="eyebrow">完成两张角色卡之后</p>
  <h2>{html.escape(blind_trace["title"])}</h2>
  <p>{html.escape(blind_trace["public_task"])}</p>
  {trace_html}
  <p class="muted">{html.escape(blind_trace["disclosure"])}</p>
  <h3>候选量表题</h3>
  <p>请逐题说明：你会观察什么行为来作答？它是否能只根据这段轨迹判断？是否与其他题重复？这里不要求你打分。</p>
  {rubric_html}
  <h3>总体追问</h3>
  <ol>
    <li>“自然”“主动性”“社会回应性”“角色连续性”分别是什么意思？</li>
    <li>哪些问题无法只根据轨迹判断，还缺少什么？</li>
    <li>你是否会把“答案正确”直接当成“像真人”？为什么？</li>
    <li>你能否从格式、用词、长度或错误猜测来源？信心如何？</li>
    <li>1分、4分和7分分别应对应怎样的可观察表现？</li>
  </ol>
  <h3>结束反馈</h3>
  <ol>
    <li>今天最难理解的三个词或句子是什么？</li>
    <li>哪一步最容易越过自己的角色边界？</li>
    <li>哪一步最像真实合作，哪一步最像填表？为什么？</li>
    <li>如果在自己电脑上远程完成，你最担心什么？</li>
    <li>页面需要增加什么提示？哪些提示又可能泄露答案？</li>
  </ol>
</section>
<footer>匿名代号 {interview_id} · 材料版本 {material_version} · 请勿转发</footer>
</main></body></html>
"""


def admin_assignments(
    config: dict[str, Any],
    tasks: dict[str, dict[str, Any]],
    instructions: dict[str, dict[str, Any]],
) -> dict[str, list[dict[str, Any]]]:
    output: dict[str, list[dict[str, Any]]] = {}
    for assignment in config["assignments"]:
        cards: list[dict[str, Any]] = []
        for card in assignment["cards"]:
            family = card["family"]
            role = role_for(instructions[family], card["role_id"])
            expected = [
                {
                    "id": item["id"],
                    "prompt": item["prompt"],
                    "expected_concept": item["expected_concept"],
                }
                for item in instructions[family]["pre_task_comprehension"]["items"]
            ]
            cards.append(
                {
                    "card_key": f"{family}:{card['role_id']}:{card['surface_id']}",
                    "family": family,
                    "family_label": FAMILY_LABELS[family],
                    "task_id": tasks[family]["task_id"],
                    "surface_id": card["surface_id"],
                    "surface_label": surface_for(tasks[family], card["surface_id"])[
                        "label"
                    ],
                    "role_id": card["role_id"],
                    "role_title": role["screen_title"],
                    "condition": card["condition"],
                    "knowledge_items": expected,
                }
            )
        output[assignment["interview_id"]] = cards
    return output


def render_facilitator_form(
    material_version: str, assignments: dict[str, list[dict[str, Any]]]
) -> str:
    safe_data = json.dumps(
        {"material_version": material_version, "assignments": assignments},
        ensure_ascii=False,
        separators=(",", ":"),
    ).replace("</", "<\\/")
    options = "".join(f'<option value="{key}">{key}</option>' for key in assignments)
    admin_css = (
        CSS
        + "\nlabel{display:block;font-weight:700;margin:12px 0 4px} input,select,textarea{width:100%;padding:9px;border:1px solid var(--line);border-radius:7px;font:inherit} textarea{min-height:76px} button{background:var(--accent);color:#fff;border:0;border-radius:8px;padding:11px 18px;font-weight:700;cursor:pointer}.grid{display:grid;grid-template-columns:1fr 1fr;gap:12px}.answer{background:#fff4d9;padding:10px;border-radius:8px}.admin{border-left:5px solid #a12626}@media(max-width:680px){.grid{grid-template-columns:1fr}}"
    )
    return f"""<!doctype html>
<html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="robots" content="noindex,nofollow,noarchive"><meta http-equiv="Content-Security-Policy" content="default-src 'none'; style-src 'unsafe-inline'; script-src 'unsafe-inline'; connect-src 'none'; img-src data:; form-action 'none'; base-uri 'none'">
<title>主持人匿名记录页 · EXP-HF-H1H4-02</title><style>{admin_css}</style></head>
<body><main><header class="admin"><p class="eyebrow">仅限主持人，不得发给参与者</p><h1>认知访谈匿名记录页</h1>
<p>本页完全离线，不联网、不使用localStorage。点击导出后浏览器只下载一份JSON；请立即移到受控的非公开目录。</p>
<div class="warning">禁止记录姓名、学校、学号、电话、邮箱、微信或其他身份信息。若不同意参加，只导出最小退出记录，不记录行为内容。</div>
<p>材料版本：<code>{material_version}</code></p></header>
<section class="panel"><div class="grid"><div><label for="interview-id">匿名访谈代号</label><select id="interview-id">{options}</select></div>
<div><label for="consent">是否知情同意</label><select id="consent"><option value="">请选择</option><option value="yes">是</option><option value="no">否</option></select></div></div>
<div class="grid"><div><label for="started-at">开始时间</label><input id="started-at" type="datetime-local"></div><div><label for="ended-at">结束时间</label><input id="ended-at" type="datetime-local"></div></div></section>
<div id="card-records"></div>
<section class="panel"><h2>H1量表认知检查</h2>
<label for="h1-meanings">参与者怎样解释自然、主动性、社会回应性和角色连续性？</label><textarea id="h1-meanings"></textarea>
<label for="h1-unobservable">哪些题不能只根据轨迹判断？</label><textarea id="h1-unobservable"></textarea>
<label for="h1-redundant">哪些题看起来重复？</label><textarea id="h1-redundant"></textarea>
<label for="h1-source-cues">参与者认为哪些格式或措辞会泄露来源？</label><textarea id="h1-source-cues"></textarea>
<label for="h1-correctness">是否把功能正确性等同于像真人？怎样解释？</label><textarea id="h1-correctness"></textarea>
<label for="h1-anchors">参与者怎样解释1、4、7分锚点？</label><textarea id="h1-anchors"></textarea></section>
<section class="panel"><h2>结束与协议记录</h2>
<label for="closing-feedback">最难词句、边界风险、真实感、远程担忧和页面建议（每点一行）</label><textarea id="closing-feedback"></textarea>
<label for="session-deviations">主持人介入或协议偏离（每项一行；没有则留空）</label><textarea id="session-deviations"></textarea>
<button id="export" type="button">导出匿名JSON</button><p id="message" class="muted" aria-live="polite"></p></section>
<footer>主持人工具 · {material_version} · 不得发送给参与者</footer></main>
<script type="application/json" id="assignment-data">{safe_data}</script>
<script>
const study=JSON.parse(document.getElementById('assignment-data').textContent);
const byId=id=>document.getElementById(id);
const esc=value=>String(value).replace(/[&<>"']/g,ch=>({{'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}}[ch]));
const lines=id=>byId(id).value.split(/\\r?\\n/).map(x=>x.trim()).filter(Boolean);
const tri=id=>{{const value=byId(id).value;return value===''?null:value==='true';}};
function renderCards(){{
  const id=byId('interview-id').value;
  byId('card-records').innerHTML=study.assignments[id].map((card,index)=>`<section class="panel admin"><p class="eyebrow">主持人记录 · 角色卡 ${{index+1}}</p><h2>${{esc(card.family_label)}} · ${{esc(card.role_title)}}</h2><p>${{esc(card.surface_label)}} · 后台条件 ${{esc(card.condition)}}</p>
  <div class="answer"><strong>知识检查概念：</strong><ol>${{card.knowledge_items.map(item=>`<li>${{esc(item.prompt)}}<br><span class="muted">${{esc(item.expected_concept)}}</span></li>`).join('')}}</ol></div>
  <div class="grid"><div><label for="c${{index}}-read">阅读秒数</label><input id="c${{index}}-read" type="number" min="0"></div><div><label for="c${{index}}-knowledge">知识检查结果</label><select id="c${{index}}-knowledge"><option value="">未记录</option><option value="first">首次答对</option><option value="reread">重读后答对</option><option value="fail">两次未答对</option></select></div></div>
  <div class="grid"><div><label for="c${{index}}-paraphrase">无提示复述正确</label><select id="c${{index}}-paraphrase"><option value="">未记录</option><option value="true">是</option><option value="false">否</option></select></div><div><label for="c${{index}}-boundary">信息边界理解正确</label><select id="c${{index}}-boundary"><option value="">未记录</option><option value="true">是</option><option value="false">否</option></select></div></div>
  <label for="c${{index}}-termination">结束条件理解正确</label><select id="c${{index}}-termination"><option value="">未记录</option><option value="true">是</option><option value="false">否</option></select>
  <label for="c${{index}}-micro">微型情境中的下一步理解摘要</label><textarea id="c${{index}}-micro"></textarea>
  <label for="c${{index}}-ambiguous">含糊词句（每项一行）</label><textarea id="c${{index}}-ambiguous"></textarea>
  <label for="c${{index}}-action">动作误解（每项一行）</label><textarea id="c${{index}}-action"></textarea>
  <label for="c${{index}}-boundary-notes">边界误解（每项一行）</label><textarea id="c${{index}}-boundary-notes"></textarea>
  <label for="c${{index}}-prompts">主持人额外提示（每项一行）</label><textarea id="c${{index}}-prompts"></textarea>
  <label for="c${{index}}-changes">参与者建议（每项一行）</label><textarea id="c${{index}}-changes"></textarea></section>`).join('');
}}
function text(id){{return byId(id).value.trim();}}
function exportRecord(){{
  const interviewId=byId('interview-id').value, consent=byId('consent').value;
  if(!consent){{byId('message').textContent='请先记录是否同意。';return;}}
  let record={{schema_version:1,experiment_id:'EXP-HF-H1H4-02',interview_id:interviewId,material_version:study.material_version,consent:consent==='yes',started_at:text('started-at'),ended_at:text('ended-at')}};
  if(consent==='yes'){{
    record.card_records=study.assignments[interviewId].map((card,index)=>({{card_key:card.card_key,task_id:card.task_id,surface_id:card.surface_id,role_id:card.role_id,condition:card.condition,read_seconds:Number(text(`c${{index}}-read`))||null,paraphrase_correct_without_prompt:tri(`c${{index}}-paraphrase`),information_boundary_correct_without_prompt:tri(`c${{index}}-boundary`),termination_rule_correct_without_prompt:tri(`c${{index}}-termination`),knowledge_check_result:text(`c${{index}}-knowledge`)||null,micro_scenario_understanding:text(`c${{index}}-micro`),ambiguous_phrases:lines(`c${{index}}-ambiguous`),expected_action_misunderstandings:lines(`c${{index}}-action`),boundary_misunderstandings:lines(`c${{index}}-boundary-notes`),facilitator_prompts:lines(`c${{index}}-prompts`),participant_suggested_changes:lines(`c${{index}}-changes`)}}));
    record.h1_cognitive_review={{dimension_meanings:text('h1-meanings'),unobservable_items:lines('h1-unobservable'),redundant_items:lines('h1-redundant'),possible_source_cues:lines('h1-source-cues'),correctness_conflation:text('h1-correctness'),scale_anchor_interpretation:text('h1-anchors')}};
    record.closing_feedback=lines('closing-feedback'); record.protocol_deviations=lines('session-deviations');
  }}
  const blob=new Blob([JSON.stringify(record,null,2)+'\\n'],{{type:'application/json'}}),url=URL.createObjectURL(blob),a=document.createElement('a');
  const stamp=(new Date()).toISOString().replace(/[:.]/g,'-'); a.href=url;a.download=`${{interviewId}}_${{stamp}}.json`;a.click();URL.revokeObjectURL(url);
  byId('message').textContent=consent==='yes'?'已下载匿名记录；请移到非公开受控目录并运行泄漏检查。':'已下载最小退出记录；未保存行为字段。';
}}
byId('interview-id').addEventListener('change',renderCards);byId('export').addEventListener('click',exportRecord);renderCards();
</script></body></html>"""


def record_template(material_version: str) -> dict[str, Any]:
    return {
        "schema_version": 1,
        "experiment_id": "EXP-HF-H1H4-02",
        "interview_id": "CIxx",
        "material_version": material_version,
        "consent": True,
        "started_at": "",
        "ended_at": "",
        "card_records": [
            {
                "card_key": "assigned_card_key",
                "task_id": "",
                "surface_id": "",
                "role_id": "",
                "condition": "admin_only",
                "read_seconds": None,
                "paraphrase_correct_without_prompt": None,
                "information_boundary_correct_without_prompt": None,
                "termination_rule_correct_without_prompt": None,
                "knowledge_check_result": None,
                "micro_scenario_understanding": "",
                "ambiguous_phrases": [],
                "expected_action_misunderstandings": [],
                "boundary_misunderstandings": [],
                "facilitator_prompts": [],
                "participant_suggested_changes": [],
            }
        ],
        "h1_cognitive_review": {
            "dimension_meanings": "",
            "unobservable_items": [],
            "redundant_items": [],
            "possible_source_cues": [],
            "correctness_conflation": "",
            "scale_anchor_interpretation": "",
        },
        "closing_feedback": [],
        "protocol_deviations": [],
    }


def assignment_csv(
    assignments: dict[str, list[dict[str, Any]]], material_version: str
) -> str:
    stream = io.StringIO(newline="")
    writer = csv.DictWriter(
        stream,
        fieldnames=[
            "interview_id",
            "card_number",
            "family",
            "role_id",
            "surface_id",
            "condition",
            "material_version",
        ],
        lineterminator="\n",
    )
    writer.writeheader()
    for interview_id, cards in assignments.items():
        for index, card in enumerate(cards, start=1):
            writer.writerow(
                {
                    "interview_id": interview_id,
                    "card_number": index,
                    "family": card["family"],
                    "role_id": card["role_id"],
                    "surface_id": card["surface_id"],
                    "condition": card["condition"],
                    "material_version": material_version,
                }
            )
    return "\ufeff" + stream.getvalue()


def dist_readme(material_version: str, packet_hashes: dict[str, str]) -> str:
    rows = "\n".join(
        f"| {path.removeprefix('participant_packets/').removesuffix('.html')} | `{path}` | `{digest}` |"
        for path, digest in sorted(packet_hashes.items())
    )
    return f"""# EXP-HF-H1H4-02 认知访谈材料包

材料版本：`{material_version}`

## 发放规则

只把对应的单个HTML文件发给对应匿名代号；不要发送本目录、压缩整个目录、发送GitHub链接或发送`admin/`。参与者可以直接双击HTML离线打开，不需要Python，也不会联网或保存输入。

| 匿名代号 | 只发送这个文件 | SHA-256 |
|---|---|---|
{rows}

主持人使用`admin/facilitator_record.html`记录。导出的JSON必须移到公开仓库之外，并用`python -m human_validity.h1_h4_v2.cognitive_interview_kit.audit --records <私有目录>`检查。自动检查不能识别所有姓名或上下文身份线索，仍需人工复核。

本材料仅用于5–8人认知访谈，不是正式Human Reference，不允许据此计算Human–Agent差异。
"""


def write_text(path: Path, value: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(value, encoding="utf-8", newline="\n")


def prepare_output(out: Path) -> None:
    resolved = out.resolve()
    dangerous = {
        Path(resolved.anchor).resolve(),
        REPO_ROOT.resolve(),
        H1H4_DIR.resolve(),
        KIT_DIR.resolve(),
    }
    if resolved in dangerous:
        raise ValueError(f"Refusing broad output path: {resolved}")
    if resolved.exists():
        marker = resolved / OUTPUT_MARKER
        owned = (
            marker.is_file()
            and marker.read_text(encoding="utf-8").strip() == "EXP-HF-H1H4-02"
        )
        if not owned:
            raise ValueError(
                f"Refusing to replace unowned output directory: {resolved}"
            )
        shutil.rmtree(resolved)
    resolved.mkdir(parents=True)
    write_text(resolved / OUTPUT_MARKER, "EXP-HF-H1H4-02\n")


def generate(out: Path) -> dict[str, Any]:
    config = load_yaml(KIT_DIR / "assignments.yaml")
    tasks = {
        family: load_yaml(H1H4_DIR / "tasks" / directory / "task_card.yaml")
        for family, directory in FAMILY_FILES.items()
    }
    instructions = {
        family: load_yaml(
            H1H4_DIR / "tasks" / directory / "participant_instructions.yaml"
        )
        for family, directory in FAMILY_FILES.items()
    }
    rubric = load_yaml(REPO_ROOT / "exp_hf_h1_01" / "rubric.yaml")
    validate_assignments(config, tasks, instructions)
    material_sha256, input_hashes = material_fingerprint()
    material_version = f"CIKIT-{material_sha256[:16]}"

    prepare_output(out)
    (out / "participant_packets").mkdir(parents=True)
    (out / "admin").mkdir(parents=True)

    packet_audits: list[dict[str, Any]] = []
    packet_hashes: dict[str, str] = {}
    for assignment in config["assignments"]:
        public_cards: list[dict[str, Any]] = []
        model_failures: list[str] = []
        for assigned in assignment["cards"]:
            family = assigned["family"]
            task = tasks[family]
            instruction = instructions[family]
            surface = surface_for(task, assigned["surface_id"])
            condition = condition_for(family, task, surface, assigned["condition"])
            public_card = make_public_card(
                family,
                assigned["role_id"],
                task,
                instruction,
                surface,
                condition,
            )
            model_failures.extend(
                audit_public_model(
                    public_card,
                    private_literals(
                        family,
                        assigned["role_id"],
                        task,
                        instruction,
                        surface,
                        assigned["condition"],
                        public_card,
                    ),
                )
            )
            public_cards.append(public_card)
        if model_failures:
            raise ValueError(
                f"Public model leak for {assignment['interview_id']}: {model_failures}"
            )

        packet = render_participant_packet(
            assignment["interview_id"],
            material_version,
            public_cards,
            config["blind_trace_example"],
            rubric,
        )
        relative = f"participant_packets/{assignment['interview_id']}.html"
        path = out / relative
        write_text(path, packet)
        html_failures = audit_participant_html(path)
        if html_failures:
            raise ValueError(
                f"Rendered participant leak for {assignment['interview_id']}: {html_failures}"
            )
        digest = sha256_file(path)
        packet_hashes[relative] = digest
        packet_audits.append(
            {
                "interview_id": assignment["interview_id"],
                "packet": relative,
                "sha256": digest,
                "public_model_allowlist": "passed",
                "private_literal_scan": "passed",
                "rendered_hidden_token_scan": "passed",
                "script_or_input_scan": "passed",
                "external_resource_scan": "passed",
            }
        )

    admin_data = admin_assignments(config, tasks, instructions)
    write_text(
        out / "admin" / "facilitator_record.html",
        render_facilitator_form(material_version, admin_data),
    )
    write_text(
        out / "admin" / "ASSIGNMENT_TABLE.csv",
        assignment_csv(admin_data, material_version),
    )
    write_text(
        out / "admin" / "INTERVIEW_RECORD_TEMPLATE.json",
        json.dumps(record_template(material_version), ensure_ascii=False, indent=2)
        + "\n",
    )

    leak_audit = {
        "schema_version": 1,
        "experiment_id": "EXP-HF-H1H4-02",
        "material_version": material_version,
        "passed": True,
        "scope": "participant_packets_only",
        "checks": [
            "six_assignments_and_twelve_unique_family_role_cards",
            "administrative_conditions_balanced_six_and_six",
            "public_model_field_allowlist",
            "private_literal_absence",
            "hidden_backend_token_absence",
            "no_participant_scripts_or_input_collection",
            "no_external_resources_or_network_access",
        ],
        "packets": packet_audits,
        "limitations": [
            "static_files_cannot_prevent_a_recipient_from_forwarding_their_own_packet",
            "send_only_one_named_HTML_not_the_dist_directory_or_repository_link",
            "automated_record_PII_scan_requires_manual_review_for_names_and_contextual_identifiers",
        ],
    }
    write_text(
        out / "LEAK_AUDIT.json",
        json.dumps(leak_audit, ensure_ascii=False, indent=2) + "\n",
    )

    preliminary_hashes = {
        path.relative_to(out).as_posix(): sha256_file(path)
        for path in sorted(out.rglob("*"))
        if path.is_file()
    }
    write_text(out / "README.md", dist_readme(material_version, packet_hashes))
    output_hashes = {
        path.relative_to(out).as_posix(): sha256_file(path)
        for path in sorted(out.rglob("*"))
        if path.is_file() and path.name != "MANIFEST.json"
    }
    assert set(preliminary_hashes).issubset(output_hashes)
    manifest = {
        "schema_version": 1,
        "experiment_id": "EXP-HF-H1H4-02",
        "status": "cognitive_interview_only_not_formal_data",
        "formal_data_collection_allowed": False,
        "material_version": material_version,
        "material_sha256": material_sha256,
        "deterministic_generation": True,
        "participant_packet_count": 6,
        "cards_total": 12,
        "source_sha256": input_hashes,
        "output_sha256": output_hashes,
        "raw_records_in_public_repository_allowed": False,
    }
    write_text(
        out / "MANIFEST.json", json.dumps(manifest, ensure_ascii=False, indent=2) + "\n"
    )
    return manifest


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    manifest = generate(args.out.resolve())
    print(args.out.resolve())
    print(f"material_version={manifest['material_version']}")
    print(f"participant_packets={manifest['participant_packet_count']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
