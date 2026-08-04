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

    const feedbackNode = document.querySelector("[data-cart-feedback]");
    const cartTotalNode = document.querySelector("[data-cart-total]");
    const cartBadgeNode = document.querySelector(".cart-nav-badge");

    function showCartFeedback(message, type) {
        if (!feedbackNode || !message) {
            return;
        }

        feedbackNode.hidden = false;
        feedbackNode.textContent = message;
        feedbackNode.classList.remove("is-success", "is-error");
        feedbackNode.classList.add(type === "error" ? "is-error" : "is-success");
    }

    function syncCartBadge(quantityDisplay, quantityValue) {
        if (!cartBadgeNode) {
            return;
        }

        if (Number(quantityValue) > 0) {
            cartBadgeNode.textContent = quantityDisplay;
            cartBadgeNode.hidden = false;
            return;
        }

        cartBadgeNode.hidden = true;
    }

    function syncCartRow(row, payload) {
        const quantityInput = row.querySelector("[data-cart-quantity-input]");
        const itemTotalNode = row.querySelector("[data-item-total]");
        const stockNode = row.querySelector("[data-item-stock]");
        const increaseBtn = row.querySelector('[data-cart-action="increase"]');
        const decreaseBtn = row.querySelector('[data-cart-action="decrease"]');

        if (quantityInput) {
            quantityInput.value = payload.quantity;
            quantityInput.max = payload.stock;
            quantityInput.defaultValue = String(payload.quantity);
        }
        if (itemTotalNode) {
            itemTotalNode.textContent = payload.item_total_display;
        }
        if (stockNode) {
            stockNode.textContent = payload.stock.toLocaleString("fa-IR");
        }
        if (cartTotalNode) {
            cartTotalNode.textContent = payload.cart_total_display;
        }
        if (increaseBtn) {
            increaseBtn.disabled = !payload.can_increment;
        }
        if (decreaseBtn) {
            decreaseBtn.disabled = !payload.can_decrement;
        }
        syncCartBadge(payload.cart_total_quantity_display, payload.cart_total_quantity);
    }

    function updateCartQuantity(row, quantity) {
        const form = row.querySelector("[data-cart-quantity-form]");
        const quantityInput = row.querySelector("[data-cart-quantity-input]");
        if (!form || !quantityInput) {
            return;
        }

        const max = Number(quantityInput.max || row.dataset.stock || 0);
        const normalizedQuantity = Math.max(1, Math.min(Number(quantity) || 1, max || Number(quantity) || 1));
        const csrfToken = form.querySelector('input[name="csrfmiddlewaretoken"]');
        const formData = new FormData();
        formData.append("quantity", String(normalizedQuantity));

        row.classList.add("bazar-cart-item-loading");
        quantityInput.value = normalizedQuantity;

        fetch(form.action, {
            method: "POST",
            body: formData,
            headers: csrfToken ? { "X-CSRFToken": csrfToken.value } : {},
            credentials: "same-origin",
        })
            .then(async function (response) {
                const payload = await response.json();
                if (!response.ok) {
                    throw payload;
                }
                syncCartRow(row, payload);
                showCartFeedback(payload.message, "success");
            })
            .catch(function (payload) {
                if (payload && typeof payload === "object" && payload.quantity) {
                    syncCartRow(row, payload);
                } else if (quantityInput) {
                    quantityInput.value = quantityInput.defaultValue || "1";
                }
                showCartFeedback((payload && payload.message) || "بروزرسانی سبد خرید انجام نشد.", "error");
            })
            .finally(function () {
                row.classList.remove("bazar-cart-item-loading");
            });
    }

    document.querySelectorAll("[data-cart-item]").forEach(function (row) {
        const quantityInput = row.querySelector("[data-cart-quantity-input]");
        const increaseBtn = row.querySelector('[data-cart-action="increase"]');
        const decreaseBtn = row.querySelector('[data-cart-action="decrease"]');

        if (quantityInput) {
            quantityInput.defaultValue = quantityInput.value;
            quantityInput.addEventListener("change", function () {
                updateCartQuantity(row, quantityInput.value);
            });
        }

        if (increaseBtn && quantityInput) {
            increaseBtn.addEventListener("click", function () {
                updateCartQuantity(row, Number(quantityInput.value || 0) + 1);
            });
        }

        if (decreaseBtn && quantityInput) {
            decreaseBtn.addEventListener("click", function () {
                updateCartQuantity(row, Number(quantityInput.value || 0) - 1);
            });
        }
    });
});
document.addEventListener("DOMContentLoaded", function () {
    const feedbackEl = document.querySelector("[data-cart-feedback]");
    let feedbackTimer = null;

    function showCartFeedback(message, isError) {
        if (!feedbackEl) return;
        feedbackEl.textContent = message;
        feedbackEl.hidden = false;
        feedbackEl.classList.toggle("is-error", Boolean(isError));
        window.clearTimeout(feedbackTimer);
        feedbackTimer = window.setTimeout(function () {
            feedbackEl.hidden = true;
        }, 3000);
    }

    function toPersianDigits(value) {
        return String(value).replace(/\d/g, function (d) {
            return "۰۱۲۳۴۵۶۷۸۹"[d];
        });
    }

    document.querySelectorAll("[data-cart-item]").forEach(function (row) {
        const form = row.querySelector("[data-cart-quantity-form]");
        const input = row.querySelector("[data-cart-quantity-input]");
        if (!form || !input) return;

        let debounceTimer = null;

        function submitQuantity() {
            const stock = Number(row.dataset.stock || input.max || 0);
            let quantity = parseInt(input.value, 10);
            if (!quantity || quantity < 1) quantity = 1;
            if (stock > 0 && quantity > stock) {
                quantity = stock;
                showCartFeedback("تعداد انتخابی بیشتر از موجودی محصول است.", true);
            }
            input.value = quantity;

            const formData = new FormData(form);
            formData.set("quantity", quantity);
            const csrfInput = form.querySelector("input[name=csrfmiddlewaretoken]");

            fetch(form.action, {
                method: "POST",
                headers: {
                    "X-Requested-With": "XMLHttpRequest",
                    "X-CSRFToken": csrfInput ? csrfInput.value : "",
                },
                body: formData,
            })
                .then(function (res) { return res.json(); })
                .then(function (data) {
                    if (!data) return;

                    const totalEl = row.querySelector("[data-item-total]");
                    if (totalEl) totalEl.textContent = toPersianDigits(data.item_total.toLocaleString("en-US"));

                    const cartTotalEl = document.querySelector("[data-cart-total]");
                    if (cartTotalEl) cartTotalEl.textContent = toPersianDigits(data.cart_total.toLocaleString("en-US"));

                    showCartFeedback(data.error || "سبد خرید بروزرسانی شد.", Boolean(data.error));
                })
                .catch(function () {
                    showCartFeedback("خطا در بروزرسانی سبد خرید. دوباره تلاش کنید.", true);
                });
        }

        input.addEventListener("change", function () {
            window.clearTimeout(debounceTimer);
            debounceTimer = window.setTimeout(submitQuantity, 300);
        });

        row.querySelectorAll("[data-cart-action]").forEach(function (btn) {
            btn.addEventListener("click", function () {
                const stock = Number(row.dataset.stock || input.max || 0);
                let quantity = parseInt(input.value, 10) || 1;
                quantity = btn.dataset.cartAction === "increase"
                    ? (stock > 0 ? Math.min(quantity + 1, stock) : quantity + 1)
                    : Math.max(quantity - 1, 1);
                input.value = quantity;
                window.clearTimeout(debounceTimer);
                debounceTimer = window.setTimeout(submitQuantity, 150);
            });
        });
    });
});