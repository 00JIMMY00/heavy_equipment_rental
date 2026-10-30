/* Anonymous login follows the OS theme. Desk keeps its native saved preference. */
(() => {
	function initialize() {
		const root = document.documentElement;
		if (!document.querySelector("#page-login") || root.hasAttribute("data-theme")) return;
		const systemTheme = window.matchMedia("(prefers-color-scheme: dark)");
		const applyTheme = () => {
			root.dataset.theme = systemTheme.matches ? "dark" : "light";
		};
		applyTheme();
		systemTheme.addEventListener("change", applyTheme);
	}
	if (document.readyState === "loading") {
		document.addEventListener("DOMContentLoaded", initialize, { once: true });
	} else {
		initialize();
	}
})();
