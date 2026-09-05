(function ($) {
    "use strict";

    if (!$("#page-settings").length) return;

    // --- IMAP connect modal --------------------------------------------- //
    const $modal = $("#imap-modal");
    const $err = $("#imap-error");

    // Domain -> (host, port) — mirrors providers.IMAP_HOST_PRESETS so the form
    // pre-fills; the server re-guesses / validates anyway.
    const PRESETS = {
        "gmail.com": ["imap.gmail.com", 993],
        "googlemail.com": ["imap.gmail.com", 993],
        "outlook.com": ["outlook.office365.com", 993],
        "hotmail.com": ["outlook.office365.com", 993],
        "live.com": ["outlook.office365.com", 993],
        "msn.com": ["outlook.office365.com", 993],
        "yahoo.com": ["imap.mail.yahoo.com", 993],
        "aol.com": ["imap.aol.com", 993],
        "icloud.com": ["imap.mail.me.com", 993],
        "me.com": ["imap.mail.me.com", 993],
        "fastmail.com": ["imap.fastmail.com", 993],
        "zoho.com": ["imap.zoho.com", 993],
        "gmx.com": ["imap.gmx.com", 993],
    };

    function openModal() {
        $err.hide().text("");
        $("#imap-email, #imap-password, #imap-host").val("");
        $("#imap-port").val(993);
        $("#imap-host-guess").text("");
        $modal.addClass("is-open");
        $("#imap-email").trigger("focus");
    }
    function closeModal() {
        $modal.removeClass("is-open");
    }

    $("#mailbox-imap-btn").on("click", openModal);
    $("#imap-cancel").on("click", closeModal);
    $modal.on("click", function (e) { if (e.target === this) closeModal(); });
    $(document).on("keydown", function (e) {
        if (e.key === "Escape" && $modal.hasClass("is-open")) closeModal();
    });

    $("#imap-email").on("input", function () {
        const domain = ($(this).val().split("@")[1] || "").toLowerCase().trim();
        const preset = PRESETS[domain];
        if (preset && !$("#imap-host").val()) {
            $("#imap-host-guess").text("· " + preset[0]);
        } else {
            $("#imap-host-guess").text("");
        }
    });

    $("#imap-connect").on("click", function () {
        const $btn = $(this).prop("disabled", true).text("Testing…");
        $err.hide();

        $.ajax({
            url: "/api/email-account/imap/",
            type: "POST",
            contentType: "application/json",
            data: JSON.stringify({
                email_address: $("#imap-email").val().trim(),
                password: $("#imap-password").val(),
                host: $("#imap-host").val().trim(),
                port: $("#imap-port").val(),
            }),
        })
            .done(function () {
                window.showToast("Mailbox connected.", "success");
                window.location.reload();
            })
            .fail(function (xhr) {
                const msg = (xhr.responseJSON && xhr.responseJSON.detail) || "Couldn't connect.";
                $err.text(msg).show();
                $btn.prop("disabled", false).text("Test & connect");
            });
    });

    // --- Test / disconnect an existing mailbox ------------------------- //
    $("#mailbox-test-btn").on("click", function () {
        const $btn = $(this).prop("disabled", true).text("Testing…");
        $.ajax({ url: "/api/email-account/test/", type: "POST" })
            .done(function () {
                window.showToast("Connection OK.", "success");
                window.location.reload();
            })
            .fail(function (xhr) {
                const msg = (xhr.responseJSON && xhr.responseJSON.detail) || "Connection failed.";
                window.showToast(msg, "warning");
                $btn.prop("disabled", false).text("Test connection");
            });
    });

    $("#mailbox-disconnect-btn").on("click", function () {
        window
            .confirmDialog({
                title: "Disconnect this mailbox?",
                message: "Mail2Record will stop syncing it. Already-collected emails and records stay.",
                confirmLabel: "Disconnect",
            })
            .then(function (confirmed) {
                if (!confirmed) return;
                $.ajax({ url: "/api/email-account/", type: "DELETE" })
                    .done(function () {
                        window.showToast("Mailbox disconnected.", "default");
                        window.location.reload();
                    })
                    .fail(function () {
                        window.showToast("Couldn't disconnect.", "warning");
                    });
            });
    });
})(jQuery);
