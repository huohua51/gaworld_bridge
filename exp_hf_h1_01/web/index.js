async function main() {
  const response = await fetch("/api/status");
  if (!response.ok) throw new Error(`HTTP ${response.status}`);
  const data = await response.json();
  document.getElementById("human-count").textContent = `${data.n_human_collected || 0}/${data.n_human_slots || 18}`;
  document.getElementById("stimulus-count").textContent = String((data.stimuli || []).length);
}

main().catch((error) => {
  document.getElementById("status").textContent = `状态读取失败：${error.message}`;
});
