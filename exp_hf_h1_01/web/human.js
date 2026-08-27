let TASKS = {};
let SLOTS = [];
let slotStartedAt = Date.now();

const ROLES = {
  T3: ["起草人", "审核员", "执行人"],
  I1: ["观察员", "核验员", "调度员"],
  L1: ["执行者甲", "协调员", "执行者乙"],
};

async function main() {
  const [tasksResponse, slotsResponse] = await Promise.all([
    fetch("/human-protocols/tasks.json"),
    fetch("/api/human-slots"),
  ]);
  TASKS = await tasksResponse.json();
  updateSlots(await slotsResponse.json());
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

function updateSlots(data) {
  SLOTS = data.slots || [];
  document.getElementById("progress").textContent =
    `Human Trace 进度：${data.n_human_collected || 0}/${data.n_human_slots || 18}（试采，不计正式 H1）`;
}

function currentTask() {
  const construct = document.getElementById("construct").value;
  const taskId = document.getElementById("task").value;
  return TASKS[construct].find((item) => item.task_id === taskId);
}

function currentSlot() {
  const construct = document.getElementById("construct").value;
  const taskId = document.getElementById("task").value;
  const variant = document.getElementById("variant").value;
  return SLOTS.find((slot) =>
    slot.construct === construct && slot.task_id === taskId && slot.variant_code === variant
  );
}

function draw() {
  const construct = document.getElementById("construct").value;
  const variant = document.getElementById("variant").value;
  const spec = currentTask();
  if (!spec) return;
  document.getElementById("brief").textContent = `${spec.label}：${spec.brief || spec.output_rule || spec.rule || ""}`;
  document.getElementById("protocol-link").href = `/human-protocols/${construct.toLowerCase()}.md`;
  drawAssignments(construct);
  const box = document.getElementById("workspace");
  if (construct === "T3") box.innerHTML = t3Form(spec, variant);
  if (construct === "I1") box.innerHTML = i1Form(spec, variant);
  if (construct === "L1") box.innerHTML = l1Form(spec, variant);
  slotStartedAt = Date.now();
  document.getElementById("status").textContent = "";
  updateSlotStatus();
}

function drawAssignments(construct) {
  const container = document.getElementById("role-assignments");
  container.innerHTML = ROLES[construct].map((role, index) => `
    <label>${esc(role)}参与者代号
      <input class="participant-code" data-role="${esc(role)}" maxlength="40" placeholder="例如 p-${index + 1}" />
    </label>`).join("");
}

function updateSlotStatus() {
  const slot = currentSlot();
  const collected = slot && slot.human_status === "collected";
  document.getElementById("slot-status").textContent = collected
    ? "该槽位已经采集并锁定，请选择其他槽位。"
    : "该槽位尚未采集。保存后默认不可覆盖。";
  document.getElementById("save").disabled = Boolean(collected);
}

function t3Form(spec, variant) {
  const required = variant === "A" ? spec.A_required : spec.B_required;
  const review = {
    decision: "keep 或 update",
    evidence: { path: spec.symbol, observed: "填写草稿中的值", required },
    required_changes: [],
  };
  return `
    <article class="turn"><div class="role">起草人</div><p class="kind">可见：公开说明。看不到本轮私有标准。公开值 ${esc(spec.symbol)} = ${spec.public_value}。</p>
      <p>${esc(spec.brief)}</p><textarea id="draft">${esc(spec.draft_template)}</textarea></article>
    <article class="turn"><div class="role">审核员</div><p class="kind">可见：上面的草稿 + 本轮标准 ${esc(spec.symbol)} = ${required}。只输出 JSON。</p>
      <textarea id="review">${esc(JSON.stringify(review, null, 2))}</textarea></article>
    <article class="turn"><div class="role">执行人</div><p class="kind">可见：草稿与审核意见。keep 则原样确认，update 则只实施 required_changes。</p>
      <textarea id="after">${esc(spec.draft_template)}</textarea></article>`;
}

function i1Form(spec, variant) {
  const signals = variant === "A" ? spec.signals_A : spec.signals_B;
  const state = spec[variant];
  return `
    <article class="turn"><div class="role">观察员</div><p class="kind">把两个来源原样发出，不判断谁可信。</p>
      <textarea id="obs">${esc(JSON.stringify(signals, null, 2))}</textarea></article>
    <article class="turn"><div class="role">核验员</div><p class="kind">可信来源：${esc(spec.trusted_source_id)}。本轮信息版本：${esc(state.version)}。不能提交最终动作。</p>
      <textarea id="ver">${esc(JSON.stringify({ verified_state: "", source_id: "", state_version: state.version }, null, 2))}</textarea></article>
    <article class="turn"><div class="role">调度员</div><p class="kind">${esc(spec.rule)} 不能读取可信来源表。</p>
      <textarea id="act">${esc(JSON.stringify({ action: spec.action, value: "", adopted_state_version: state.version }, null, 2))}</textarea></article>`;
}

function l1Form(spec, variant) {
  const steps = spec.steps;
  const materials = spec.materials;
  const interrupt = variant === "B" ? `<article class="turn"><div class="role">执行者甲</div><p>执行者甲在第一里程碑后不可用。</p></article>` : "";
  const successor = variant === "B" ? "执行者乙" : "执行者甲";
  const [step1, step2, step3] = steps.map((step) => step.id);
  return `
    <p class="kind">${esc(spec.output_rule)}</p>
    <article class="turn"><div class="role">执行者甲 · 第一步</div><p class="kind">材料：${esc(JSON.stringify(materials[step1]))}</p><textarea id="step1">${esc(JSON.stringify({ worker_id: "worker_a", step_id: step1, output: {} }, null, 2))}</textarea></article>
    <article class="turn"><div class="role">执行者甲 · 检查点</div><p class="kind">不要填写版本号，由平台盖章。</p><textarea id="ckpt">${esc(JSON.stringify({ worker_id: "worker_a", completed_steps: [], outputs: {} }, null, 2))}</textarea></article>
    <article class="turn"><div class="role">协调员</div><p class="kind">不能执行具体步骤，不能给出剩余步骤的正确答案。</p><textarea id="hand">${esc(JSON.stringify({ successor: "", checkpoint_version: "ckpt-001", completed_steps: [], resume_step: "", remaining_steps: [] }, null, 2))}</textarea></article>
    ${interrupt}
    <article class="turn"><div class="role">${successor} · 恢复</div><textarea id="resume">${esc(JSON.stringify({ worker_id: "", checkpoint_version: "ckpt-001", resume_step: "" }, null, 2))}</textarea></article>
    <article class="turn"><div class="role">${successor} · 第二步</div><p class="kind">材料：${esc(JSON.stringify(materials[step2] || {}))}</p><textarea id="step2">${esc(JSON.stringify({ worker_id: "", step_id: step2, output: {} }, null, 2))}</textarea></article>
    <article class="turn"><div class="role">${successor} · 第三步</div><p class="kind">材料：${esc(JSON.stringify(materials[step3] || {}))}</p><textarea id="step3">${esc(JSON.stringify({ worker_id: "", step_id: step3, output: {} }, null, 2))}</textarea></article>`;
}

async function save() {
  const construct = document.getElementById("construct").value;
  const spec = currentTask();
  const variant = document.getElementById("variant").value;
  const roleAssignments = {};
  for (const input of document.querySelectorAll(".participant-code")) {
    roleAssignments[input.dataset.role] = input.value.trim();
  }
  const body = {
    construct,
    task_id: spec.task_id,
    variant_code: variant,
    collection_mode: document.getElementById("collection-mode").value,
    team_code: document.getElementById("team-code").value.trim(),
    session_code: document.getElementById("session-code").value.trim(),
    role_assignments: roleAssignments,
    consent_confirmed: document.getElementById("consent").checked,
    started_at: new Date(slotStartedAt).toISOString(),
    duration_ms: Date.now() - slotStartedAt,
    protocol_deviations: document.getElementById("deviations").value.trim(),
    turns: collect(construct),
  };
  if (!body.consent_confirmed) {
    setStatus("请先确认知情同意和匿名要求。");
    return;
  }
  if (!window.confirm(`确认保存 ${construct} / ${spec.label} / 变体 ${variant}？保存后不可覆盖。`)) return;
  const response = await fetch("/api/human-trace", {
    method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body),
  });
  const result = await response.json();
  if (!response.ok) {
    setStatus(`保存失败：${result.error || "unknown_error"}`);
    return;
  }
  setStatus(`已保存。进度 ${result.n_human_collected}/${result.n_human_slots}`);
  updateSlots(await (await fetch("/api/human-slots")).json());
  updateSlotStatus();
}

function setStatus(message) { document.getElementById("status").textContent = message; }

function collect(construct) {
  const value = (id) => document.getElementById(id).value;
  if (construct === "T3") return [
    { t: 1, role: "起草人", kind: "produce", body: value("draft") },
    { t: 2, role: "审核员", kind: "decide", body: value("review") },
    { t: 3, role: "执行人", kind: "apply", body: value("after") },
  ];
  if (construct === "I1") return [
    { t: 1, role: "观察员", kind: "report", body: value("obs") },
    { t: 2, role: "核验员", kind: "verify", body: value("ver") },
    { t: 3, role: "调度员", kind: "act", body: value("act") },
  ];
  const turns = [
    { t: 1, role: "执行者甲", kind: "produce", body: value("step1") },
    { t: 2, role: "执行者甲", kind: "checkpoint", body: value("ckpt") },
    { t: 3, role: "协调员", kind: "handoff", body: value("hand") },
  ];
  let t = 4;
  const variant = document.getElementById("variant").value;
  if (variant === "B") {
    turns.push({ t, role: "执行者甲", kind: "unavailable", body: "执行者甲在第一里程碑后不可用。" });
    t += 1;
  }
  const successor = variant === "B" ? "执行者乙" : "执行者甲";
  turns.push({ t, role: successor, kind: "resume", body: value("resume") });
  turns.push({ t: t + 1, role: successor, kind: "produce", body: value("step2") });
  turns.push({ t: t + 2, role: successor, kind: "produce", body: value("step3") });
  return turns;
}

function esc(value) {
  return String(value ?? "").replace(/[&<>"']/g, (char) => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;",
  }[char]));
}

main().catch((error) => setStatus(`页面初始化失败：${error.message}`));
