from os.path import join

from django.conf import settings
from storages.backends.azure_storage import AzureStorage


class CustomAzureStorage(AzureStorage):
    """Used to override the url of files to allow setting a custom domain for file access"""

    def url(self, name, expire=None, parameters=None):
        url = super().url(name, expire, parameters)
        _, path = url.split(settings.AZURE_CONTAINER)
        base_url = settings.CONTENT_URL

        return join(base_url, *path.split("/"))
