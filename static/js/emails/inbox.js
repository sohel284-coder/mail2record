(function ($) {
    "use strict";

    const $tbody = $("#inbox-tbody");
    const $count = $("#inbox-count");
    let debounceTimer = null;

    function escapeHtml(str) {
        return $("<div>").text(str || "").html();
    }

    function timeAgo(isoString) {
        if (!isoString) return "—";
        const diffMs = Date.now() - new Date(isoString).getTime();
        const mins = Math.round(diffMs / 60000);
        if (mins < 60) return mins + " min ago";
        const hrs = Math.round(mins / 60);
        if (hrs < 24) return hrs + " hr ago";
        return Math.round(hrs / 24) + " day(s) ago";
    }

    function renderRow(email) {
        const statusPill = email.is_processed
            ? '<span class="status-pill status-approved">Processed</span>'
            : '<span class="status-pill status-review">Draft</span>';

        const actionCell = email.is_processed
            ? '<button class="row-action" disabled>Open →</button>'
            : '<a class="row-action" href="/review/' + email.id + '/">Review →</a>';

        return (
            "<tr>" +
            "<td><strong>" + escapeHtml(email.sender) + "</strong></td>" +
            "<td><strong>" + escapeHtml(email.subject || "(no subject)") + "</strong>" +
            "<small>Message ID · " + escapeHtml(email.message_id.slice(0, 12)) + "…</small></td>" +
            "<td>" + timeAgo(email.received_at) + "</td>" +
            "<td>" + statusPill + "</td>" +
            "<td>" + actionCell + "</td>" +
            "</tr>"
        );
    }

    function loadEmails() {
        const search = $("#inbox-search").val();
        const status = $("#inbox-status").val();

        const params = {};
        if (search) params.search = search;
        if (status !== "") params.is_processed = status;

        $tbody.html('<tr><td colspan="5" class="hint">Loading…</td></tr>');

        $.getJSON("/api/emails/", params)
            .done(function (resp) {
                const results = resp.results || resp;
                if (!results.length) {
                    $tbody.html('<tr><td colspan="5" class="hint">No emails match your filters.</td></tr>');
                } else {
                    $tbody.html(results.map(renderRow).join(""));
                }
                $count.text("Showing " + results.length + " of " + (resp.count || results.length) + " emails");
            })
            .fail(function () {
                $tbody.html('<tr><td colspan="5" class="hint error">Failed to load inbox.</td></tr>');
            });
    }

    $("#inbox-search").on("input", function () {
        clearTimeout(debounceTimer);
        debounceTimer = setTimeout(loadEmails, 300);
    });

    $("#inbox-status").on("change", loadEmails);

    $("#clear-filters").on("click", function () {
        $("#inbox-search").val("");
        $("#inbox-status").val("");
        loadEmails();
    });

    $("#sync-now-2").on("click", function () {
        window.showToast("Manual sync isn't wired up yet — run 'fetch_emails' from the terminal, or wait for the scheduled poll.", "default");
    });

    loadEmails();
})(jQuery);