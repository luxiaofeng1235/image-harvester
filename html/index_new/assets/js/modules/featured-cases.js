const ANIMATION_CLASSES = [
  "anim-1",
  "anim-2",
  "anim-3",
  "anim-4",
  "anim-5",
  "anim-6"
];

export function initFeaturedCases(root, brandEl, titleCnEl, titleEnEl, config) {
  if (!root || !config || !Array.isArray(config.items)) {
    return;
  }

  if (brandEl && config.brandTitle) brandEl.textContent = config.brandTitle;
  if (titleCnEl && config.cnTitle) titleCnEl.textContent = config.cnTitle;
  if (titleEnEl && config.enTitle) titleEnEl.textContent = config.enTitle;

  const stepSeconds = Number(config.animationStepSeconds) || 3;
  root.innerHTML = "";

  config.items.forEach((item, index) => {
    const li = document.createElement("li");
    li.className = `featured-case-item is-animating ${ANIMATION_CLASSES[index % ANIMATION_CLASSES.length]}`;
    li.style.animationDelay = `${index * stepSeconds}s`;

    const link = document.createElement("a");
    link.className = "featured-link";
    link.href = item.link || "#";

    const img = document.createElement("img");
    img.src = item.image;
    img.alt = item.name || "精品案例";
    img.loading = index < 2 ? "eager" : "lazy";

    const label = document.createElement("span");
    label.className = "featured-label";
    label.textContent = item.name || "";

    link.appendChild(img);
    link.appendChild(label);
    li.appendChild(link);
    root.appendChild(li);
  });
}
