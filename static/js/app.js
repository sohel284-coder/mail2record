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
})(jQuery);