from azure.storage.blob import BlobServiceClient
from django.conf import settings

from ..tasks.process_hash import process_files
from .base_script import BaseScript


class BarclaysHashCorrectionsUpload(BaseScript):
    def script(self):
        try:
            blob_service_client = BlobServiceClient.from_connection_string(settings.AZURE_CONNECTION_STRING)
            container_client = blob_service_client.get_container_client(settings.UPLOAD_CONTAINER_NAME)

            # List the blobs in the container
            blob_list = container_client.list_blobs(name_starts_with="barclays/hash/hash-files/")
            file_list = []
            for blob in blob_list:
                file_list.append(blob.name)
            if container_client:
                self.result.append("Files found to process in Background\n\t")
                self.result.append("\n\t".join(file_list))
                process_files.delay(file_list)
            else:
                self.result.append("Did not access Azure Container\n")

        except Exception as ex:
            self.result.append(f"Failed Exception Occurred {ex}\n")
