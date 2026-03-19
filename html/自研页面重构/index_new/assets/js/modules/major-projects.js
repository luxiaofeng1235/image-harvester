export function initMajorProjects(root, titleCnEl, titleEnEl, config) {
  if (!root || !config || !Array.isArray(config.items)) {
    return;
  }

  if (titleCnEl && config.cnTitle) titleCnEl.textContent = config.cnTitle;
  if (titleEnEl && config.enTitle) titleEnEl.textContent = config.enTitle;

  root.innerHTML = "";

  config.items.forEach((item) => {
    const li = document.createElement("li");
    li.className = "major-project-item";

    const link = document.createElement("a");
    link.className = "major-link";
    link.href = item.link || "#";

    const img = document.createElement("img");
    img.src = item.image;
    img.alt = item.name || "主要项目";
    img.loading = "lazy";

    const label = document.createElement("span");
    label.className = "major-label";
    label.textContent = item.name || "";

    link.appendChild(img);
    link.appendChild(label);
    li.appendChild(link);
    root.appendChild(li);
  });
}
