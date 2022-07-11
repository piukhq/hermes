from ..azure_files import upload_files_and_process
from ..tasks.barclays_hash_tasks import process_barclays_delete_files, process_barclays_hash_files
from .base_script import BaseScript

SUMMARY = "Please wait will files are processed in Background"


class BarclaysHashCorrectionsUpload(BaseScript):
    def script(self):
        self.result = upload_files_and_process(self, "barclays/hash/hash-files/", process_barclays_hash_files)
        self.summary = SUMMARY


class BarclaysDeleteUpload(BaseScript):
    def script(self):
        self.result = upload_files_and_process(self, "barclays/hash/delete-files/", process_barclays_delete_files)
        self.summary = SUMMARY
