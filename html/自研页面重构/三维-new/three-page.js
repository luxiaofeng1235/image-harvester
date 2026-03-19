import { initSharedSlider } from "../plugin/shared-slider.js";

var root = document.getElementById("zr-3dnew-root");

if (root) {
  initStandalonePreview();
  initPage();
}

async function initPage() {
  try {
    var config = await loadConfig(root.getAttribute("data-config"));
    renderSections(config);
    initSharedSlider(document.getElementById("zr-3dnew-slider"), config.slider || {});
  } catch (error) {
    console.error("Failed to render three-dimensional page.", error);
  }
}

function initStandalonePreview() {
  if (!document.body || root.parentElement !== document.body) {
    return;
  }

  document.body.style.margin = "0";
  document.body.style.backgroundColor = "#ffffff";
}

async function loadConfig(url) {
  var response = await fetch(url, { cache: "no-store" });
  if (!response.ok) {
    throw new Error("Config request failed: " + response.status);
  }
  return response.json();
}

function renderSections(config) {
  var container = document.getElementById("zr-3dnew-content");
  if (!container) {
    return;
  }

  container.innerHTML = "";
  container.style.height = String(config.contentHeight || 1843) + "px";

  (config.sections || []).forEach(function (sectionConfig) {
    container.appendChild(createSection(sectionConfig));
  });
}

function createSection(sectionConfig) {
  var section = document.createElement("section");
  section.className = "zr-3dnew-section";
  section.setAttribute("data-section-id", sectionConfig.id || "");
  section.style.top = String(sectionConfig.top || 0) + "px";
  section.style.height = String(sectionConfig.height || 0) + "px";

  if (sectionConfig.label) {
    section.appendChild(createLabel(sectionConfig.label));
  }

  if (sectionConfig.guide) {
    section.appendChild(createGuide(sectionConfig.guide));
  }

  if (sectionConfig.button) {
    section.appendChild(createButton(sectionConfig.button));
  }

  (sectionConfig.cards || []).forEach(function (cardConfig) {
    section.appendChild(createMedia(cardConfig));
    section.appendChild(createMediaTitle(cardConfig));
  });

  return section;
}

function createLabel(labelConfig) {
  var label = document.createElement("div");
  label.className = "zr-3dnew-section-label";
  label.textContent = labelConfig.text || "";
  applyBoxStyle(label, labelConfig);
  return label;
}

function createGuide(guideConfig) {
  var guide = document.createElement("div");
  guide.className = "zr-3dnew-guide";
  guide.style.left = String(guideConfig.left || 0) + "px";
  guide.style.top = String(guideConfig.top || 0) + "px";
  guide.style.width = String(guideConfig.width || 0) + "px";

  var wrap = document.createElement("div");
  wrap.className = "zr-3dnew-guide-wrap";

  var line = document.createElement("span");
  line.className = "zr-3dnew-guide-line";

  var arrow = document.createElement("span");
  arrow.className = "zr-3dnew-guide-arrow";

  wrap.appendChild(line);
  wrap.appendChild(arrow);
  guide.appendChild(wrap);
  return guide;
}

function createButton(buttonConfig) {
  var button = document.createElement("a");
  button.className = "zr-3dnew-button";
  button.href = buttonConfig.href || "#";
  button.target = buttonConfig.target || "_self";
  button.rel = button.target === "_blank" ? "noopener noreferrer" : "";
  button.style.left = String(buttonConfig.left || 0) + "px";
  button.style.top = String(buttonConfig.top || 0) + "px";

  var label = document.createElement("span");
  label.className = "zr-3dnew-button-label";
  label.textContent = buttonConfig.text || "查看更多>";

  button.appendChild(label);
  return button;
}

function createMedia(cardConfig) {
  var media = document.createElement("article");
  media.className = "zr-3dnew-media";
  applyBoxStyle(media, cardConfig.frame || {});

  var iframe = document.createElement("iframe");
  iframe.src = cardConfig.iframeUrl || "";
  iframe.title = cardConfig.title || "";
  iframe.loading = "lazy";
  iframe.setAttribute("scrolling", "no");
  iframe.setAttribute("allowtransparency", "true");
  iframe.setAttribute("frameborder", "0");

  media.appendChild(iframe);
  return media;
}

function createMediaTitle(cardConfig) {
  var title = document.createElement("div");
  title.className = "zr-3dnew-media-title";
  title.textContent = cardConfig.title || "";
  applyBoxStyle(title, cardConfig.titleBox || {});
  return title;
}

function applyBoxStyle(node, box) {
  if (!node || !box) {
    return;
  }

  if (box.left !== undefined) {
    node.style.left = String(box.left) + "px";
  }
  if (box.top !== undefined) {
    node.style.top = String(box.top) + "px";
  }
  if (box.width !== undefined) {
    node.style.width = String(box.width) + "px";
  }
  if (box.height !== undefined) {
    node.style.height = String(box.height) + "px";
  }
}
