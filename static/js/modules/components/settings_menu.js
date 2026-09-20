/**
 * Header Settings Menu Component
 * Controls hover/click toggle, click-outside dismissal, and keyboard accessibility
 * for the consolidated settings gear dropdown.
 */

let _initialized = false;

export function initSettingsMenu() {
  if (_initialized) return;
  _initialized = true;

  const dropdown = document.getElementById("settings-dropdown");
  const toggleBtn = document.getElementById("settings-toggle-btn");
  const menu = document.getElementById("settings-menu");

  if (!dropdown || !toggleBtn || !menu) return;

  function openMenu() {
    dropdown.classList.add("open");
    toggleBtn.setAttribute("aria-expanded", "true");
  }

  function closeMenu() {
    dropdown.classList.remove("open");
    toggleBtn.setAttribute("aria-expanded", "false");
  }

  function toggleMenu(e) {
    if (e) e.stopPropagation();
    const isOpen = dropdown.classList.contains("open");
    if (isOpen) {
      closeMenu();
    } else {
      openMenu();
    }
  }

  toggleBtn.addEventListener("click", toggleMenu);

  // Close when clicking outside
  document.addEventListener("click", (e) => {
    if (!dropdown.contains(e.target)) {
      closeMenu();
    }
  });

  // Keyboard accessibility
  document.addEventListener("keydown", (e) => {
    if (e.key === "Escape" && dropdown.classList.contains("open")) {
      closeMenu();
      toggleBtn.focus();
    }
  });

  // Desktop hover interactions (ensure state synchronization)
  dropdown.addEventListener("mouseenter", () => {
    dropdown.classList.add("hovered");
  });

  dropdown.addEventListener("mouseleave", () => {
    dropdown.classList.remove("hovered");
  });
}
