import csv
from io import BytesIO

from django.contrib.auth.decorators import login_required
from django.http import HttpResponse
from django.utils import timezone

from .exporters import build_table, get_records


def _filters(request):
    return dict(
        template_id=request.GET.get("template") or None,
        status=request.GET.get("status") or None,
        created_after=request.GET.get("created_after") or None,
        created_before=request.GET.get("created_before") or None,
    )


@login_required
def export_csv(request):
    headers, rows = build_table(get_records(request.user, **_filters(request)))
    stamp = timezone.now().strftime("%Y%m%d-%H%M")
    response = HttpResponse(content_type="text/csv")
    response["Content-Disposition"] = f'attachment; filename="records-{stamp}.csv"'
    writer = csv.writer(response)
    writer.writerow(headers)
    writer.writerows(rows)
    return response


@login_required
def export_xlsx(request):
    from openpyxl import Workbook

    headers, rows = build_table(get_records(request.user, **_filters(request)))

    wb = Workbook()
    ws = wb.active
    ws.title = "Records"
    ws.append(headers)
    for row in rows:
        ws.append(row)
    ws.freeze_panes = "A2"

    buffer = BytesIO()
    wb.save(buffer)
    buffer.seek(0)

    stamp = timezone.now().strftime("%Y%m%d-%H%M")
    response = HttpResponse(
        buffer.read(),
        content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )
    response["Content-Disposition"] = f'attachment; filename="records-{stamp}.xlsx"'
    return response
