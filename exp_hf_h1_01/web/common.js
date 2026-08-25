function renderTrace(el, data) {
  if (!data) {
    el.innerHTML = "";
    return;
  }
  const turns = (data.turns || []).map((turn) => {
    const vis = turn.visible_to_role ? `<p class="kind">可见信息：${escapeHtml(turn.visible_to_role)}</p>` : "";
    return `<article class="turn"><div class="role">${escapeHtml(turn.role)} · ${escapeHtml(turn.kind)}</div>${vis}<pre>${escapeHtml(turn.body)}</pre></article>`;
  }).join("");
  el.innerHTML = `<p><strong>${escapeHtml(data.task_label)}</strong> · ${escapeHtml(data.construct)} · 变体 ${escapeHtml(data.variant_code)}</p>
    <p class="kind">角色：${(data.roles || []).map(escapeHtml).join(" / ")}</p>${turns}`;
}

function escapeHtml(value) {
  return String(value ?? "").replace(/[&<>"']/g, (ch) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[ch]));
}

async function loadIndex() {
  const res = await fetch("/api/stimuli");
  return res.json();
}
