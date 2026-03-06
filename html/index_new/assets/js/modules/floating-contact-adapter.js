export function initFloatingContactAdapter(mountEl) {
  if (!mountEl) {
    return;
  }

  mountEl.setAttribute("data-floating-adapter", "pending");
  mountEl.innerHTML = "";

  // Placeholder: the WP/online consultation plugin can be mounted here later.
  const placeholder = document.createElement("div");
  placeholder.style.display = "none";
  placeholder.textContent = "floating contact mount";
  mountEl.appendChild(placeholder);
}
