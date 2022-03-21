from django.contrib.admin.apps import AdminConfig


class AADAdminConfig(AdminConfig):
    default_site = "sso.admin.AADAdminSite"
