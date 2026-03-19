import { initSharedSlider } from "../plugin/shared-slider.js?v=20260319-1";

var root = document.getElementById("zr-more-root");

if (root) {
  initPage();
}

async function initPage() {
  try {
    var config = await loadConfig();
    renderCompanyTitle(config.companyTitle);
    renderSections(config.sections || []);
    initSharedSlider(document.getElementById("zr-more-slider"), config.slider || {});
  } catch (error) {
    console.error("Failed to render more products page.", error);
  }
}

async function loadConfig() {
  var configUrl = root.getAttribute("data-config");
  var response = await fetch(configUrl, { cache: "no-store" });
  if (!response.ok) {
    throw new Error("Config request failed: " + response.status);
  }
  return response.json();
}

function renderCompanyTitle(title) {
  var heading = document.getElementById("zr-more-company-title");
  if (!heading || !title) {
    return;
  }
  heading.textContent = title;
}

function renderSections(sections) {
  var container = document.getElementById("zr-more-sections");
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
  wrapper.className = "zr-more-section";

  var shell = document.createElement("div");
  shell.className = "zr-more-shell";

  var heading = document.createElement("div");
  heading.className = "zr-more-section-heading";

  var line = document.createElement("span");
  line.className = "zr-more-section-line";

  var title = document.createElement("h2");
  title.textContent = section.title || "";

  heading.appendChild(line);
  heading.appendChild(title);
  shell.appendChild(heading);

  (section.rows || []).forEach(function (row) {
    var rowElement = document.createElement("div");
    rowElement.className = "zr-more-row";

    row.forEach(function (card) {
      rowElement.appendChild(createCard(card));
    });

    shell.appendChild(rowElement);
  });

  if (section.moreUrl) {
    var footer = document.createElement("div");
    footer.className = "zr-more-section-footer";

    var button = document.createElement("a");
    button.className = "zr-more-more-button";
    button.href = section.moreUrl;
    button.textContent = "更多产品";

    footer.appendChild(button);
    shell.appendChild(footer);
  }

  wrapper.appendChild(shell);
  return wrapper;
}

function createCard(card) {
  var link = document.createElement("a");
  link.className = "zr-more-card zr-more-card-" + (card.variant || "large");
  link.href = card.href || "#";
  link.setAttribute("aria-label", card.title || "");

  var media = document.createElement("span");
  media.className = "zr-more-card-media";

  var image = document.createElement("img");
  image.src = card.imageUrl || "";
  image.alt = card.title || "";
  image.loading = "lazy";
  image.decoding = "async";

  var overlay = document.createElement("span");
  overlay.className = "zr-more-card-overlay";

  var overlayTitle = document.createElement("span");
  overlayTitle.className = "zr-more-card-title";
  overlayTitle.textContent = card.title || "";

  overlay.appendChild(overlayTitle);
  media.appendChild(image);
  media.appendChild(overlay);
  link.appendChild(media);

  return link;
}
