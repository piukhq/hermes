import arrow
from payment_card.enums import RequestMethod
from payment_card.tasks import metis_request
from time import sleep
from .models import ScriptResult
from .scripts import DataScripts, SCRIPT_TITLES
from django.core.exceptions import ObjectDoesNotExist


def delete_metis_callback():
    try:
        s_obj = ScriptResult.objects.get(item_id=999, script_name=SCRIPT_TITLES[DataScripts.METIS_CALLBACK])
        s_obj.delete()
    except ObjectDoesNotExist:
        pass


def get_metis_callback():
    try:
        s_obj = ScriptResult.objects.get(item_id=999, script_name=SCRIPT_TITLES[DataScripts.METIS_CALLBACK])
        return s_obj.data
    except ObjectDoesNotExist:
        return None


def get_card_data(entry):
    return {
        'payment_token': entry.data['payment_token'],
        'card_token': entry.data['card_token'],
        'partner_slug': entry.data['partner_slug'],
        'id': 999,
        'date': arrow.utcnow().timestamp
    }


def get_metis_result(method, data):
    args = (
        RequestMethod.DELETE,
        '/payment_service/payment_card',
        data,
    )
    metis_request(*args)
    waiting_rely = True
    result = {}
    while waiting_rely:
        sleep(1)
        result = get_metis_callback()
        if result:
            waiting_rely = False
    return result


def do_un_eroll(entry):
    delete_metis_callback()
    data = get_card_data(entry)
    data['activations'] = {}
    result = get_metis_result(requestMethod.DELETE, data)
    if result.get('response_status', "") == 'Delete:SUCCESS':
        return True
    return False


def do_deactivate(entry):

    return True


def do_re_enroll(entry):
    # This is a re-enrol for purposes of removing activations or ensuring an un-enrol
    # create duplicate data for call back account
    delete_metis_callback()
    result = get_metis_result(RequestMethod.POST, get_card_data(entry))
    if result.get('response_status', "") == 'Add:SUCCESS':
        return True
    return False


def do_transfer_activation(entry):
    return True


def do_mark_as_deactivated(entry):
    return True
