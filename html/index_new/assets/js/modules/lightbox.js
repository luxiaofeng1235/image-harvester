export function initLightbox(root) {
  if (!root) {
    return {
      open: () => {},
      close: () => {}
    };
  }

  const dialog = root.querySelector(".lightbox-dialog");
  const image = root.querySelector("#lightbox-image");
  const loading = root.querySelector("#lightbox-loading");
  const caption = root.querySelector("#lightbox-caption");
  const closeBtn = root.querySelector('[data-role="close"]');
  const prevBtn = root.querySelector('[data-role="prev"]');
  const nextBtn = root.querySelector('[data-role="next"]');

  let items = [];
  let index = 0;
  let opener = null;
  let renderToken = 0;
  const preloaded = new Set();
  const MIN_LOADING_MS = 650;

  function setLoading(flag) {
    root.classList.toggle("is-loading", Boolean(flag));
    if (loading) {
      loading.hidden = !flag;
    }
  }

  function preload(url) {
    if (!url || preloaded.has(url)) return;
    const temp = new Image();
    temp.src = url;
    preloaded.add(url);
  }

  function preloadBatch() {
    items.forEach((item) => preload(item.largeUrl || item.thumbUrl));
  }

  function render() {
    if (!items.length) return;
    const token = ++renderToken;
    const current = items[index];
    const imgUrl = current.largeUrl || current.thumbUrl;
    const loadingStart = Date.now();

    setLoading(true);
    image.alt = current.name || "图片预览";
    caption.textContent = current.name || "";

    const loader = new Image();
    const done = () => {
      if (token !== renderToken) return;
      image.src = imgUrl;
      const elapsed = Date.now() - loadingStart;
      const wait = Math.max(0, MIN_LOADING_MS - elapsed);
      window.setTimeout(() => {
        if (token !== renderToken) return;
        setLoading(false);
      }, wait);
    };
    loader.onload = () => {
      done();
    };
    loader.onerror = () => {
      done();
    };
    loader.src = imgUrl;
  }

  function lockBody() {
    document.body.style.overflow = "hidden";
  }

  function unlockBody() {
    document.body.style.overflow = "";
  }

  function close() {
    root.hidden = true;
    setLoading(false);
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
    root.hidden = false;
    lockBody();
    render();
    window.setTimeout(preloadBatch, 1200);
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
      event.preventDefault();
      close();
    } else if (event.key === "ArrowLeft") {
      event.preventDefault();
      prev();
    } else if (event.key === "ArrowRight") {
      event.preventDefault();
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
