from django.http import HttpResponse


def permission_denied(request):
    return HttpResponse("Permission denied", status=403)
