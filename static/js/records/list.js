(function ($) {
    "use strict";

    if (!$("#page-records").length) return;

    const $thead = $("#rec-thead-row");
    const $tbody = $("#rec-tbody");
    const $count = $("#rec-count");
    const $modal = $("#record-modal");
    let debounce = null;
    let byId = {};
    let currentCols = [];

    function esc(s) {
        return $("<div>").text(s == null ? "" : s).html();
    }

    function currentParams() {
        const p = {};
        const search = $("#rec-search").val();
        const template = $("#rec-template").val();
        const status = $("#rec-status").val();
        const after = $("#rec-after").val();
        const before = $("#rec-before").val();
        if (search) p.search = search;
        if (template) p.template = template;
        if (status) p.status = status;
        if (after) p.created_after = after;
        if (before) p.created_before = before;
        return p;
    }

    // One column per template field, unioned across every record in the
    // current filtered set (same approach as the CSV/Excel export), in
    // first-seen order.
    function collectColumns(results) {
        const cols = [];
        const seen = {};
        results.forEach(function (rec) {
            (rec.field_schema || []).forEach(function (f) {
                if (!seen[f.name]) {
                    seen[f.name] = true;
                    cols.push(f);
                }
            });
        });
        return cols;
    }

    function renderHead(cols) {
        let html = "<th>Email</th>";
        cols.forEach(function (f) {
            html += "<th>" + esc(f.label) + "</th>";
        });
        $thead.html(html);
    }

    function statusClass(status) {
        return status === "APPROVED" ? "status-approved" : status === "REJECTED" ? "status-rejected" : "status-review";
    }

    function row(rec, cols) {
        let html = "<tr>";
        html +=
            '<td><button type="button" class="rec-email-cell" data-id="' + rec.id + '">' +
            "<strong>" + esc(rec.email_subject || "(no subject)") + "</strong>" +
            "<small>" + esc(rec.email_sender) + "</small>" +
            "</button></td>";
        cols.forEach(function (f) {
            const v = rec.data ? rec.data[f.name] : undefined;
            html += "<td>" + (v === null || v === undefined || v === "" ? "—" : esc(v)) + "</td>";
        });
        html += "</tr>";
        return html;
    }

    function load() {
        const colCount = Math.max(currentCols.length + 1, 1);
        $tbody.html('<tr><td colspan="' + colCount + '" class="hint">Loading…</td></tr>');
        $.getJSON("/api/records/", currentParams())
            .done(function (resp) {
                const results = resp.results || resp;
                byId = {};
                results.forEach(function (rec) { byId[rec.id] = rec; });
                currentCols = collectColumns(results);
                renderHead(currentCols);
                if (!results.length) {
                    $tbody.html('<tr><td colspan="' + Math.max(currentCols.length + 1, 1) + '" class="hint">No records match these filters.</td></tr>');
                } else {
                    $tbody.html(results.map(function (rec) { return row(rec, currentCols); }).join(""));
                }
                $count.text("Showing " + results.length + " of " + (resp.count || results.length) + " records");
            })
            .fail(function () {
                $tbody.html('<tr><td class="hint error">Failed to load records.</td></tr>');
            });
        updateExportLinks();
    }

    function updateExportLinks() {
        const qs = $.param(currentParams());
        $("#export-csv").attr("href", "/exports/records.csv" + (qs ? "?" + qs : ""));
        $("#export-xlsx").attr("href", "/exports/records.xlsx" + (qs ? "?" + qs : ""));
    }

    // Record info modal — click the Email cell to open it.
    function fmtDate(iso) {
        if (!iso) return "—";
        const d = new Date(iso);
        return isNaN(d) ? iso : d.toLocaleString();
    }

    function openModal(rec) {
        $("#record-modal-title").text(rec.email_subject || "(no subject)");
        $("#record-modal-status")
            .attr("class", "status-pill " + statusClass(rec.status))
            .text(rec.status[0] + rec.status.slice(1).toLowerCase());

        const review = rec.review || {};
        const meta = [
            ["From", rec.email_sender || "—"],
            ["Template", rec.template_name || "—"],
            ["Message ID", rec.email_message_id || "—"],
            ["Received", fmtDate(rec.email_received_at)],
            ["Confidence", rec.confidence || (review.required_found + "/" + review.required_total + " required fields")],
            ["Approved by", rec.approved_by_name ? rec.approved_by_name + " · " + fmtDate(rec.approved_at) : "—"],
            ["Created", fmtDate(rec.created_at)],
        ];
        let metaHtml = "";
        meta.forEach(function (pair) {
            metaHtml += "<div><span>" + esc(pair[0]) + "</span><strong>" + esc(pair[1]) + "</strong></div>";
        });
        $("#record-modal-meta").html(metaHtml);

        const openHref = rec.status === "DRAFT" ? "/review/" + rec.id + "/" : "/records/" + rec.id + "/";
        $("#record-modal-open").attr("href", openHref);

        $modal.addClass("is-open");
    }

    $tbody.on("click", ".rec-email-cell", function () {
        const rec = byId[$(this).data("id")];
        if (rec) openModal(rec);
    });

    function closeModal() {
        $modal.removeClass("is-open");
    }
    $("#record-modal-close, #record-modal-close-btn").on("click", closeModal);
    $modal.on("click", function (e) {
        if (e.target === this) closeModal();
    });
    $(document).on("keydown", function (e) {
        if (e.key === "Escape" && $modal.hasClass("is-open")) closeModal();
    });

    $("#rec-search").on("input", function () {
        clearTimeout(debounce);
        debounce = setTimeout(load, 300);
    });
    $("#rec-template, #rec-status, #rec-after, #rec-before").on("change", load);
    $("#rec-clear").on("click", function () {
        $("#rec-search, #rec-after, #rec-before").val("");
        $("#rec-template").val("");
        $("#rec-status").val("");
        load();
    });

    load();
})(jQuery);
