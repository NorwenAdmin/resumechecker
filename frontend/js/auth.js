async function mountUserBadge() {
  const nav = document.querySelector("nav");
  if (!nav) return null;

  let user;
  try {
    user = await API.me();
  } catch (e) {
    window.location.replace("/login.html");
    return null;
  }

  const badge = document.createElement("span");
  badge.style.marginLeft = "auto";
  badge.style.display = "flex";
  badge.style.alignItems = "center";
  badge.style.gap = "10px";
  badge.innerHTML = `<span class="muted">${user.email}</span>`;

  const logoutBtn = document.createElement("button");
  logoutBtn.className = "secondary";
  logoutBtn.textContent = "Log out";
  logoutBtn.style.padding = "4px 10px";
  logoutBtn.style.fontSize = "12px";
  logoutBtn.addEventListener("click", async () => {
    await API.logout();
    window.location.replace("/login.html");
  });
  badge.appendChild(logoutBtn);

  nav.appendChild(badge);
  return user;
}
