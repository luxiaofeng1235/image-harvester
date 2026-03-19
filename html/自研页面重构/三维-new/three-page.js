import { initSharedSlider } from "https://static.jsss999.com/upload/zrsite/plugin/shared-slider.js?v=20260319-oss-1";

var root = document.getElementById("zr-3dnew-root");

if (root) {
  root.setAttribute("data-zr-3dnew-page", "1");
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

  container.setAttribute("data-zr-3dnew-content", "1");
  container.innerHTML = "";

  (config.sections || []).forEach(function (sectionConfig) {
    container.appendChild(createSection(sectionConfig));
  });
}

function createSection(sectionConfig) {
  var section = document.createElement("section");
  section.className = "zr-3dnew-section";
  section.setAttribute("data-zr-3dnew-section", "1");
  section.setAttribute("data-section-id", sectionConfig.id || "");

  if (sectionConfig.label) {
    section.appendChild(createLabel(sectionConfig.label));
  }

  section.appendChild(createGuide());

  if (sectionConfig.button) {
    section.appendChild(createButton(sectionConfig.button));
  }

  var items = document.createElement("div");
  items.className = "zr-3dnew-section-items";

  (sectionConfig.cards || []).forEach(function (cardConfig) {
    items.appendChild(createMediaItem(cardConfig));
  });

  section.appendChild(items);
  return section;
}

function createLabel(labelText) {
  var label = document.createElement("div");
  label.className = "zr-3dnew-section-label";
  label.textContent = labelText || "";
  return label;
}

function createGuide() {
  var guide = document.createElement("div");
  guide.className = "zr-3dnew-guide";
  guide.setAttribute("aria-hidden", "true");

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
  button.setAttribute("data-zr-3dnew-button", "1");
  button.href = buttonConfig.href || "#";
  button.target = buttonConfig.target || "_self";
  if (button.target === "_blank") {
    button.rel = "noopener noreferrer";
  }

  var label = document.createElement("span");
  label.className = "zr-3dnew-button-label";
  label.textContent = buttonConfig.text || "查看更多>";

  button.appendChild(label);
  return button;
}

function createMediaItem(cardConfig) {
  var item = document.createElement("article");
  item.className = "zr-3dnew-media-item";
  item.setAttribute("data-zr-3dnew-media-item", "1");

  var media = document.createElement("article");
  media.className = "zr-3dnew-media";

  var iframe = document.createElement("iframe");
  iframe.src = cardConfig.iframeUrl || "";
  iframe.title = cardConfig.title || "";
  iframe.loading = "lazy";
  iframe.setAttribute("scrolling", "no");
  iframe.setAttribute("allowtransparency", "true");
  iframe.setAttribute("frameborder", "0");

  media.appendChild(iframe);
  var title = document.createElement("div");
  title.className = "zr-3dnew-media-title";
  title.textContent = cardConfig.title || "";

  item.appendChild(media);
  item.appendChild(title);
  return item;
}
