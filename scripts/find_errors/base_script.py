from uuid import uuid4

from scripts.actions.corrections import Correction
from scripts.models import ScriptResult


class BaseScript:
    def __init__(self, script_id, script_name):
        self.script_id = script_id
        self.script_name = script_name
        self._correction_titles = dict(Correction.CORRECTION_SCRIPTS)
        self.result = []
        self.correction_count = 0
        self.new_corrections = 0
        self.found = 0
        self.correction_function = Correction.NO_CORRECTION
        self._sequence = []
        self.summary = ""
        self.script_run_uid = uuid4()

    def script(self):
        """
        Overlay this method with your script

        """
        pass

    def run(self):
        try:
            self.script()
            if not self.summary:
                self.summary = f"Found {self.found} Issues and added {self.new_corrections} correction_count"
        except BaseException as e:
            self.summary = f"Exception {e}"
        return self.summary, self.correction_count, "<br/>".join(self.result)

    def make_correction(self, unique_id_string, data):
        unique_ref = f"{unique_id_string}.{self.script_id}"

        all_corrections = Correction.COMPOUND_CORRECTION_SCRIPTS
        self._sequence = all_corrections.get(self.correction_function, [self.correction_function])

        data["script_id"] = self.script_id
        data["sequence"] = self._sequence
        data["sequence_pos"] = 0
        sr, created = ScriptResult.objects.get_or_create(
            item_id=unique_ref,
            script_name=self.script_name,
            defaults={
                "data": data,
                "apply": self._sequence[0],
                "correction": self.correction_function,
                "script_run_uid": self.script_run_uid,
            },
        )
        self.correction_count += 1
        if created:
            self.new_corrections += 1

    def set_correction(self, correction_function):
        self.correction_function = correction_function

    @property
    def correction_title(self):
        return self._correction_titles[self.correction_function]
