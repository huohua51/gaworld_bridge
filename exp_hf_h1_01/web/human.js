let TASKS = {};

async function main() {
  TASKS = await (await fetch("/human-protocols/tasks.json")).json();
  const construct = document.getElementById("construct");
  const task = document.getElementById("task");
  const variant = document.getElementById("variant");
  function fillTasks() {
    task.innerHTML = "";
    for (const item of TASKS[construct.value]) {
      const opt = document.createElement("option");
      opt.value = item.task_id;
      opt.textContent = item.label;
      task.appendChild(opt);
    }
    draw();
  }
  construct.onchange = fillTasks;
  task.onchange = draw;
  variant.onchange = draw;
  fillTasks();
  document.getElementById("save").onclick = save;
}

function currentTask() {
  return TASKS[document.getElementById("construct").value].find((t) => t.task_id === document.getElementById("task").value);
}

function draw() {
  const c = document.getElementById("construct").value;
  const v = document.getElementById("variant").value;
  const spec = currentTask();
  const box = document.getElementById("workspace");
  document.getElementById("brief").textContent = spec.label + (spec.brief || spec.output_rule || spec.rule || "");
  if (c === "T3") box.innerHTML = t3Form(spec, v);
  if (c === "I1") box.innerHTML = i1Form(spec, v);
  if (c === "L1") box.innerHTML = l1Form(spec, v);
}

function t3Form(spec, v) {
  const req = v === "A" ? spec.A_required : spec.B_required;
  return `
    <article class="turn"><div class="role">起草人</div><p class="kind">可见：公开说明。看不到本轮私有标准。公开值 ${esc(spec.symbol)} = ${spec.public_value}。</p>
      <p>${esc(spec.brief)}</p>
      <textarea id="draft">${esc(spec.draft_template)}</textarea></article>
    <article class="turn"><div class="role">审核员</div><p class="kind">可见：上面的草稿 + 本轮标准 ${esc(spec.symbol)} = ${req}。只输出 JSON。</p>
      <textarea id="review">${esc(JSON.stringify({ decision: "keep 或 update", evidence: { path: spec.symbol, observed: "填草稿中的值", required: req }, required_changes: [] }, null, 2))}</textarea></article>
    <article class="turn"><div class="role">执行人</div><p class="kind">可见：草稿与审核意见。keep 则确认原文，update 则只改 required_changes。</p>
      <textarea id="after"></textarea></article>`;
}

function i1Form(spec, v) {
  const signals = v === "A" ? spec.signals_A : spec.signals_B;
  return `
    <article class="turn"><div class="role">观察员</div><p class="kind">把两个来源原样发出，不判断谁可信。</p>
      <textarea id="obs">${esc(JSON.stringify(signals, null, 2))}</textarea></article>
    <article class="turn"><div class="role">核验员</div><p class="kind">可信来源：${esc(spec.trusted_source_id)}。不能提交最终动作。</p>
      <textarea id="ver">${esc(JSON.stringify({ verified_state: "", source_id: "", state_version: "" }, null, 2))}</textarea></article>
    <article class="turn"><div class="role">调度员</div><p class="kind">${esc(spec.rule)} 不能读可信表。</p>
      <textarea id="act">${esc(JSON.stringify({ action: spec.action, value: "", adopted_state_version: "" }, null, 2))}</textarea></article>`;
}

function l1Form(spec, v) {
  const s = spec.steps;
  const m = spec.materials;
  const interrupt = v === "B" ? `<article class="turn"><div class="role">执行者甲</div><p>执行者甲在第一里程碑后不可用。</p></article>` : "";
  const successor = v === "B" ? "执行者乙" : "执行者甲";
  const s1 = s[0].id;
  const s2 = s[1].id;
  const s3 = s[2].id;
  return `
    <p class="kind">${esc(spec.output_rule)}</p>
    <article class="turn"><div class="role">执行者甲 · 第一步</div><p class="kind">材料：${esc(JSON.stringify(m[s1]))}</p><textarea id="step1">${esc(JSON.stringify({ worker_id: "worker_a", step_id: s1, output: {} }, null, 2))}</textarea></article>
    <article class="turn"><div class="role">执行者甲 · 检查点</div><p class="kind">不要填写版本号，由平台盖章。</p><textarea id="ckpt">${esc(JSON.stringify({ worker_id: "worker_a", completed_steps: [], outputs: {} }, null, 2))}</textarea></article>
    <article class="turn"><div class="role">协调员</div><p class="kind">不能执行具体步骤，不能给出剩余步骤的正确答案。</p><textarea id="hand">${esc(JSON.stringify({ successor: "", checkpoint_version: "ckpt-001", completed_steps: [], resume_step: "", remaining_steps: [] }, null, 2))}</textarea></article>
    ${interrupt}
    <article class="turn"><div class="role">${successor} · 恢复</div><textarea id="resume">${esc(JSON.stringify({ worker_id: "", checkpoint_version: "ckpt-001", resume_step: "" }, null, 2))}</textarea></article>
    <article class="turn"><div class="role">${successor} · 第二步</div><p class="kind">材料：${esc(JSON.stringify(m[s2] || {}))}</p><textarea id="step2">${esc(JSON.stringify({ worker_id: "", step_id: s2, output: {} }, null, 2))}</textarea></article>
    <article class="turn"><div class="role">${successor} · 第三步</div><p class="kind">材料：${esc(JSON.stringify(m[s3] || {}))}</p><textarea id="step3">${esc(JSON.stringify({ worker_id: "", step_id: s3, output: {} }, null, 2))}</textarea></article>`;
}

async function save() {
  const c = document.getElementById("construct").value;
  const spec = currentTask();
  const v = document.getElementById("variant").value;
  const turns = collect(c);
  const body = {
    construct: c,
    task_id: spec.task_id,
    variant_code: v,
    task_label: spec.label,
    turns,
  };
  const res = await fetch("/api/human-trace", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });
  const out = await res.json();
  document.getElementById("status").textContent = res.ok ? `已保存 ${out.path}` : (out.error || "失败");
}

function collect(c) {
  const val = (id) => document.getElementById(id).value;
  if (c === "T3") {
    return [
      { t: 1, role: "起草人", kind: "produce", body: val("draft"), visible_to_role: "公开任务说明" },
      { t: 2, role: "审核员", kind: "decide", body: val("review"), visible_to_role: "草稿与本轮审核可见标准" },
      { t: 3, role: "执行人", kind: "apply", body: val("after"), visible_to_role: "草稿与审核意见" },
    ];
  }
  if (c === "I1") {
    return [
      { t: 1, role: "观察员", kind: "report", body: val("obs"), visible_to_role: "两个来源的现场报告" },
      { t: 2, role: "核验员", kind: "verify", body: val("ver"), visible_to_role: "原始报告 + 私有可信来源表" },
      { t: 3, role: "调度员", kind: "act", body: val("act"), visible_to_role: "已核实状态与动作规则" },
    ];
  }
  const turns = [
    { t: 1, role: "执行者甲", kind: "produce", body: val("step1"), visible_to_role: "第一步材料" },
    { t: 2, role: "执行者甲", kind: "checkpoint", body: val("ckpt"), visible_to_role: "已完成第一步" },
    { t: 3, role: "协调员", kind: "handoff", body: val("hand"), visible_to_role: "检查点" },
  ];
  let t = 4;
  if (document.getElementById("variant").value === "B") {
    turns.push({ t, role: "执行者甲", kind: "unavailable", body: "执行者甲在第一里程碑后不可用。", visible_to_role: "现场状态" });
    t += 1;
  }
  const suc = document.getElementById("variant").value === "B" ? "执行者乙" : "执行者甲";
  turns.push({ t, role: suc, kind: "resume", body: val("resume"), visible_to_role: "检查点与接替指令" });
  t += 1;
  turns.push({ t, role: suc, kind: "produce", body: val("step2"), visible_to_role: "当前步骤材料" });
  t += 1;
  turns.push({ t, role: suc, kind: "produce", body: val("step3"), visible_to_role: "最后一步材料" });
  return turns;
}

function esc(v) {
  return String(v ?? "").replace(/[&<>"']/g, (ch) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[ch]));
}

main();
