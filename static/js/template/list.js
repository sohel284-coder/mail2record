(function ($) {
    "use strict";

    // Delete a template — with explicit user consent via the themed confirm
    // modal (window.confirmDialog, defined in app.js). The API blocks the
    // delete (409) if the template already has records, so a stray click
    // can never wipe out approved data.
    $(".template-delete-btn").on("click", function () {
        const $btn = $(this);
        const $card = $btn.closest(".template-card");
        const id = $btn.data("id");
        const name = $btn.data("name");

        window
            .confirmDialog({
                title: "Delete template?",
                message: 'Delete template "' + name + '"? This cannot be undone.',
                confirmLabel: "Delete",
            })
            .then(function (confirmed) {
                if (!confirmed) return;

                $btn.prop("disabled", true);

                $.ajax({ url: "/api/templates/" + id + "/", type: "DELETE" })
                    .done(function () {
                        window.showToast("Template deleted.", "success");
                        $card.fadeOut(180, function () {
                            $(this).remove();
                        });
                    })
                    .fail(function (xhr) {
                        const msg =
                            (xhr.responseJSON && xhr.responseJSON.detail) || "Delete failed.";
                        window.showToast(msg, "warning");
                        $btn.prop("disabled", false);
                    });
            });
    });

    // Set/unset the default template used to pre-fill the inbox extract dialog.
    $(".template-default-btn").on("click", function () {
        const $btn = $(this).prop("disabled", true);
        const name = $btn.data("name");
        $.ajax({ url: "/api/templates/" + $btn.data("id") + "/set-default/", type: "POST" })
            .done(function () {
                window.showToast('"' + name + '" is now the default template.', "success");
                window.location.reload();
            })
            .fail(function (xhr) {
                const msg = (xhr.responseJSON && xhr.responseJSON.detail) || "Couldn't set default.";
                window.showToast(msg, "warning");
                $btn.prop("disabled", false);
            });
    });

    $(".template-unset-default-btn").on("click", function () {
        const $btn = $(this).prop("disabled", true);
        $.ajax({ url: "/api/templates/" + $btn.data("id") + "/unset-default/", type: "POST" })
            .done(function () {
                window.showToast("Default template cleared.", "default");
                window.location.reload();
            })
            .fail(function (xhr) {
                const msg = (xhr.responseJSON && xhr.responseJSON.detail) || "Couldn't clear default.";
                window.showToast(msg, "warning");
                $btn.prop("disabled", false);
            });
    });
})(jQuery);
