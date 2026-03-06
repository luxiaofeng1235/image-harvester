export function initAboutSection(sectionEl, nodes, config) {
  if (!sectionEl || !config || !nodes) {
    return;
  }

  const {
    brandEl,
    titleCnEl,
    titleEnEl,
    headlineEl,
    paragraphsEl,
    closingEl
  } = nodes;

  if (config.background) {
    sectionEl.style.backgroundImage = `url(${config.background})`;
  }

  if (brandEl && config.brandTitle) brandEl.textContent = config.brandTitle;
  if (titleCnEl && config.cnTitle) titleCnEl.textContent = config.cnTitle;
  if (titleEnEl && config.enTitle) titleEnEl.textContent = config.enTitle;
  if (headlineEl && config.headline) headlineEl.textContent = config.headline;

  if (paragraphsEl && Array.isArray(config.paragraphs)) {
    paragraphsEl.innerHTML = "";
    config.paragraphs.forEach((text) => {
      const p = document.createElement("p");
      p.textContent = text;
      paragraphsEl.appendChild(p);
    });
  }

  if (closingEl && config.closing) {
    closingEl.textContent = config.closing;
  }
}
