async function main() {
  const [indexResponse, rubricResponse] = await Promise.all([
    fetch("/api/stimuli"), fetch("/rubric.json"),
  ]);
  const index = await indexResponse.json();
  const rubric = await rubricResponse.json();
  const select = document.getElementById("sid");
  const stimuli = index.stimuli || [];
  document.getElementById("progress").textContent =
    `匿名池 ${stimuli.length} 条：Agent ${index.n_agent || 0}，Human ${index.n_human_collected || 0}/${index.n_human_slots || 18}`;
  for (const id of stimuli) {
    const option = document.createElement("option");
    option.value = id;
    option.textContent = id;
    select.appendChild(option);
  }
  const items = document.getElementById("items");
  items.innerHTML = rubric.map((item) => {
    const radios = [1, 2, 3, 4, 5, 6, 7]
      .map((n) => `<label><input type="radio" name="${item.id}" value="${n}" /> ${n}</label>`).join("");
    return `<article class="turn"><div class="role">${item.id} · ${item.dimension}</div><p>${item.prompt}</p><div class="scale">${radios}</div></article>`;
  }).join("");
  const box = document.getElementById("trace");
  async function show() {
    clearScores(items);
    document.getElementById("status").textContent = "";
    if (!select.value) {
      box.innerHTML = "<p>匿名池为空，需先生成 Agent 刺激。</p>";
      document.getElementById("save").disabled = true;
      return;
    }
    document.getElementById("save").disabled = false;
    const response = await fetch(`/api/display/${encodeURIComponent(select.value)}`);
    if (!response.ok) throw new Error(`刺激读取失败：HTTP ${response.status}`);
    box.innerHTML = render(await response.json());
  }
  select.addEventListener("change", () => show().catch(reportError));
  await show();
  document.getElementById("save").onclick = async () => {
    const scores = {};
    for (const item of rubric) {
      const picked = items.querySelector(`input[name="${item.id}"]:checked`);
      if (!picked) {
        reportError(new Error(`未完成 ${item.id}`));
        return;
      }
      scores[item.id] = Number(picked.value);
    }
    const body = {
      stimulus_id: select.value,
      rater_id: document.getElementById("rater").value.trim(),
      scores,
      comment: document.getElementById("comment").value.trim(),
    };
    if (!body.rater_id) {
      reportError(new Error("请填写匿名评委代号"));
      return;
    }
    const response = await fetch("/api/rating", {
      method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body),
    });
    const result = await response.json();
    document.getElementById("status").textContent = response.ok ? "评分已保存。" : `保存失败：${result.error || "unknown_error"}`;
    if (response.ok) document.getElementById("save").disabled = true;
  };
}

function clearScores(container) {
  for (const input of container.querySelectorAll("input[type=radio]")) input.checked = false;
}

function render(data) {
  const turns = (data.turns || []).map((turn) => {
    const visible = turn.visible_to_role ? `<p class="kind">可见信息：${esc(turn.visible_to_role)}</p>` : "";
    return `<article class="turn"><div class="role">${esc(turn.role)} · ${esc(turn.kind)}</div>${visible}<pre>${esc(turn.body)}</pre></article>`;
  }).join("");
  return `<p><strong>${esc(data.task_label)}</strong> · ${esc(data.construct)} · 变体 ${esc(data.variant_code)}</p>${turns}`;
}

function reportError(error) { document.getElementById("status").textContent = error.message; }
function esc(value) {
  return String(value ?? "").replace(/[&<>"']/g, (char) => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;",
  }[char]));
}
main().catch(reportError);
