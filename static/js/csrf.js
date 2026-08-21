(function ($) {
    "use strict";

    function getCookie(name) {
        const match = document.cookie.match(new RegExp("(^| )" + name + "=([^;]+)"));
        return match ? decodeURIComponent(match[2]) : null;
    }

    const csrftoken = getCookie("csrftoken");

    $.ajaxSetup({
        beforeSend: function (xhr, settings) {
            const safeMethod = /^(GET|HEAD|OPTIONS|TRACE)$/i.test(settings.type);
            if (!safeMethod && !this.crossDomain) {
                xhr.setRequestHeader("X-CSRFToken", csrftoken);
            }
        },
    });
})(jQuery);
