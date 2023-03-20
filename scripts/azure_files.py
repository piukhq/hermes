from collections.abc import Callable
from datetime import datetime

from azure.storage.blob import BlobServiceClient
from django.conf import settings


def upload_files_and_process(correction_script: object, location: str, func: Callable[[dict], None]) -> list:
    results = []
    try:
        blob_service_client = BlobServiceClient.from_connection_string(settings.AZURE_CONNECTION_STRING)
        container_client = blob_service_client.get_container_client(settings.UPLOAD_CONTAINER_NAME)

        # List the blobs in the container
        blob_list = container_client.list_blobs(name_starts_with=location)
        file_list = []
        results.append("The following files were discovered on Azure and will be process in background:")
        for blob in blob_list:
            file_list.append(blob.name)
            results.append(f"&nbsp;&nbsp;&nbsp;&nbsp;{blob.name}")
        if container_client:
            func.delay(correction_script, file_list)
        else:
            results.append(f"Could not find/access Azure Container {settings.UPLOAD_CONTAINER_NAME}")

    except Exception as ex:
        results.append(f"Failed Exception Occurred {ex}\n")

    return results


def process_files(correction_script: object, file_list: list, type_dir: str, func: Callable[[list, int], list, int]):
    now = datetime.now()
    now_str = now.strftime("%H%M")
    date_str = now.strftime("%Y/%m/%d/")
    blob_service_client = BlobServiceClient.from_connection_string(settings.AZURE_CONNECTION_STRING)
    container_client = blob_service_client.get_container_client(settings.UPLOAD_CONTAINER_NAME)
    archive_client = blob_service_client.get_container_client(settings.ARCHIVE_CONTAINER_NAME)
    item_no = 0
    for upload_file in file_list:
        line_no = 0
        archive_file = date_str + upload_file.replace(type_dir, f"processed_{now_str}/imported/")
        bytes_io = container_client.download_blob(upload_file).readall()
        archive_client.get_blob_client(archive_file).upload_blob(bytes_io)
        contents = str(bytes_io, "utf-8").split("\n")

        failures, item_no = func(correction_script, upload_file, contents, item_no)

        if failures:
            failed_file = archive_file.replace("imported/", "failures/failed_")
            data = "\n".join(failures)
            archive_client.get_blob_client(failed_file).upload_blob(data)
        else:
            success_file = archive_file.replace("imported/", "success/success_")
            data = f'{upload_file},{line_no},{item_no},"all read in for corrections"\n'
            archive_client.get_blob_client(success_file).upload_blob(data)
        # Now delete file from imports to archive:
        container_client.get_blob_client(upload_file).delete_blob()
