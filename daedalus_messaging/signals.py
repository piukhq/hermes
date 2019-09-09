from django.db.models.signals import post_save
from django.dispatch import receiver
from django.contrib.admin.models import LogEntry
from hermes.settings import TO_DAEDALUS, ENABLE_DAEDALUS_MESSAGING


@receiver(post_save, sender=LogEntry)
def watch_for_admin_updates(sender, **kwargs):
    instance = kwargs.get("instance")
    if instance and ENABLE_DAEDALUS_MESSAGING:
        object_id = instance.object_id
        content_type = instance.content_type
        if content_type:
            model_saved = content_type.model
            model_action = instance.action_flag                 # 1 =  addition, 2 = change, 3 = Delete
            action_type = "admin_update"
            if model_action == 3:
                action_type = "admin_delete"
            model_rep = instance.object_repr
            TO_DAEDALUS.send({"type": action_type,
                              "model": model_saved,
                              "id": object_id,
                              "rep": model_rep},
                             headers={'X-content-type': 'application/json'}
                             )
