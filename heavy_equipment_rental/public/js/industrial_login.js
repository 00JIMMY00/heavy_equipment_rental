/* Presentation only: native Frappe forms, routing and authentication remain intact. */
(() => {
	function initialize() {
		const root = document.documentElement;
		const page = document.querySelector("#page-login");
		const forms = page?.querySelector(".for-login")?.parentElement;
		if (!forms || page.querySelector(".her-login-shell")) return;
		root.dataset.theme = "light";
		const ar = (root.lang || "").startsWith("ar");
		const copy = ar ? {
			name: "لتأجير المعدات الثقيلة", eyebrow: "كل تفاصيل شغلك… في مكان واحد",
			title: "شغلك كبير.<br>وإدارته <em>أسهل.</em>",
			description: "من أول حجز لآخر رفعة، خليك متابع معداتك وعقودك وحساباتك بخطوات بسيطة وواضحة.",
			footer: "جاهزين ليوم شغل جديد؟", welcome: "أهلاً بيك من جديد", hint: "سجّل دخولك وخلّينا نبدأ يوم شغل ناجح.",
			features: ["معداتك", "عقودك", "حساباتك"], access: "مساحة عملك", note: "كل شغلك تحت السيطرة.",
		} : {
			name: "Heavy Equipment Rental", eyebrow: "All your operations, together",
			title: "Big work.<br>Made <em>simple.</em>",
			description: "From the first booking to the final lift. Keep your equipment, contracts and accounts moving together.",
			footer: "Ready for a new working day?", welcome: "Welcome back", hint: "Sign in and start a productive day.",
			features: ["Equipment", "Contracts", "Accounts"], access: "Your workspace", note: "Your operations, in hand.",
		};
		const shell = document.createElement("div");
		shell.className = "her-login-shell";
		shell.dir = ar ? "rtl" : "ltr";
		const hero = document.createElement("aside");
		hero.className = "her-login-hero";
		hero.innerHTML = `
			<div class="her-login-brand"><span class="her-login-monogram">HER<span>.</span></span><span>${copy.name}</span></div>
			<div class="her-login-story"><p class="her-login-eyebrow"><span aria-hidden="true"></span>${copy.eyebrow}</p><h1>${copy.title}</h1><p class="her-login-description">${copy.description}</p>
			<div class="her-login-features">${copy.features.map((text, index) => `<span><b aria-hidden="true">0${index + 1}</b>${text}</span>`).join("")}</div></div>
			<div class="her-login-photo" role="img" aria-label="${ar ? "أوناش صفراء في ساحة المعدات" : "Yellow mobile cranes in an equipment yard"}"></div>
			<div class="her-login-caption"><span class="her-login-stripe" aria-hidden="true"></span><span>${copy.footer}</span></div>`;
		forms.before(shell);
		shell.append(hero, forms);
		forms.classList.add("her-login-forms");
		const formIntro = document.createElement("div");
		formIntro.className = "her-login-form-intro";
		formIntro.innerHTML = `<span class="her-login-access">${copy.access}</span><span class="her-login-small-brand" dir="ltr">HER.</span>`;
		forms.prepend(formIntro);
		const note = document.createElement("p");
		note.className = "her-login-note";
		note.textContent = copy.note;
		forms.append(note);
		if (ar) {
			page.querySelectorAll(".btn-login[type='submit']").forEach(button => { button.textContent = "تسجيل الدخول"; });
			page.querySelectorAll("label[for='login_email']").forEach(label => { label.textContent = "اسم المستخدم أو البريد الإلكتروني"; });
			page.querySelectorAll("#login_email").forEach(input => { input.placeholder = "اسم المستخدم أو البريد الإلكتروني"; });
		}
		page.querySelectorAll(".for-login > .page-card-head, .for-email-login > .page-card-head").forEach(head => {
			const title = head.querySelector("h4");
			if (title) title.textContent = copy.welcome;
			const hint = document.createElement("p");
			hint.className = "her-login-hint";
			hint.textContent = copy.hint;
			head.append(hint);
		});
		page.querySelectorAll(".toggle-password").forEach(toggle => {
			toggle.setAttribute("role", "button");
			toggle.tabIndex = 0;
			const input = page.querySelector(toggle.getAttribute("toggle"));
			if (ar && input) {
				const updateLabel = () => {
					toggle.textContent = input.type === "password" ? "إظهار" : "إخفاء";
					toggle.setAttribute("aria-label", `${toggle.textContent} كلمة المرور`);
				};
				updateLabel();
				new MutationObserver(updateLabel).observe(input, { attributes: true, attributeFilter: ["type"] });
			}
			toggle.addEventListener("keydown", event => {
				if (event.key === "Enter" || event.key === " ") { event.preventDefault(); toggle.click(); }
			});
		});
	}
	if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", initialize, { once: true });
	else initialize();
})();
