document.addEventListener("DOMContentLoaded", function () {
    document.querySelectorAll("[data-bazar-auto-submit]").forEach(function (field) {
        field.addEventListener("change", function () {
            const form = field.closest("form");
            if (form) {
                form.submit();
            }
        });
    });

    const redirectNode = document.querySelector("[data-auto-redirect-url]");
    if (redirectNode) {
        const url = redirectNode.getAttribute("data-auto-redirect-url");
        const delay = Number(redirectNode.getAttribute("data-auto-redirect-delay") || 2500);
        if (url) {
            window.setTimeout(function () {
                window.location.href = url;
            }, delay);
        }
    }
});
