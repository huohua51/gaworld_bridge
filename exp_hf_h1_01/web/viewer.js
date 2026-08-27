async function main() {
  const response = await fetch("/api/stimuli");
  const index = await response.json();
  const select = document.getElementById("sid");
  for (const id of index.stimuli || []) {
    const option = document.createElement("option");
    option.value = id;
    option.textContent = id;
    select.appendChild(option);
  }
  const box = document.getElementById("trace");
  async function show() {
    if (!select.value) {
      box.innerHTML = "<p>匿名池为空，需先生成 Agent 刺激。</p>";
      return;
    }
    const itemResponse = await fetch(`/api/display/${encodeURIComponent(select.value)}`);
    if (!itemResponse.ok) throw new Error(`HTTP ${itemResponse.status}`);
    renderTrace(box, await itemResponse.json());
  }
  select.addEventListener("change", () => show().catch(reportError));
  await show();
}

function renderTrace(element, data) {
  const turns = (data.turns || []).map((turn) => {
    const visible = turn.visible_to_role ? `<p class="kind">可见信息：${esc(turn.visible_to_role)}</p>` : "";
    return `<article class="turn"><div class="role">${esc(turn.role)} · ${esc(turn.kind)}</div>${visible}<pre>${esc(turn.body)}</pre></article>`;
  }).join("");
  element.innerHTML = `<p><strong>${esc(data.task_label)}</strong> · ${esc(data.construct)} · 变体 ${esc(data.variant_code)}</p><p class="kind">角色：${(data.roles || []).map(esc).join(" / ")}</p>${turns}`;
}

function reportError(error) { document.getElementById("trace").innerHTML = `<p class="status">读取失败：${esc(error.message)}</p>`; }
function esc(value) {
  return String(value ?? "").replace(/[&<>"']/g, (char) => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;",
  }[char]));
}
main().catch(reportError);
