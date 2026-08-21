from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, render

from .models import Template


@login_required
def template_list(request):
    templates = Template.objects.filter(user=request.user).prefetch_related("fields")
    return render(request, "template/list.html", {"templates": templates})


@login_required
def template_create(request):
    return render(request, "template/form.html", {"template_id": None})


@login_required
def template_edit(request, pk):
    template = get_object_or_404(Template, pk=pk, user=request.user)
    return render(request, "template/form.html", {"template_id": template.pk})
