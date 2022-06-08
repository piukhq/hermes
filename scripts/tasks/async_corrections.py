from celery import shared_task

from ..actions.corrections import Correction


@shared_task()
def background_corrections(queryset: object):

    for entry in queryset:
        if not entry.done:
            title = Correction.TITLES[entry.apply]
            success = Correction.do(entry)
            if success:
                sequence = entry.data["sequence"]
                sequence_pos = entry.data["sequence_pos"] + 1
                entry.results.append(f"{title}: success")
                if sequence_pos >= len(sequence):
                    entry.done = True
                    entry.apply = Correction.NO_CORRECTION

                else:
                    entry.data["sequence_pos"] = sequence_pos
                    entry.apply = sequence[sequence_pos]
            else:
                entry.results.append(f"{title}: failed")
            entry.save()
