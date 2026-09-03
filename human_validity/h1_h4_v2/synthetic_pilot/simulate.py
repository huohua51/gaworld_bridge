"""Generate a deterministic synthetic dry run for EXP-HF-H1H4-02.

This module never calls a model and never reads real participant data.  Its only
purpose is to exercise the planned Wave 1 denominators, H4 coding diagnostics,
and H1 rating summaries before the remote collection system exists.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import random
import statistics
from collections import defaultdict
from pathlib import Path
from typing import Any


SEED = 20260903
H1_ITEMS = [f"H1-{index:02d}" for index in range(1, 13)]
DIMENSIONS = {
    "naturalness": H1_ITEMS[0:3],
    "agency": H1_ITEMS[3:6],
    "social_responsiveness": H1_ITEMS[6:9],
    "role_continuity": H1_ITEMS[9:12],
}


HUMAN_TRACES: list[dict[str, Any]] = [
    {
        "trace_id": "SYN-H-P01-01",
        "unit_id": "SYN-P01",
        "surface_id": "rev_campus_notice_001",
        "condition": "A",
        "family": "revision",
        "functional_pass": True,
        "completion_seconds": 574,
        "turns": [2, 2, 1],
        "accepted_actions": 7,
        "role_boundary_violations": 0,
        "idempotent_retries": 0,
        "functional": {"authorized_fact_accuracy": [5, 5]},
        "h4": {
            "clarification_request_rate": [0, 0],
            "specific_challenge_rate": [0, 0],
            "valid_correction_adoption_rate": [0, 0],
            "role_boundary_violation_rate": [0, 7],
        },
        "note": "标准未变化；审核员明确保留，没有为制造互动而提出假修改。",
    },
    {
        "trace_id": "SYN-H-P01-02",
        "unit_id": "SYN-P01",
        "surface_id": "verify_supply_arrival_001",
        "condition": "B",
        "family": "verification",
        "functional_pass": True,
        "completion_seconds": 706,
        "turns": [3, 3, 2],
        "accepted_actions": 10,
        "role_boundary_violations": 0,
        "idempotent_retries": 0,
        "functional": {
            "report_preservation": [6, 6],
            "verification_completeness": [4, 4],
            "verified_decision_accuracy": [1, 1],
        },
        "h4": {
            "clarification_request_rate": [1, 1],
            "explicit_verification_rate": [1, 1],
            "verified_information_adoption_rate": [1, 1],
            "unverified_action_rate": [0, 1],
            "role_boundary_violation_rate": [0, 10],
        },
        "note": "整理员第一次漏写报告时间，核验员提出具体问题后补齐。",
    },
    {
        "trace_id": "SYN-H-P02-01",
        "unit_id": "SYN-P02",
        "surface_id": "handoff_event_materials_001",
        "condition": "A",
        "family": "handoff",
        "functional_pass": True,
        "completion_seconds": 681,
        "turns": [3, 2, 1],
        "accepted_actions": 9,
        "role_boundary_violations": 0,
        "idempotent_retries": 0,
        "functional": {
            "stage_fact_accuracy": [9, 9],
            "checkpoint_completeness": [4, 4],
            "authorized_stage_completion": [3, 3],
        },
        "h4": {
            "handoff_completeness": [4, 4],
            "redundant_work_rate": [0, 1],
            "role_boundary_violation_rate": [0, 9],
            "clarification_request_rate": [0, 0],
            "recovery_time_seconds": 42,
        },
        "note": "原执行者继续；协调员仍明确登记下一阶段，未重复第一阶段。",
    },
    {
        "trace_id": "SYN-H-P02-02",
        "unit_id": "SYN-P02",
        "surface_id": "rev_volunteer_shift_001",
        "condition": "B",
        "family": "revision",
        "functional_pass": False,
        "completion_seconds": 815,
        "turns": [3, 3, 2],
        "accepted_actions": 10,
        "role_boundary_violations": 0,
        "idempotent_retries": 0,
        "functional": {
            "authorized_fact_accuracy": [4, 5],
            "material_difference_detection_rate": [4, 5],
        },
        "h4": {
            "clarification_request_rate": [0, 0],
            "specific_challenge_rate": [4, 5],
            "valid_correction_adoption_rate": [4, 4],
            "role_boundary_violation_rate": [0, 10],
        },
        "note": "审核和采纳过程可追溯，但审核员漏掉负责人到场时间，最终保留一个旧值。",
    },
    {
        "trace_id": "SYN-H-P03-01",
        "unit_id": "SYN-P03",
        "surface_id": "verify_room_access_001",
        "condition": "A",
        "family": "verification",
        "functional_pass": True,
        "completion_seconds": 748,
        "turns": [2, 4, 3],
        "accepted_actions": 11,
        "role_boundary_violations": 0,
        "idempotent_retries": 0,
        "functional": {
            "report_preservation": [6, 6],
            "verification_completeness": [4, 4],
            "verified_decision_accuracy": [1, 1],
        },
        "h4": {
            "clarification_request_rate": [1, 1],
            "explicit_verification_rate": [1, 1],
            "verified_information_adoption_rate": [1, 1],
            "unverified_action_rate": [0, 1],
            "role_boundary_violation_rate": [0, 11],
        },
        "note": "核验消息起初缺目录版本，协调员等待并请求补充后再行动。",
    },
    {
        "trace_id": "SYN-H-P03-02",
        "unit_id": "SYN-P03",
        "surface_id": "handoff_appointment_queue_001",
        "condition": "B",
        "family": "handoff",
        "functional_pass": False,
        "completion_seconds": 1034,
        "turns": [3, 3, 4],
        "accepted_actions": 12,
        "role_boundary_violations": 0,
        "idempotent_retries": 0,
        "functional": {
            "stage_fact_accuracy": [9, 9],
            "checkpoint_completeness": [4, 4],
            "authorized_stage_completion": [2, 3],
        },
        "h4": {
            "handoff_completeness": [4, 4],
            "redundant_work_rate": [1, 1],
            "role_boundary_violation_rate": [0, 12],
            "clarification_request_rate": [1, 1],
            "recovery_time_seconds": 130,
        },
        "note": "接替者看到了检查点，却重新提交第一阶段；后续事实正确但全过程不通过。",
    },
    {
        "trace_id": "SYN-H-P04-01",
        "unit_id": "SYN-P04",
        "surface_id": "handoff_appointment_queue_001",
        "condition": "A",
        "family": "handoff",
        "functional_pass": True,
        "completion_seconds": 729,
        "turns": [3, 2, 1],
        "accepted_actions": 9,
        "role_boundary_violations": 0,
        "idempotent_retries": 1,
        "functional": {
            "stage_fact_accuracy": [9, 9],
            "checkpoint_completeness": [4, 4],
            "authorized_stage_completion": [3, 3],
        },
        "h4": {
            "handoff_completeness": [4, 4],
            "redundant_work_rate": [0, 1],
            "role_boundary_violation_rate": [0, 9],
            "clarification_request_rate": [0, 0],
            "recovery_time_seconds": 55,
        },
        "note": "一次断线重试被幂等去重，业务事件没有重复计数。",
    },
    {
        "trace_id": "SYN-H-P04-02",
        "unit_id": "SYN-P04",
        "surface_id": "rev_campus_notice_001",
        "condition": "B",
        "family": "revision",
        "functional_pass": True,
        "completion_seconds": 762,
        "turns": [3, 3, 2],
        "accepted_actions": 10,
        "role_boundary_violations": 0,
        "idempotent_retries": 0,
        "functional": {
            "authorized_fact_accuracy": [5, 5],
            "material_difference_detection_rate": [3, 3],
        },
        "h4": {
            "clarification_request_rate": [1, 1],
            "specific_challenge_rate": [3, 3],
            "valid_correction_adoption_rate": [3, 3],
            "role_boundary_violation_rate": [0, 10],
        },
        "note": "发布人追问含糊的地点修改，审核员补充具体新地点后完整采纳。",
    },
]


def make_agent_traces() -> list[dict[str, Any]]:
    traces: list[dict[str, Any]] = []
    for index, human in enumerate(HUMAN_TRACES, start=1):
        trace = {
            **human,
            "trace_id": f"SYN-A-{index:02d}",
            "unit_id": f"SYN-AGENT-RUN-{index:02d}",
            "completion_seconds": [104, 126, 91, 132, 119, 108, 88, 125][index - 1],
            "turns": [1, 1, 1],
            "accepted_actions": 6,
            "idempotent_retries": 0,
            "note": "合成Agent占位轨迹；没有发生真实模型调用。",
        }
        if trace["family"] == "revision":
            changed = 0 if trace["condition"] == "A" else (5 if "volunteer" in trace["surface_id"] else 3)
            trace["functional_pass"] = True
            trace["functional"] = {
                "authorized_fact_accuracy": [5, 5],
                "material_difference_detection_rate": [changed, changed],
            }
            trace["h4"] = {
                "clarification_request_rate": [0, 0],
                "specific_challenge_rate": [changed, changed],
                "valid_correction_adoption_rate": [changed, changed],
                "role_boundary_violation_rate": [0, 6],
            }
        elif trace["family"] == "verification":
            trace["functional_pass"] = True
            trace["functional"] = {
                "report_preservation": [6, 6],
                "verification_completeness": [4, 4],
                "verified_decision_accuracy": [1, 1],
            }
            trace["h4"] = {
                "clarification_request_rate": [0, 0],
                "explicit_verification_rate": [1, 1],
                "verified_information_adoption_rate": [1, 1],
                "unverified_action_rate": [0, 1],
                "role_boundary_violation_rate": [0, 6],
            }
        else:
            trace["functional_pass"] = index != 6
            checkpoint = [3, 4] if index == 6 else [4, 4]
            authorized = [2, 3] if index == 6 else [3, 3]
            trace["functional"] = {
                "stage_fact_accuracy": [9, 9],
                "checkpoint_completeness": checkpoint,
                "authorized_stage_completion": authorized,
            }
            trace["h4"] = {
                "handoff_completeness": checkpoint,
                "redundant_work_rate": [0, 1],
                "role_boundary_violation_rate": [0, 6],
                "clarification_request_rate": [0, 0],
                "recovery_time_seconds": [8, 9, 7][[3, 6, 7].index(index)],
            }
        traces.append(trace)
    return traces


CODER_PAIRS = {
    "clarification_request": [(1, 1)] * 4 + [(1, 0), (0, 1)] + [(0, 0)] * 6,
    "specific_challenge": [(1, 1)] * 3 + [(1, 0)] + [(0, 0)] * 8,
    "valid_correction": [(1, 1)] * 5 + [(1, 0)] + [(0, 0)] * 4,
    "correction_adopted": [(1, 1)] * 3 + [(1, 0)] * 2 + [(0, 1)] + [(0, 0)] * 4,
}


def ratio_text(value: Any) -> str:
    if not isinstance(value, list):
        return str(value)
    numerator, denominator = value
    return "N/A" if denominator == 0 else f"{numerator}/{denominator} ({numerator / denominator:.3f})"


def icc_one_way(groups: list[list[float]]) -> float:
    """Balanced one-way random effects ICC(1), used only as a pilot diagnostic."""
    if not groups or len({len(group) for group in groups}) != 1:
        return math.nan
    k = len(groups[0])
    if k < 2:
        return math.nan
    group_means = [statistics.mean(group) for group in groups]
    grand_mean = statistics.mean(value for group in groups for value in group)
    ms_between = k * sum((mean - grand_mean) ** 2 for mean in group_means) / (len(groups) - 1)
    ms_within = sum(
        sum((value - group_means[index]) ** 2 for value in group)
        for index, group in enumerate(groups)
    ) / (len(groups) * (k - 1))
    denominator = ms_between + (k - 1) * ms_within
    return (ms_between - ms_within) / denominator if denominator else math.nan


def cohen_kappa(pairs: list[tuple[int, int]]) -> tuple[float, float]:
    n = len(pairs)
    observed = sum(a == b for a, b in pairs) / n
    p1 = sum(a for a, _ in pairs) / n
    p2 = sum(b for _, b in pairs) / n
    expected = p1 * p2 + (1 - p1) * (1 - p2)
    kappa = (observed - expected) / (1 - expected) if expected != 1 else math.nan
    return observed, kappa


def generate_h1_ratings(traces: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rng = random.Random(SEED)
    bases = {
        "synthetic_human": {
            "naturalness": 5.35,
            "agency": 5.35,
            "social_responsiveness": 5.20,
            "role_continuity": 5.45,
        },
        "synthetic_agent": {
            "naturalness": 4.45,
            "agency": 5.10,
            "social_responsiveness": 4.75,
            "role_continuity": 5.55,
        },
    }
    rater_biases = [-0.45, -0.20, -0.05, 0.10, 0.25, 0.35]
    rows: list[dict[str, Any]] = []
    for stimulus_index, trace in enumerate(traces, start=1):
        source = trace["source_kind"]
        for rater_index, bias in enumerate(rater_biases, start=1):
            row: dict[str, Any] = {
                "rating_id": f"SYN-RATE-{stimulus_index:02d}-{rater_index:02d}",
                "stimulus_id": f"SYN-STIM-{stimulus_index:02d}",
                "trace_id": trace["trace_id"],
                "source_kind_hidden_during_rating": source,
                "rater_id": f"SYN-RATER-{rater_index:02d}",
                "task_understanding_check": 0 if (stimulus_index, rater_index) in {(5, 2), (13, 5)} else 1,
            }
            for dimension, items in DIMENSIONS.items():
                functional_penalty = 0 if trace["functional_pass"] else (0.25 if dimension == "naturalness" else 0.55)
                family_shift = {"revision": 0.10, "verification": 0.00, "handoff": -0.10}[trace["family"]]
                for item_offset, item in enumerate(items):
                    score = (
                        bases[source][dimension]
                        + bias
                        + family_shift
                        - functional_penalty
                        + (item_offset - 1) * 0.08
                        + rng.gauss(0, 0.58)
                    )
                    row[item] = max(1, min(7, int(round(score))))
            if (stimulus_index, rater_index) == (10, 4):
                row["H1-09"] = ""
            natural_values = [row[item] for item in DIMENSIONS["naturalness"] if row[item] != ""]
            perceived_human_probability = 0.66 if source == "synthetic_human" else 0.34
            guess_human = rng.random() < perceived_human_probability
            row["guessed_source"] = "Human" if guess_human else "Agent"
            row["guess_confidence_1_to_5"] = max(
                1,
                min(5, int(round(2.5 + abs(statistics.mean(natural_values) - 4.5) + rng.random()))),
            )
            rows.append(row)
    return rows


def aggregate_h4(traces: list[dict[str, Any]]) -> dict[tuple[str, str], dict[str, Any]]:
    output: dict[tuple[str, str], dict[str, Any]] = {}
    grouped: defaultdict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for trace in traces:
        grouped[(trace["source_kind"], trace["family"])].append(trace)
    for key, group in grouped.items():
        metric_names = sorted({name for trace in group for name in trace["h4"]})
        metrics: dict[str, Any] = {}
        for name in metric_names:
            values = [trace["h4"][name] for trace in group if name in trace["h4"]]
            if name == "recovery_time_seconds":
                metrics[name] = statistics.median(values)
            else:
                metrics[name] = [sum(value[0] for value in values), sum(value[1] for value in values)]
        output[key] = metrics
    return output


def aggregate_h1(
    rows: list[dict[str, Any]],
) -> tuple[dict[str, dict[str, float]], dict[str, float], dict[str, tuple[float, float, float]]]:
    dimension_means: dict[str, dict[str, float]] = defaultdict(dict)
    stimulus_dimension: defaultdict[tuple[str, str], list[float]] = defaultdict(list)
    for row in rows:
        for dimension, items in DIMENSIONS.items():
            values = [float(row[item]) for item in items if row[item] != ""]
            stimulus_dimension[(row["stimulus_id"], dimension)].append(statistics.mean(values))
    source_by_stimulus = {row["stimulus_id"]: row["source_kind_hidden_during_rating"] for row in rows}
    for source in ("synthetic_human", "synthetic_agent"):
        for dimension in DIMENSIONS:
            values = [
                value
                for (stimulus_id, dim), group in stimulus_dimension.items()
                if dim == dimension and source_by_stimulus[stimulus_id] == source
                for value in group
            ]
            dimension_means[source][dimension] = statistics.mean(values)
    reliability = {
        dimension: icc_one_way(
            [
                group
                for (stimulus_id, dim), group in sorted(stimulus_dimension.items())
                if dim == dimension
            ]
        )
        for dimension in DIMENSIONS
    }
    paired_intervals: dict[str, tuple[float, float, float]] = {}
    human_stimuli = sorted(
        stimulus_id for stimulus_id, source in source_by_stimulus.items() if source == "synthetic_human"
    )
    agent_stimuli = sorted(
        stimulus_id for stimulus_id, source in source_by_stimulus.items() if source == "synthetic_agent"
    )
    for dimension in DIMENSIONS:
        differences = [
            statistics.mean(stimulus_dimension[(human_id, dimension)])
            - statistics.mean(stimulus_dimension[(agent_id, dimension)])
            for human_id, agent_id in zip(human_stimuli, agent_stimuli, strict=True)
        ]
        mean_gap = statistics.mean(differences)
        standard_error = statistics.stdev(differences) / math.sqrt(len(differences))
        t_975_df7 = 2.364624
        paired_intervals[dimension] = (
            mean_gap,
            mean_gap - t_975_df7 * standard_error,
            mean_gap + t_975_df7 * standard_error,
        )
    return dict(dimension_means), reliability, paired_intervals


def write_csv(path: Path, rows: list[dict[str, Any]], fieldnames: list[str]) -> None:
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def render_report(
    traces: list[dict[str, Any]],
    ratings: list[dict[str, Any]],
    h4: dict[tuple[str, str], dict[str, Any]],
    h1: dict[str, dict[str, float]],
    reliability: dict[str, float],
    paired_intervals: dict[str, tuple[float, float, float]],
    coder_rows: list[dict[str, Any]],
) -> str:
    human = [trace for trace in traces if trace["source_kind"] == "synthetic_human"]
    agent = [trace for trace in traces if trace["source_kind"] == "synthetic_agent"]
    missing_items = sum(row[item] == "" for row in ratings for item in H1_ITEMS)
    understood = sum(row["task_understanding_check"] for row in ratings)
    correct_guesses = sum(
        (row["guessed_source"] == "Human")
        == (row["source_kind_hidden_during_rating"] == "synthetic_human")
        for row in ratings
    )
    mean_confidence = statistics.mean(row["guess_confidence_1_to_5"] for row in ratings)
    participation = {}
    for source, group in (("synthetic_human", human), ("synthetic_agent", agent)):
        dispersions = []
        for trace in group:
            turn_total = sum(trace["turns"])
            shares = [turns / turn_total for turns in trace["turns"]]
            dispersions.append(max(shares) - min(shares))
        participation[source] = {
            "turns": sum(sum(trace["turns"]) for trace in group),
            "mean_dispersion": statistics.mean(dispersions),
        }
    lines = [
        "# EXP-HF-H1H4-02 合成内部试采演练结果",
        "",
        "> **警告：本目录全部是合成数据。真实参与者为0，真实模型调用为0，API费用为0。**",
        "> 本结果只能检查采集字段、分母、编码和报告逻辑，绝不能作为Human Reference、模型能力或论文实证结果。",
        "",
        "## 一、这次模拟了什么",
        "",
        "按照`PILOT_PLAN.yaml`的Wave 1固定分配，模拟4个三人团队、12个匿名角色和8条Human轨迹；另造8条任务/条件匹配的Agent占位轨迹。6名合成盲评员各评16个刺激，共96份评分、1152个H1题目单元。共同排序Wave 2没有模拟，因为其协调依赖仍未解除。",
        "",
        "H1来源差异、猜测概率和两个功能失败都是生成器事先注入的测试场景，不是从真实对话或模型中观察得到。它们的作用是确认分析能否正确输出差值、区间、缺失值和修订门，而不是预言正式采集会得到相同方向或大小。",
        "",
        "模拟不是把每条轨迹都做成满分：其中安排了一个修订漏项、一个中断后重复劳动、四次合理澄清、一次幂等网络重试和一项低于门槛的双人编码一致性。这样才能检查失败是否会落到正确分母和正确修订决定。",
        "",
        "## 二、管线结果",
        "",
        "| 检查 | 合成结果 | 解释 |",
        "| --- | ---: | --- |",
        f"| Wave 1 Human会话完成 | {len(human)}/{len(human)} | 无退出、超时或R0无效 |",
        f"| 匹配Agent占位轨迹完成 | {len(agent)}/{len(agent)} | 仅为合成评分输入，不是真实调用 |",
        "| 私有信息/来源标签泄漏 | 0 | 这是模拟设定，不等于远程系统已经通过安全测试 |",
        f"| 幂等重试 | {sum(t['idempotent_retries'] for t in traces)}次 | 重试未产生重复业务事件 |",
        f"| H1任务理解检查 | {understood}/{len(ratings)} | 两份评分理解检查失败，正式方案需预注册保留/排除规则 |",
        f"| H1题目缺失 | {missing_items}/{len(ratings) * len(H1_ITEMS)} | 验证缺失值不会被静默补成中点 |",
        "",
        "## 三、功能结果",
        "",
        "| 来源 | 修订 | 核验 | 交接 | 总计 |",
        "| --- | ---: | ---: | ---: | ---: |",
    ]
    for source, group in (("Synthetic Human", human), ("Synthetic Agent", agent)):
        cells = []
        for family in ("revision", "verification", "handoff"):
            family_group = [trace for trace in group if trace["family"] == family]
            cells.append(f"{sum(t['functional_pass'] for t in family_group)}/{len(family_group)}")
        lines.append(f"| {source} | {' | '.join(cells)} | {sum(t['functional_pass'] for t in group)}/{len(group)} |")
    lines.extend(
        [
            "",
            "这里故意展示两个重要边界。`SYN-H-P02-02`的四条有效修改全部得到采纳，但审核员没有发现第五个差异，最终事实正确率只有4/5；所以‘采纳率高’不能替代功能正确。`SYN-H-P03-02`的最终事实都正确，但接替者重复了检查点中已经完成的第一阶段；所以‘最终答案对’也不能替代过程闭环。",
            "",
            "## 四、H4过程画像",
            "",
            "比率均保留分子/分母；没有机会时写`N/A`，不记成0。恢复时间只作匹配描述，越快不自动代表越好。",
            "",
            "### 跨任务发言分布",
            "",
            "| 来源 | 消息轮次 | 各轨角色发言占比极差的均值 |",
            "| --- | ---: | ---: |",
            f"| Synthetic Human | {participation['synthetic_human']['turns']} | {participation['synthetic_human']['mean_dispersion']:.3f} |",
            f"| Synthetic Agent | {participation['synthetic_agent']['turns']} | {participation['synthetic_agent']['mean_dispersion']:.3f} |",
            "",
            "发言占比极差为每条轨迹中最高角色占比减最低角色占比。这里的0表示三名合成Agent各发一轮，并不自动优于Human；它也可能只是协议机械对称。",
            "",
            "### 修订任务",
            "",
            "| 来源 | 具体异议 | 有效纠正采纳 | 澄清 | 越界 |",
            "| --- | ---: | ---: | ---: | ---: |",
        ]
    )
    for source, label in (("synthetic_human", "Synthetic Human"), ("synthetic_agent", "Synthetic Agent")):
        metrics = h4[(source, "revision")]
        lines.append(
            f"| {label} | {ratio_text(metrics['specific_challenge_rate'])} | "
            f"{ratio_text(metrics['valid_correction_adoption_rate'])} | "
            f"{ratio_text(metrics['clarification_request_rate'])} | "
            f"{ratio_text(metrics['role_boundary_violation_rate'])} |"
        )
    lines.extend(
        [
            "",
            "### 核验任务",
            "",
            "| 来源 | 显式核验 | 已核验信息采用 | 必要澄清 | 未核验先行动 |",
            "| --- | ---: | ---: | ---: | ---: |",
        ]
    )
    for source, label in (("synthetic_human", "Synthetic Human"), ("synthetic_agent", "Synthetic Agent")):
        metrics = h4[(source, "verification")]
        lines.append(
            f"| {label} | {ratio_text(metrics['explicit_verification_rate'])} | "
            f"{ratio_text(metrics['verified_information_adoption_rate'])} | "
            f"{ratio_text(metrics['clarification_request_rate'])} | "
            f"{ratio_text(metrics['unverified_action_rate'])} |"
        )
    lines.extend(
        [
            "",
            "### 交接任务",
            "",
            "| 来源 | 交接完整 | 重复劳动 | 越界 | 恢复时间中位数 |",
            "| --- | ---: | ---: | ---: | ---: |",
        ]
    )
    for source, label in (("synthetic_human", "Synthetic Human"), ("synthetic_agent", "Synthetic Agent")):
        metrics = h4[(source, "handoff")]
        lines.append(
            f"| {label} | {ratio_text(metrics['handoff_completeness'])} | "
            f"{ratio_text(metrics['redundant_work_rate'])} | "
            f"{ratio_text(metrics['role_boundary_violation_rate'])} | "
            f"{metrics['recovery_time_seconds']:.0f}秒 |"
        )
    lines.extend(
        [
            "",
            "合成Agent明显更快、消息更少，但这不能被解释成团队过程更好。Human轨迹中的两次澄清恰好避免了未核验行动；如果把‘消息少、速度快’统一设成高分，会惩罚必要的人类协作。",
            "",
            "## 五、H1盲评演练",
            "",
            "下表只是验证统计出口。差值定义为Synthetic Human减Synthetic Agent，不能当作真实自然度差异。区间按8对匹配刺激的均值差、t(7)临界值计算；ICC(1)是平衡全评设计下的内部试采诊断，不是正式量表信度结论。",
            "",
            "| 维度 | Synthetic Human均值 | Synthetic Agent均值 | 合成差值及95%配对区间 | ICC(1) |",
            "| --- | ---: | ---: | ---: | ---: |",
        ]
    )
    labels = {
        "naturalness": "自然性",
        "agency": "主动担当",
        "social_responsiveness": "社会回应性",
        "role_continuity": "角色连续性",
    }
    for dimension in DIMENSIONS:
        human_mean = h1["synthetic_human"][dimension]
        agent_mean = h1["synthetic_agent"][dimension]
        mean_gap, lower, upper = paired_intervals[dimension]
        lines.append(
            f"| {labels[dimension]} | {human_mean:.2f} | {agent_mean:.2f} | "
            f"{mean_gap:+.2f} [{lower:+.2f}, {upper:+.2f}] | {reliability[dimension]:.3f} |"
        )
    lines.extend(
        [
            "",
            f"来源猜测正确率为{correct_guesses}/{len(ratings)}（{correct_guesses / len(ratings):.1%}），平均信心{mean_confidence:.2f}/5。若真人Pilot也明显高于机会水平，应先检查格式、长度、过度整齐用语和功能错误是否泄露来源，而不是立即解释自然度差异。",
            "",
            "## 六、双人编码一致性",
            "",
            "| 语义标签 | 候选事件 | 原始一致率 | Cohen's kappa | 是否触发修订 |",
            "| --- | ---: | ---: | ---: | --- |",
        ]
    )
    for row in coder_rows:
        lines.append(
            f"| `{row['label']}` | {row['events']} | {row['raw_agreement']:.3f} | "
            f"{row['cohens_kappa']:.3f} | {'是' if row['revision_triggered'] else '否'} |"
        )
    lines.extend(
        [
            "",
            "`correction_adopted`低于Codebook的0.80原始一致率和0.60 kappa门。模拟中，两位编码员主要争议‘结果已经修改，但采纳说明没有明确指回哪条审核意见’是否算采纳。若真实Pilot出现同类结果，应把‘实施’和‘可追溯承认’拆成两个标签，再只对Pilot重编码；不能在正式比较后根据来源差异改定义。",
            "",
            "共同排序的`accurate_tradeoff_statement`没有候选事件，因为Wave 2未运行，必须报告`N/A`。不能拿其他三类任务的消息填充它的分母。",
            "",
            "## 七、如果这是真实Pilot，应作出的决定",
            "",
            "结论应是`revise_before_next_wave`，而不是‘GAWorld不如真人’或‘Human自然度高0.x分’。具体动作是：",
            "",
            "1. 在页面上把‘检查点已完成阶段’与‘下一步允许动作’并列显示，并用负控确认接替者不能再次提交已完成阶段；",
            "2. 将`correction_adopted`拆成‘修改已实施’和‘采纳说明可追溯’两个可独立判断的标签，重新做双人编码；",
            "3. 在正式H1规则中事前决定理解检查失败如何处理，同时保留包含与排除两种敏感性结果；",
            "4. 对低ICC维度先做题目可观察性和措辞认知访谈；不能因为某题产生了不喜欢的来源差值而删题；",
            "5. 检查来源猜测是否由篇幅、模板化语言或功能错误泄露；展示归一化规则必须在正式来源比较前冻结；",
            "6. 远程三角色令牌、私有信息隔离、不可变事件日志和断线恢复仍需真实系统测试。合成数据不能替这些门签字；",
            "7. 共同排序继续保持阻塞，直到C1或等价协调路径完成规则校准。",
            "",
            "## 八、文件说明",
            "",
            "- `MANIFEST.json`：合成标识、零真实样本声明、设计规模和种子；",
            "- `trace_summary.csv`：每条Human/Agent占位轨迹的最小汇总；",
            "- `trace_metrics.json`：功能和H4的分子、分母及失败说明；",
            "- `h1_ratings.csv`：96份合成盲评记录，包含12题、来源猜测和理解检查；",
            "- `coder_agreement.csv`：双人语义编码诊断；",
            "- `REPORT.md`：本报告。",
            "",
            "重新生成命令：",
            "",
            "```powershell",
            "F:\\proj\\.venv_gaworld_eval\\Scripts\\python.exe human_validity\\h1_h4_v2\\synthetic_pilot\\simulate.py",
            "```",
        ]
    )
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--out",
        type=Path,
        default=Path(__file__).resolve().parent / "result_20260903",
    )
    args = parser.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)

    human = [{**trace, "source_kind": "synthetic_human", "r0_valid": True} for trace in HUMAN_TRACES]
    agent = [{**trace, "source_kind": "synthetic_agent", "r0_valid": True} for trace in make_agent_traces()]
    traces = human + agent
    ratings = generate_h1_ratings(traces)
    h4 = aggregate_h4(traces)
    h1, reliability, paired_intervals = aggregate_h1(ratings)

    coder_rows = []
    for label, pairs in CODER_PAIRS.items():
        agreement, kappa = cohen_kappa(pairs)
        coder_rows.append(
            {
                "label": label,
                "events": len(pairs),
                "raw_agreement": round(agreement, 6),
                "cohens_kappa": round(kappa, 6),
                "revision_triggered": agreement < 0.80 or kappa < 0.60,
            }
        )

    manifest = {
        "schema_version": 1,
        "experiment_id": "EXP-HF-H1H4-02-SYNTHETIC-DRY-RUN",
        "generated_for": "EXP-HF-H1H4-02",
        "generated_date": "2026-09-03",
        "synthetic": True,
        "real_participants": 0,
        "real_model_calls": 0,
        "api_cost": 0,
        "may_be_used_as_human_reference": False,
        "may_be_used_for_model_comparison": False,
        "formal_data_collection_allowed": False,
        "seed": SEED,
        "wave_1": {
            "synthetic_people": 12,
            "synthetic_teams": 4,
            "synthetic_human_traces": 8,
            "synthetic_agent_placeholders": 8,
            "synthetic_raters": 6,
            "synthetic_rating_records": len(ratings),
        },
        "wave_2": {"status": "not_simulated_dependency_blocked"},
        "generator": "../simulate.py",
        "inputs": [
            "../../PILOT_PLAN.yaml",
            "../../PREREGISTRATION.yaml",
            "../../H4_CODEBOOK.yaml",
            "../../tasks/*/task_card.yaml",
            "../../tasks/*/scoring.yaml",
        ],
    }
    (args.out / "MANIFEST.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    (args.out / "trace_metrics.json").write_text(
        json.dumps(traces, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    summary_rows = [
        {
            "trace_id": trace["trace_id"],
            "source_kind": trace["source_kind"],
            "unit_id": trace["unit_id"],
            "surface_id": trace["surface_id"],
            "condition": trace["condition"],
            "family": trace["family"],
            "r0_valid": int(trace["r0_valid"]),
            "completed": 1,
            "functional_pass": int(trace["functional_pass"]),
            "completion_seconds": trace["completion_seconds"],
            "role_1_turns": trace["turns"][0],
            "role_2_turns": trace["turns"][1],
            "role_3_turns": trace["turns"][2],
            "accepted_actions": trace["accepted_actions"],
            "role_boundary_violations": trace["role_boundary_violations"],
            "idempotent_retries": trace["idempotent_retries"],
            "note": trace["note"],
        }
        for trace in traces
    ]
    write_csv(args.out / "trace_summary.csv", summary_rows, list(summary_rows[0]))
    write_csv(args.out / "h1_ratings.csv", ratings, list(ratings[0]))
    write_csv(args.out / "coder_agreement.csv", coder_rows, list(coder_rows[0]))
    report = render_report(traces, ratings, h4, h1, reliability, paired_intervals, coder_rows)
    (args.out / "REPORT.md").write_text(report, encoding="utf-8")
    print(args.out)
    print(f"traces={len(traces)} ratings={len(ratings)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
