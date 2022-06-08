from ..azure_files import upload_files_and_process
from ..tasks.barclays_hash_tasks import process_barclays_delete_files, process_barclays_hash_files
from .base_script import BaseScript


class BarclaysHashCorrectionsUpload(BaseScript):
    def script(self):
        self.result.append(upload_files_and_process("barclays/hash/hash-files/", process_barclays_hash_files))


class BarclaysDeleteUpload(BaseScript):
    def script(self):
        self.result.append(upload_files_and_process("barclays/hash/delete-files/", process_barclays_delete_files))
