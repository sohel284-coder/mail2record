(function ($) {
    "use strict";

    const BATCH_MAX_SELECTED = 10;
    const BATCH_CONCURRENCY = 5; // fixed — not user-configurable, see project notes
    // Generous: with concurrency fixed at 5 against one local model, a
    // request that started last in a wave can wait behind 4 others.
    const EXTRACT_TIMEOUT_MS = 300000;
    const TRASH_SVG =
        '<svg viewBox="0 0 16 16" width="14" height="14" fill="none" stroke="currentColor" stroke-width="1.4" ' +
        'stroke-linecap="round" stroke-linejoin="round"><path d="M2.5 4h11M6 4V2.6c0-.33.27-.6.6-.6h2.8c.33 0 ' +
        '.6.27.6.6V4M5.5 4l.5 9.2c.02.44.39.8.83.8h3.34c.44 0 .81-.36.83-.8L11.5 4"/><path d="M6.5 6.8v4.4M9.5 6.8v4.4"/></svg>';

    const $page = $("#page-inbox");
    const $tbody = $("#inbox-tbody");
    const $count = $("#inbox-count");
    const defaultTemplateId = $page.data("default-template-id");
    const defaultTemplateName = $page.data("default-template-name");
    let debounceTimer = null;
    let pendingEmailId = null;
    let emailsById = {};
    let selectedIds = [];
    let batchRunning = false;

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

    // --- Table rendering -------------------------------------------------- //
    function renderRow(email) {
        let statusPill;
        let actionCell;
        let checkboxCell = "<td></td>";

        if (email.is_processed && email.record_id) {
            statusPill = '<span class="status-pill status-approved">Processed</span>';
            actionCell = '<a class="row-action" href="/review/' + email.record_id + '/">Review →</a>';
        } else if (email.is_processed) {
            statusPill = '<span class="status-pill status-approved">Processed</span>';
            actionCell = '<span class="hint">no draft</span>';
        } else {
            statusPill = '<span class="status-pill status-review">Unprocessed</span>';
            actionCell = '<button class="row-action extract-btn" data-id="' + email.id + '">Extract →</button>';
            checkboxCell = '<td><input type="checkbox" class="row-select" data-id="' + email.id + '"></td>';
        }

        const attachmentNote = email.attachments && email.attachments.length
            ? "<small>" + email.attachments.length + " attachment(s)</small>" : "";

        const deleteBtn =
            '<button type="button" class="icon-button row-delete-btn" data-id="' + email.id +
            '" data-subject="' + escapeHtml(email.subject || "(no subject)") + '" ' +
            'aria-label="Delete email" title="Delete email">' + TRASH_SVG + "</button>";

        return (
            '<tr data-id="' + email.id + '">' +
            checkboxCell +
            "<td><strong>" + escapeHtml(email.sender) + "</strong></td>" +
            "<td><strong>" + escapeHtml(email.subject || "(no subject)") + "</strong>" +
            "<small>" + escapeHtml((email.message_id || "").slice(0, 18)) + "…</small>" + attachmentNote + "</td>" +
            "<td>" + timeAgo(email.received_at) + "</td>" +
            "<td>" + statusPill + "</td>" +
            '<td><div style="display:flex;align-items:center;justify-content:flex-end;gap:8px;">' +
            actionCell + deleteBtn + "</div></td>" +
            "</tr>"
        );
    }

    function loadEmails() {
        const search = $("#inbox-search").val();
        const status = $("#inbox-status").val();

        const params = {};
        if (search) params.search = search;
        if (status !== "") params.is_processed = status;

        selectedIds = [];
        updateBatchBar();
        $tbody.html('<tr><td colspan="6" class="hint">Loading…</td></tr>');

        $.getJSON("/api/emails/", params)
            .done(function (resp) {
                const results = resp.results || resp;
                emailsById = {};
                results.forEach(function (email) { emailsById[email.id] = email; });
                if (!results.length) {
                    $tbody.html('<tr><td colspan="6" class="hint">No emails match your filters.</td></tr>');
                } else {
                    $tbody.html(results.map(renderRow).join(""));
                }
                $count.text("Showing " + results.length + " of " + (resp.count || results.length) + " emails");
            })
            .fail(function () {
                $tbody.html('<tr><td colspan="6" class="hint error">Failed to load inbox.</td></tr>');
            });
    }

    // --- Row selection / batch bar ----------------------------------------- //
    function updateBatchBar() {
        const $bar = $("#batch-bar");
        if (selectedIds.length > 0) {
            $("#batch-bar-text").text(
                selectedIds.length + " selected" + (selectedIds.length >= BATCH_MAX_SELECTED ? " (max)" : "")
            );
            $bar.css("display", "flex");
        } else {
            $bar.hide();
        }
        $("#inbox-select-all").prop(
            "checked",
            selectedIds.length > 0 && selectedIds.length === $tbody.find(".row-select").length
        );
    }

    $tbody.on("change", ".row-select", function () {
        const id = $(this).data("id");
        if (this.checked) {
            if (selectedIds.length >= BATCH_MAX_SELECTED) {
                this.checked = false;
                window.showToast("You can batch up to " + BATCH_MAX_SELECTED + " emails at once.", "warning");
                return;
            }
            selectedIds.push(id);
        } else {
            selectedIds = selectedIds.filter(function (x) { return x !== id; });
        }
        updateBatchBar();
    });

    $("#inbox-select-all").on("change", function () {
        const checked = this.checked;
        const $boxes = $tbody.find(".row-select");
        if (!checked) {
            selectedIds = [];
            $boxes.prop("checked", false);
            updateBatchBar();
            return;
        }
        selectedIds = [];
        $boxes.each(function () {
            if (selectedIds.length >= BATCH_MAX_SELECTED) {
                this.checked = false;
                return;
            }
            this.checked = true;
            selectedIds.push($(this).data("id"));
        });
        if ($boxes.length > BATCH_MAX_SELECTED) {
            window.showToast("Selected the first " + BATCH_MAX_SELECTED + " — that's the batch limit.", "default");
        }
        updateBatchBar();
    });

    $("#batch-clear-btn").on("click", function () {
        selectedIds = [];
        $tbody.find(".row-select").prop("checked", false);
        updateBatchBar();
    });

    // --- Delete (single row, always behind a themed confirm dialog) -------- //
    $tbody.on("click", ".row-delete-btn", function () {
        const $btn = $(this);
        const id = $btn.data("id");
        const subject = $btn.data("subject");

        window
            .confirmDialog({
                title: "Delete this email?",
                message: 'Permanently delete "' + subject + '" and any attachments. This can\'t be undone.',
                confirmLabel: "Delete",
            })
            .then(function (confirmed) {
                if (!confirmed) return;
                $btn.prop("disabled", true);
                $.ajax({ url: "/api/emails/" + id + "/", type: "DELETE" })
                    .done(function () {
                        window.showToast("Email deleted.", "default");
                        selectedIds = selectedIds.filter(function (x) { return x !== id; });
                        loadEmails();
                    })
                    .fail(function (xhr) {
                        const msg = (xhr.responseJSON && xhr.responseJSON.detail) || "Delete failed.";
                        window.showToast(msg, "warning");
                        $btn.prop("disabled", false);
                    });
            });
    });

    // --- Delete (bulk, from the selection bar) ------------------------------ //
    $("#batch-delete-btn").on("click", function () {
        if (!selectedIds.length) return;
        const ids = selectedIds.slice();
        const $btn = $(this);

        window
            .confirmDialog({
                title: "Delete " + ids.length + " email(s)?",
                message:
                    "Permanently delete the selected emails and their attachments. This can't be undone. " +
                    "Any that already have a record will be skipped.",
                confirmLabel: "Delete " + ids.length,
            })
            .then(function (confirmed) {
                if (!confirmed) return;
                $btn.prop("disabled", true);

                let doneCount = 0;
                let okCount = 0;
                let failCount = 0;

                ids.forEach(function (id) {
                    $.ajax({ url: "/api/emails/" + id + "/", type: "DELETE" })
                        .done(function () { okCount++; })
                        .fail(function () { failCount++; })
                        .always(function () {
                            doneCount++;
                            if (doneCount === ids.length) {
                                window.showToast(
                                    okCount + " deleted" + (failCount ? ", " + failCount + " skipped (has records)." : "."),
                                    failCount ? "warning" : "default"
                                );
                                $btn.prop("disabled", false);
                                selectedIds = [];
                                loadEmails();
                            }
                        });
                });
            });
    });

    // --- Single-email extract confirmation modal --------------------------- //
    // Clicking "Extract →" never fires the AI call directly — it opens a
    // dialog naming the default template (or asking you to pick one, if no
    // default is set yet), and — if the email has attachments — a picker for
    // exactly which one file (if any) to read. Only that file is ever opened;
    // everything else on the email is left untouched.
    const $modal = $("#extract-modal");
    const $modalCopy = $("#extract-modal-copy");
    const $modalSelect = $("#extract-modal-template");
    const $modalConfirm = $("#extract-modal-confirm");
    const $sourceRow = $("#extract-modal-source-row");
    const $sourceSelect = $("#extract-modal-source");

    function openExtractModal(email) {
        pendingEmailId = email.id;
        const subject = email.subject || "(no subject)";

        if (!$modalSelect.find("option").length) {
            $modalCopy.text("No active templates available — create one first.");
            $modalConfirm.prop("disabled", true);
        } else {
            $modalConfirm.prop("disabled", false);
            if (defaultTemplateId) {
                $modalCopy.html(
                    "This will extract <strong>" + escapeHtml(subject) + "</strong> using your default " +
                    "template, <strong>" + escapeHtml(defaultTemplateName) + "</strong>. " +
                    "Pick a different one below if this email doesn't match it."
                );
                $modalSelect.val(String(defaultTemplateId));
            } else {
                $modalCopy.html(
                    "No default template is set yet. Choose which template to extract " +
                    "<strong>" + escapeHtml(subject) + "</strong> against:"
                );
            }
        }

        const attachments = email.attachments || [];
        if (attachments.length) {
            let optionsHtml = '<option value="">Email body</option>';
            attachments.forEach(function (att) {
                const label = att.filename + (att.kind === "other" ? " (unsupported type)" : "");
                optionsHtml += '<option value="' + att.id + '">' + escapeHtml(label) + "</option>";
            });
            $sourceSelect.html(optionsHtml);
            const parseable = attachments.filter(function (a) { return a.kind !== "other"; });
            if (parseable.length === 1) {
                $sourceSelect.val(String(parseable[0].id));
            }
            $sourceRow.show();
        } else {
            $sourceSelect.html('<option value="">Email body</option>');
            $sourceRow.hide();
        }

        $modal.addClass("is-open");
    }

    function closeExtractModal() {
        $modal.removeClass("is-open");
        pendingEmailId = null;
    }

    $tbody.on("click", ".extract-btn", function () {
        const email = emailsById[$(this).data("id")];
        if (email) openExtractModal(email);
    });

    $("#extract-modal-cancel").on("click", closeExtractModal);
    $modal.on("click", function (e) {
        if (e.target === this) closeExtractModal();
    });

    // A client-side timeout/abort does NOT mean the server stopped — Django
    // keeps running the request to completion regardless of whether the
    // browser gave up waiting on it. Giving up on a slow-but-genuinely-
    // working extraction and just labelling it "failed" would leave the UI
    // out of sync with an email that in fact just got processed (is_processed
    // flips true only on real success — see pipeline.py — so if the record
    // shows up, it's real). So on a timeout specifically, poll the email a
    // few times before deciding it actually failed.
    function reconcileAfterTimeout(emailId, attemptsLeft) {
        const deferred = $.Deferred();
        attemptsLeft = attemptsLeft === undefined ? 6 : attemptsLeft;

        $.getJSON("/api/emails/" + emailId + "/")
            .done(function (email) {
                if (email.is_processed && email.record_id) {
                    deferred.resolve({ success: true, recordId: email.record_id, usedAttachment: null });
                } else if (email.is_processed) {
                    deferred.resolve({ success: false, error: "Extraction finished but produced no draft." });
                } else if (attemptsLeft > 0) {
                    setTimeout(function () {
                        reconcileAfterTimeout(emailId, attemptsLeft - 1).done(deferred.resolve);
                    }, 5000);
                } else {
                    deferred.resolve({ success: false, error: "Timed out — still not finished after extra waiting." });
                }
            })
            .fail(function () {
                deferred.resolve({ success: false, error: "Timed out (and couldn't confirm final status)." });
            });

        return deferred.promise();
    }

    function extractOne(emailId, templateId, attachmentId) {
        const deferred = $.Deferred();
        const payload = { template: templateId };
        if (attachmentId) payload.attachment = attachmentId;

        $.ajax({
            url: "/api/emails/" + emailId + "/extract/",
            type: "POST",
            contentType: "application/json",
            data: JSON.stringify(payload),
            timeout: EXTRACT_TIMEOUT_MS,
        })
            .done(function (resp) {
                deferred.resolve({
                    success: true, recordId: resp.record_id, usedAttachment: resp.used_attachment,
                });
            })
            .fail(function (xhr) {
                if (xhr.statusText === "timeout" || xhr.status === 0) {
                    reconcileAfterTimeout(emailId).done(deferred.resolve);
                    return;
                }
                const msg =
                    (xhr.responseJSON && (xhr.responseJSON.detail || JSON.stringify(xhr.responseJSON))) ||
                    "Extraction failed.";
                deferred.resolve({ success: false, error: msg });
            });

        return deferred.promise();
    }

    $modalConfirm.on("click", function () {
        const emailId = pendingEmailId;
        const templateId = $modalSelect.val();
        const attachmentId = $sourceSelect.val();
        if (!emailId || !templateId) return;

        const $btn = $(this).prop("disabled", true).text("Extracting… ~20s");
        $("#extract-modal-cancel").prop("disabled", true);

        extractOne(emailId, templateId, attachmentId).done(function (result) {
            if (result.success) {
                window.showToast(
                    result.usedAttachment ? "Draft created from " + result.usedAttachment + "." : "Draft created.",
                    "success"
                );
                window.location.href = "/review/" + result.recordId + "/";
            } else {
                window.showToast(result.error, "warning");
                $btn.prop("disabled", false).text("Run extraction →");
                $("#extract-modal-cancel").prop("disabled", false);
            }
        });
    });

    // --- Batch extraction: fixed concurrency, hard cap on selection -------- //
    // No queue/worker infrastructure — this is just the browser firing the
    // same /extract/ endpoint N times, at most BATCH_CONCURRENCY in flight at
    // once. Ollama serves one generation at a time on typical hardware, so a
    // higher fixed cap here just controls request overlap, not a promise of
    // parallel speedup.
    const $batchModal = $("#batch-extract-modal");
    const $batchCopy = $("#batch-modal-copy");
    const $batchTemplate = $("#batch-modal-template");
    const $batchList = $("#batch-modal-list");
    const $batchSummary = $("#batch-modal-summary");
    const $batchRunBtn = $("#batch-modal-run");
    const $batchStopBtn = $("#batch-modal-stop");
    const $batchDoneBtn = $("#batch-modal-done");
    const $batchCancelBtn = $("#batch-modal-cancel");
    let batchItems = []; // [{id, attachmentId, subject}]
    let batchStopRequested = false;

    function classifyForBatch(email) {
        const attachments = email.attachments || [];
        if (attachments.length <= 1) {
            return {
                runnable: true,
                attachmentId: attachments.length === 1 ? attachments[0].id : null,
                tag: attachments.length === 1 ? "via " + attachments[0].filename : "",
            };
        }
        return { runnable: false, attachmentId: null, tag: attachments.length + " attachments — extract individually" };
    }

    function batchRowHtml(email, classification) {
        const style = classification.runnable
            ? ""
            : " opacity:.5;";
        return (
            '<div class="batch-item" data-id="' + email.id + '" style="display:flex;align-items:center;gap:10px;' +
            'padding:10px 14px;border-bottom:1px solid var(--rule);font:11px var(--mono);' + style + '">' +
            '<span class="batch-item-status" style="width:16px;text-align:center;flex:0 0 auto;">' +
            (classification.runnable ? "—" : "✕") + "</span>" +
            '<span style="flex:1;min-width:0;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;">' +
            escapeHtml(email.subject || "(no subject)") + "</span>" +
            '<span class="hint" style="flex:0 0 auto;">' + escapeHtml(classification.tag) + "</span>" +
            "</div>"
        );
    }

    function openBatchModal() {
        if (!selectedIds.length) return;
        batchStopRequested = false;
        batchItems = [];

        const rowsHtml = selectedIds.map(function (id) {
            const email = emailsById[id];
            const classification = classifyForBatch(email);
            if (classification.runnable) {
                batchItems.push({ id: id, attachmentId: classification.attachmentId });
            }
            return batchRowHtml(email, classification);
        }).join("");

        $batchList.html(rowsHtml);
        const excludedCount = selectedIds.length - batchItems.length;

        if (!batchItems.length) {
            $batchCopy.html(
                "None of the " + selectedIds.length + " selected email(s) can be batch-extracted — they all have " +
                "multiple attachments needing an individual choice. Use each row's own <strong>Extract →</strong> instead."
            );
        } else {
            $batchCopy.html(
                "This will run extraction on <strong>" + batchItems.length + "</strong> email(s)" +
                (excludedCount ? " (" + excludedCount + " excluded — see below)" : "") +
                " using the template below, up to " + BATCH_CONCURRENCY + " at a time."
            );
        }

        $batchSummary.text("");
        $("#batch-modal-progress-row").hide();
        $("#batch-modal-progress-fill").css("width", "0%");
        $batchRunBtn.prop("disabled", !batchItems.length).text("Run extraction (" + batchItems.length + ") →").show();
        $batchStopBtn.hide();
        $batchDoneBtn.hide();
        $batchCancelBtn.show().prop("disabled", false).text("Cancel");
        $batchTemplate.prop("disabled", false);

        $batchModal.addClass("is-open");
    }

    function closeBatchModal() {
        if (batchRunning) return; // must Stop first
        $batchModal.removeClass("is-open");
    }

    $("#batch-open-btn").on("click", openBatchModal);
    $batchCancelBtn.on("click", closeBatchModal);
    $batchModal.on("click", function (e) {
        if (e.target === this) closeBatchModal();
    });

    function setItemStatus(emailId, state) {
        const $item = $batchList.find('.batch-item[data-id="' + emailId + '"]');
        const $status = $item.find(".batch-item-status");
        $item.removeClass("is-processing is-done");

        if (state === "processing") {
            $status.html('<span class="spinner"></span>');
            $item.addClass("is-processing");
        } else if (state === "success") {
            $status.text("✓");
            $item.addClass("is-done");
        } else if (state === "fail") {
            $status.text("✗");
            $item.addClass("is-done");
        } else {
            $status.text("—");
        }
    }

    function runBatchQueue(items, templateId) {
        const total = items.length;
        let idx = 0;
        let active = 0;
        let settled = 0;
        let succeeded = 0;
        let failed = 0;

        function updateSummary() {
            $batchSummary.text(settled + "/" + total + " done · " + succeeded + " succeeded · " + failed + " failed");
            $("#batch-modal-progress-fill").css("width", (total ? (settled / total) * 100 : 0) + "%");
        }

        function pump(onAllDone) {
            if (settled === total) { onAllDone(); return; }
            if (batchStopRequested && active === 0) { onAllDone(); return; }

            while (!batchStopRequested && active < BATCH_CONCURRENCY && idx < total) {
                const item = items[idx++];
                active++;
                setItemStatus(item.id, "processing");
                extractOne(item.id, templateId, item.attachmentId).done(function (result) {
                    active--; settled++;
                    if (result.success) {
                        succeeded++;
                        setItemStatus(item.id, "success");
                    } else {
                        failed++;
                        setItemStatus(item.id, "fail");
                        $batchList
                            .find('.batch-item[data-id="' + item.id + '"]')
                            .attr("title", result.error);
                    }
                    updateSummary();
                    pump(onAllDone);
                });
            }
        }

        return new Promise(function (resolve) {
            updateSummary();
            pump(resolve);
        });
    }

    $batchRunBtn.on("click", function () {
        const templateId = $batchTemplate.val();
        if (!batchItems.length || !templateId) return;

        batchRunning = true;
        batchStopRequested = false;
        $batchRunBtn.hide();
        $batchCancelBtn.hide();
        $batchTemplate.prop("disabled", true);
        $batchStopBtn.show().prop("disabled", false).text("Stop");
        $("#batch-modal-progress-row").show();

        runBatchQueue(batchItems, templateId).then(function () {
            batchRunning = false;
            $batchStopBtn.hide();
            $batchDoneBtn.show();
            $batchCancelBtn.show().prop("disabled", false).text("Close");
            loadEmails();
        });
    });

    $batchStopBtn.on("click", function () {
        batchStopRequested = true;
        $(this).prop("disabled", true).text("Stopping…");
    });

    $batchDoneBtn.on("click", function () {
        $batchModal.removeClass("is-open");
        window.location.href = "/review/";
    });

    $(document).on("keydown", function (e) {
        if (e.key !== "Escape") return;
        if ($modal.hasClass("is-open")) closeExtractModal();
        if ($batchModal.hasClass("is-open")) closeBatchModal();
    });

    window.addEventListener("beforeunload", function (e) {
        if (batchRunning) {
            e.preventDefault();
            e.returnValue = "";
        }
    });

    // --- Filters / misc ----------------------------------------------------- //
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
        window.showToast("Run 'fetch_emails' from the terminal, or wait for the scheduled poll.", "default");
    });

    loadEmails();
})(jQuery);
