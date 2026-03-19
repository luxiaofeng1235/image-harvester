export function initQuickCases(root, quickCasesConfig, lightboxApi) {
  if (!root || !quickCasesConfig || !Array.isArray(quickCasesConfig.items)) {
    return;
  }

  const items = quickCasesConfig.items;
  root.innerHTML = "";

  items.forEach((item, index) => {
    const li = document.createElement("li");
    li.className = "quick-case-item";

    const link = document.createElement("button");
    link.type = "button";
    link.className = "quick-case-link";
    link.setAttribute("aria-label", item.name || "查看图片");
    link.dataset.index = String(index);

    const img = document.createElement("img");
    img.src = item.thumbUrl;
    img.alt = item.name;
    img.loading = index < 2 ? "eager" : "lazy";

    const label = document.createElement("span");
    label.className = "quick-case-label";
    label.textContent = item.name;

    link.appendChild(img);
    link.appendChild(label);
    li.appendChild(link);
    root.appendChild(li);
  });

  root.addEventListener("click", (event) => {
    const trigger = event.target instanceof Element ? event.target.closest(".quick-case-link") : null;
    if (!trigger) return;

    event.preventDefault();
    const index = Number(trigger.dataset.index || 0);
    if (lightboxApi && typeof lightboxApi.open === "function") {
      lightboxApi.open(items, index, trigger);
    }
  });
}
