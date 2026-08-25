async function main() {
  const index = await (await fetch("/api/stimuli")).json();
  const rubric = await (await fetch("/rubric.json")).json();
  const sel = document.getElementById("sid");
  index.stimuli.forEach((id) => {
    const opt = document.createElement("option");
    opt.value = id;
    opt.textContent = id;
    sel.appendChild(opt);
  });
  const items = document.getElementById("items");
  items.innerHTML = rubric.map((item) => {
    const radios = [1, 2, 3, 4, 5, 6, 7].map((n) => `<label><input type="radio" name="${item.id}" value="${n}" /> ${n}</label>`).join("");
    return `<article class="turn"><div class="role">${item.id} · ${item.dimension}</div><p>${item.prompt}</p><div class="scale">${radios}</div></article>`;
  }).join("");
  const box = document.getElementById("trace");
  async function show() {
    const data = await (await fetch(`/api/display/${sel.value}`)).json();
    box.innerHTML = render(data);
  }
  sel.addEventListener("change", show);
  await show();
  document.getElementById("save").onclick = async () => {
    const scores = {};
    for (const item of rubric) {
      const picked = items.querySelector(`input[name="${item.id}"]:checked`);
      if (!picked) {
        document.getElementById("status").textContent = `未完成 ${item.id}`;
        return;
      }
      scores[item.id] = Number(picked.value);
    }
    const body = {
      stimulus_id: sel.value,
      rater_id: document.getElementById("rater").value.trim(),
      scores,
    };
    if (!body.rater_id) {
      document.getElementById("status").textContent = "请填写评委代号";
      return;
    }
    const res = await fetch("/api/rating", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });
    const out = await res.json();
    document.getElementById("status").textContent = res.ok ? `已保存 ${out.path}` : (out.error || "失败");
  };
}

function render(data) {
  const turns = (data.turns || []).map((turn) => {
    const vis = turn.visible_to_role ? `<p class="kind">可见信息：${esc(turn.visible_to_role)}</p>` : "";
    return `<article class="turn"><div class="role">${esc(turn.role)} · ${esc(turn.kind)}</div>${vis}<pre>${esc(turn.body)}</pre></article>`;
  }).join("");
  return `<p><strong>${esc(data.task_label)}</strong> · ${esc(data.construct)} · 变体 ${esc(data.variant_code)}</p>${turns}`;
}
function esc(v) {
  return String(v ?? "").replace(/[&<>"']/g, (ch) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[ch]));
}
main();
