import { initSharedSlider } from "https://static.jsss999.com/upload/zrsite/plugin/shared-slider.js?v=20260319-oss-1";

var root = document.getElementById("zr-vr-root");

if (root) {
  root.setAttribute("data-zr-vr-page", "1");
  initStandalonePreview();
  initPage();
}

function initStandalonePreview() {
  if (!document.body || root.parentElement !== document.body) {
    return;
  }

  document.documentElement.style.backgroundColor = "#ffffff";
  document.body.style.margin = "0";
  document.body.style.backgroundColor = "#ffffff";
}

async function initPage() {
  try {
    var pageConfig = await loadJson(root.getAttribute("data-page-config"));
    var sections = pageConfig.sections || [];
    renderSections(sections);
    renderMoreButton(pageConfig.moreButton || {});
    initSharedSlider(document.getElementById("zr-vr-slider"), pageConfig.slider || {});
  } catch (error) {
    console.error("Failed to render VR home page.", error);
  }
}

async function loadJson(url) {
  var response = await fetch(url, { cache: "no-store" });
  if (!response.ok) {
    throw new Error("Config request failed: " + response.status);
  }
  return response.json();
}

function renderSections(sections) {
  var container = document.getElementById("zr-vr-sections");
  if (!container) {
    return;
  }

  container.innerHTML = "";
  sections.forEach(function (section) {
    container.appendChild(createSection(section));
  });
}

function createSection(section) {
  var wrapper = document.createElement("section");
  wrapper.className = "zr-vr-section";
  wrapper.setAttribute("data-zr-vr-section", "1");
  wrapper.setAttribute("aria-label", section.title || "");

  var heading = document.createElement("div");
  heading.className = "zr-vr-section-heading";

  var title = document.createElement("h2");
  title.textContent = section.title || "";

  heading.appendChild(title);
  wrapper.appendChild(heading);

  var grid = document.createElement("div");
  grid.className = "zr-vr-section-grid";

  (section.items || []).forEach(function (item) {
    grid.appendChild(createCard(item));
  });

  wrapper.appendChild(grid);
  return wrapper;
}

function createCard(item) {
  var card = document.createElement("article");
  card.className = "zr-vr-card";
  card.setAttribute("data-zr-vr-card", "1");

  var media = document.createElement("div");
  media.className = "zr-vr-card-media";

  var loading = document.createElement("div");
  loading.className = "zr-vr-card-loading";
  loading.setAttribute("aria-hidden", "true");

  var iframe = document.createElement("iframe");
  iframe.src = item.iframeUrl || "";
  iframe.title = item.title || "";
  iframe.setAttribute("frameborder", "0");
  iframe.setAttribute("scrolling", "no");
  iframe.setAttribute("allowtransparency", "true");
  iframe.width = "650";
  iframe.height = "460";
  iframe.addEventListener("load", function () {
    media.classList.add("is-loaded");
  });

  var line = document.createElement("span");
  line.className = "zr-vr-card-line";

  var title = document.createElement("h3");
  title.className = "zr-vr-card-title";
  title.textContent = item.title || "";

  media.appendChild(loading);
  media.appendChild(iframe);
  card.appendChild(media);
  card.appendChild(line);
  card.appendChild(title);

  return card;
}

function renderMoreButton(buttonConfig) {
  var button = document.getElementById("zr-vr-more-button");
  if (!button) {
    return;
  }

  button.href = buttonConfig.href || "#";
  button.setAttribute("target", buttonConfig.target || "_self");
  button.setAttribute("rel", buttonConfig.target === "_blank" ? "noopener noreferrer" : "");

  var label = button.querySelector(".zr-vr-more-button-label");
  if (label) {
    label.textContent = buttonConfig.text || "更多产品";
  }
}
