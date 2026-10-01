// Apply the saved preference before paint. Storage is optional.
try {
  const savedTheme = localStorage.getItem("resolve-theme");
  if (savedTheme === "light" || savedTheme === "dark") {
    document.documentElement.dataset.theme = savedTheme;
  }
} catch { /* Private browsing can disable local storage. */ }
