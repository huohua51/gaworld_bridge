async function main() {
  const index = await (await fetch("/api/stimuli")).json();
  const sel = document.getElementById("sid");
  index.stimuli.forEach((id) => {
    const opt = document.createElement("option");
    opt.value = id;
    opt.textContent = id;
    sel.appendChild(opt);
  });
  const box = document.getElementById("trace");
  async function show() {
    const data = await (await fetch(`/api/display/${sel.value}`)).json();
    renderTrace(box, data);
  }
  sel.addEventListener("change", show);
  await show();
}

function renderTrace(el, data) {
  const turns = (data.turns || []).map((turn) => {
    const vis = turn.visible_to_role ? `<p class="kind">可见信息：${esc(turn.visible_to_role)}</p>` : "";
    return `<article class="turn"><div class="role">${esc(turn.role)} · ${esc(turn.kind)}</div>${vis}<pre>${esc(turn.body)}</pre></article>`;
  }).join("");
  el.innerHTML = `<p><strong>${esc(data.task_label)}</strong> · ${esc(data.construct)} · 变体 ${esc(data.variant_code)}</p>
    <p class="kind">角色：${(data.roles || []).map(esc).join(" / ")}</p>${turns}`;
}
function esc(v) {
  return String(v ?? "").replace(/[&<>"']/g, (ch) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[ch]));
}
main();
