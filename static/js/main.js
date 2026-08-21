(function ($) {
    "use strict";

    $(function () {
        var $health = $("#api-health");
        if (!$health.length) {
            return;
        }

        $.getJSON("/api/health/")
            .done(function (data) {
                $health
                    .text(data.status === "ok" ? "ok" : "unexpected response")
                    .toggleClass("ok", data.status === "ok")
                    .removeClass("pending");
            })
            .fail(function () {
                $health.text("unreachable").addClass("error").removeClass("pending");
            });
    });
})(jQuery);
