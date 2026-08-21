(function ($) {
    "use strict";

    const $app = $("#template-app");
    const templateId = $app.data("template-id");
    const rowTemplate = $("#field-row-template").html();

    let fieldIndex = 0;
    let detectedFilename = "";

    function renderFieldRow(field) {
        field = field || {
            name: "",
            label: "",
            data_type: "string",
            required: false,
        };
        let html = rowTemplate
            .replace(/__INDEX__/g, fieldIndex)
            .replace("__NAME__", escapeHtml(field.name))
            .replace("__LABEL__", escapeHtml(field.label))
            .replace("__CHECKED__", field.required ? "checked" : "");

        ["string", "integer", "number", "date", "boolean"].forEach(function (t) {
            html = html.replace(
                "__SEL_" + t.toUpperCase() + "__",
                field.data_type === t ? "selected" : ""
            );
        });

        $("#fields-tbody").append(html);
        fieldIndex += 1;
    }

    function escapeHtml(str) {
        return $("<div>").text(str || "").html();
    }

    function collectFields() {
        const fields = [];
        $("#fields-tbody tr").each(function (order) {
            const $row = $(this);
            const name = $row.find(".f-name").val().trim();
            if (!name) return;
            fields.push({
                name: name,
                label: $row.find(".f-label").val().trim() || name,
                data_type: $row.find(".f-type").val(),
                required: $row.find(".f-required").is(":checked"),
                description: "",
                ai_instruction: "",
                display_order: order + 1,
            });
        });
        return fields;
    }

    if (templateId) {
        $.getJSON("/api/templates/" + templateId + "/").done(function (tpl) {
            $("#tpl-name").val(tpl.name);
            $("#tpl-description").val(tpl.description);
            $("#tpl-active").prop("checked", tpl.is_active);
            detectedFilename = tpl.source_file || "";
            $("#source-file-label").text(detectedFilename || "—");
            $("#fields-tbody").empty();
            tpl.fields.forEach(renderFieldRow);
        });
    }

    $("#add-field-btn").on("click", function () {
        renderFieldRow();
    });

    $("#fields-tbody").on("click", ".remove-field-btn", function () {
        $(this).closest("tr").remove();
    });

    $("#detect-btn").on("click", function () {
        const fileInput = $("#tpl-file")[0];
        if (!fileInput.files.length) {
            $("#detect-status").text("Choose a file first.").addClass("error");
            return;
        }

        const formData = new FormData();
        formData.append("file", fileInput.files[0]);

        $("#detect-status").text("Detecting columns…").removeClass("error");

        $.ajax({
            url: "/api/templates/detect-columns/",
            type: "POST",
            data: formData,
            processData: false,
            contentType: false,
        })
            .done(function (resp) {
                $("#fields-tbody").empty();
                fieldIndex = 0;
                resp.columns.forEach(renderFieldRow);
                detectedFilename = resp.filename;
                $("#source-file-label").text(detectedFilename);
                $("#detect-status")
                    .text(
                        "Detected " +
                            resp.columns.length +
                            " column(s) from " +
                            resp.filename +
                            ". Review and adjust below."
                    )
                    .removeClass("error");
            })
            .fail(function (xhr) {
                const msg =
                    (xhr.responseJSON && xhr.responseJSON.detail) || "Detection failed.";
                $("#detect-status").text(msg).addClass("error");
            });
    });

    $("#save-btn").on("click", function () {
        const payload = {
            name: $("#tpl-name").val().trim(),
            description: $("#tpl-description").val().trim(),
            is_active: $("#tpl-active").is(":checked"),
            source_file: detectedFilename,
            fields: collectFields(),
        };

        if (!payload.name) {
            $("#save-status").text("Template name is required.").addClass("error");
            return;
        }
        if (!payload.fields.length) {
            $("#save-status").text("Add at least one field.").addClass("error");
            return;
        }

        const isEdit = !!templateId;
        const url = isEdit ? "/api/templates/" + templateId + "/" : "/api/templates/";
        const method = isEdit ? "PUT" : "POST";

        $("#save-status").text("Saving…").removeClass("error");

        $.ajax({
            url: url,
            type: method,
            contentType: "application/json",
            data: JSON.stringify(payload),
        })
            .done(function () {
                window.location.href = "/templates/";
            })
            .fail(function (xhr) {
                const msg =
                    (xhr.responseJSON && JSON.stringify(xhr.responseJSON)) ||
                    "Save failed.";
                $("#save-status").text(msg).addClass("error");
            });
    });

    if (!templateId) {
        renderFieldRow();
    }
})(jQuery);
