(function ($) {
    "use strict";

    // Mobile sidebar toggle
    $("#mobile-menu").on("click", function () {
        $("#mobile-sidebar").addClass("is-open");
    });
    $("#sidebar-scrim").on("click", function () {
        $("#mobile-sidebar").removeClass("is-open");
    });

    // Toast helper — used by page-specific scripts via window.showToast
    window.showToast = function (message, tone) {
        tone = tone || "default";
        const $toast = $("#toast");
        $toast.removeClass("is-visible is-success is-warning").addClass("is-" + tone);
        $toast.find(".toast-copy").text(message);
        window.setTimeout(function () { $toast.addClass("is-visible"); }, 10);
        window.setTimeout(function () { $toast.removeClass("is-visible"); }, 3200);
    };

    // Sync-now button on dashboard — placeholder until Phase 3 wires real polling
    $("#sync-now").on("click", function () {
        window.showToast("Manual sync isn't wired up yet — automatic polling runs every 5 min.", "default");
    });

    // Confirm modal — a themed replacement for window.confirm(), used by
    // page-specific scripts via window.confirmDialog(). Returns a Promise
    // that resolves true (confirmed) or false (cancelled/dismissed).
    window.confirmDialog = function (options) {
        options = options || {};
        const $overlay = $("#confirm-modal");
        const $ok = $("#confirm-modal-ok");
        const $cancel = $("#confirm-modal-cancel");

        $("#confirm-modal-title").text(options.title || "Are you sure?");
        $("#confirm-modal-message").text(options.message || "");
        $ok.text(options.confirmLabel || "Confirm");
        $ok
            .removeClass("button-danger button-primary")
            .addClass(options.tone === "default" ? "button-primary" : "button-danger");

        return new Promise(function (resolve) {
            function close(result) {
                $overlay.removeClass("is-open");
                $ok.off(".confirmModal");
                $cancel.off(".confirmModal");
                $overlay.off(".confirmModal");
                $(document).off(".confirmModal");
                resolve(result);
            }

            $ok.on("click.confirmModal", function () { close(true); });
            $cancel.on("click.confirmModal", function () { close(false); });
            $overlay.on("click.confirmModal", function (e) {
                if (e.target === this) close(false);
            });
            $(document).on("keydown.confirmModal", function (e) {
                if (e.key === "Escape") close(false);
            });

            $overlay.addClass("is-open");
            $ok.trigger("focus");
        });
    };
})(jQuery);