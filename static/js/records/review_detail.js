(function ($) {
    "use strict";

    const $page = $("#page-review-detail");
    if (!$page.length) return;

    const recordId = $page.data("record-id");
    const apiBase = "/api/records/" + recordId + "/";
    const $form = $("#extraction-form");
    const $saveState = $("#save-state");
    let dirty = false;

    function collectData() {
        const data = {};
        $form.find("input").each(function () {
            const $input = $(this);
            const name = $input.attr("name");
            let raw = $input.val();

            if (raw === "" || raw === null) {
                data[name] = null;
                return;
            }
            const type = $input.data("type");
            if (type === "integer") {
                const n = parseInt(raw, 10);
                data[name] = Number.isNaN(n) ? raw : n;
            } else if (type === "number") {
                const n = parseFloat(raw);
                data[name] = Number.isNaN(n) ? raw : n;
            } else if (type === "boolean") {
                data[name] = /^(true|yes|1)$/i.test(raw);
            } else {
                data[name] = raw;
            }
        });
        return data;
    }

    function refreshValidation() {
        let missing = 0;
        $form.find("label[data-field]").each(function () {
            const $label = $(this);
            const $input = $label.find("input");
            const required = $label.find(".required").length > 0;
            const empty = !$input.val();
            $label.toggleClass("is-missing", required && empty);
            if (required && empty) missing += 1;
        });

        const $note = $("#validation-note");
        const $copy = $("#validation-copy");
        if (missing === 0) {
            $note.removeClass("is-warning");
            $copy.text("All required fields are filled. Ready for review.");
        } else {
            $note.addClass("is-warning");
            $copy.text(missing + " required field(s) still empty.");
        }
    }

    function markDirty() {
        dirty = true;
        $saveState.text("Unsaved changes").css("color", "var(--amber-deep)");
    }

    function markClean() {
        dirty = false;
        $saveState.text("No unsaved changes").css("color", "");
    }

    function save() {
        return $.ajax({
            url: apiBase,
            type: "PATCH",
            contentType: "application/json",
            data: JSON.stringify({ data: collectData() }),
        });
    }

    $form.on("input", "input", function () {
        markDirty();
        refreshValidation();
    });

    $("#save-btn").on("click", function () {
        const $btn = $(this).prop("disabled", true);
        save()
            .done(function () {
                markClean();
                window.showToast("Edits saved.", "success");
            })
            .fail(function (xhr) {
                const msg = (xhr.responseJSON && JSON.stringify(xhr.responseJSON)) || "Save failed.";
                window.showToast(msg, "warning");
            })
            .always(function () {
                $btn.prop("disabled", false);
            });
    });

    $("#approve-btn").on("click", function () {
        const $btn = $(this).prop("disabled", true);
        const step = dirty ? save() : $.Deferred().resolve().promise();
        $.when(step)
            .then(function () {
                return $.ajax({ url: apiBase + "approve/", type: "POST" });
            })
            .done(function () {
                window.showToast("Record approved.", "success");
                window.location.href = "/review/";
            })
            .fail(function (xhr) {
                const msg = (xhr.responseJSON && (xhr.responseJSON.detail || JSON.stringify(xhr.responseJSON))) || "Approve failed.";
                window.showToast(msg, "warning");
                $btn.prop("disabled", false);
            });
    });

    $("#reject-btn").on("click", function () {
        const $rejectBtn = $(this);
        window
            .confirmDialog({
                title: "Reject this draft?",
                message: "It won't appear in exports. This can't be undone.",
                confirmLabel: "Reject",
            })
            .then(function (confirmed) {
                if (!confirmed) return;

                const $btn = $rejectBtn.prop("disabled", true);
                $.ajax({ url: apiBase + "reject/", type: "POST" })
                    .done(function () {
                        window.showToast("Record rejected.", "default");
                        window.location.href = "/review/";
                    })
                    .fail(function (xhr) {
                        const msg = (xhr.responseJSON && (xhr.responseJSON.detail || JSON.stringify(xhr.responseJSON))) || "Reject failed.";
                        window.showToast(msg, "warning");
                        $btn.prop("disabled", false);
                    });
            });
    });

    window.addEventListener("beforeunload", function (e) {
        if (dirty) {
            e.preventDefault();
            e.returnValue = "";
        }
    });

    refreshValidation();
})(jQuery);
