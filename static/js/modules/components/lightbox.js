export function openPhotoLightbox(src) {
  let lightbox = document.getElementById("photo-lightbox");
  if (!lightbox) {
    lightbox = document.createElement("div");
    lightbox.id = "photo-lightbox";
    lightbox.className = "photo-lightbox-overlay";
    lightbox.innerHTML = `
      <div class="photo-lightbox-content">
        <button type="button" class="photo-lightbox-close">&times;</button>
        <img id="photo-lightbox-img" src="" alt="Fullscreen photo" />
      </div>
    `;
    document.body.appendChild(lightbox);

    const closeBtn = lightbox.querySelector(".photo-lightbox-close");
    closeBtn.addEventListener("click", () => lightbox.classList.remove("active"));
    lightbox.addEventListener("click", (e) => {
      if (e.target === lightbox) lightbox.classList.remove("active");
    });
    document.addEventListener("keydown", (e) => {
      if (e.key === "Escape" && lightbox.classList.contains("active")) {
        lightbox.classList.remove("active");
      }
    });
  }

  const imgEl = document.getElementById("photo-lightbox-img");
  if (imgEl) imgEl.src = src;
  lightbox.classList.add("active");
}
