export function initLightbox(root) {
  if (!root) {
    return {
      open: () => {},
      close: () => {}
    };
  }

  const dialog = root.querySelector(".lightbox-dialog");
  const image = root.querySelector("#lightbox-image");
  const caption = root.querySelector("#lightbox-caption");
  const detailLink = root.querySelector("#lightbox-detail-link");
  const closeBtn = root.querySelector('[data-role="close"]');
  const prevBtn = root.querySelector('[data-role="prev"]');
  const nextBtn = root.querySelector('[data-role="next"]');

  let items = [];
  let index = 0;
  let opener = null;

  function render() {
    if (!items.length) return;
    const current = items[index];
    image.src = current.largeUrl || current.thumbUrl;
    image.alt = current.name || "图片预览";
    caption.textContent = current.name || "";
    detailLink.href = current.detailUrl || "#";
  }

  function lockBody() {
    document.body.style.overflow = "hidden";
  }

  function unlockBody() {
    document.body.style.overflow = "";
  }

  function close() {
    root.hidden = true;
    unlockBody();
    if (opener && typeof opener.focus === "function") {
      opener.focus();
    }
  }

  function open(inputItems, startIndex, sourceEl) {
    if (!Array.isArray(inputItems) || !inputItems.length) {
      return;
    }
    items = inputItems;
    index = Math.max(0, Math.min(startIndex || 0, inputItems.length - 1));
    opener = sourceEl || document.activeElement;
    render();
    root.hidden = false;
    lockBody();
    if (dialog) {
      dialog.focus();
    }
  }

  function prev() {
    if (!items.length) return;
    index = (index - 1 + items.length) % items.length;
    render();
  }

  function next() {
    if (!items.length) return;
    index = (index + 1) % items.length;
    render();
  }

  root.addEventListener("click", (event) => {
    const target = event.target;
    if (!(target instanceof HTMLElement)) return;

    if (target.matches('[data-role="close"]') || target.classList.contains("lightbox-mask")) {
      close();
      return;
    }
    if (target.matches('[data-role="prev"]')) {
      prev();
      return;
    }
    if (target.matches('[data-role="next"]')) {
      next();
    }
  });

  document.addEventListener("keydown", (event) => {
    if (root.hidden) return;
    if (event.key === "Escape") {
      close();
    } else if (event.key === "ArrowLeft") {
      prev();
    } else if (event.key === "ArrowRight") {
      next();
    }
  });

  if (dialog) {
    dialog.setAttribute("tabindex", "-1");
  }

  if (closeBtn) closeBtn.setAttribute("aria-label", "关闭");
  if (prevBtn) prevBtn.setAttribute("aria-label", "上一张");
  if (nextBtn) nextBtn.setAttribute("aria-label", "下一张");

  return { open, close };
}
