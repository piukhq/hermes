from enum import StrEnum


class FileScriptStatuses(StrEnum):
    READY = "READY"
    IN_PROGRESS = "IN_PROGRESS"
    DONE = "DONE"
