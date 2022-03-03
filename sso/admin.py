from django.conf import settings
from django.contrib import admin
from django.http import HttpResponse, HttpResponseRedirect
from django.urls import reverse
from django.views.decorators.cache import never_cache

class AADAdminSite(admin.AdminSite):
    @never_cache
    def login(self, request, extra_context=None):
        if settings.SSO_OFF:
            return super(AADAdminSite, self).login(request, extra_context)

        if request.method == "GET" and self.has_permission(request):
            # Already logged-in, redirect to admin index
            index_path = reverse("admin:index", current_app=self.name)
            return HttpResponseRedirect(index_path)

        if request.user.is_authenticated:
            return HttpResponse("Permission denied", status=403)

        return HttpResponseRedirect(reverse("oidc_authentication_init"))
