from celery import shared_task


def vop_enroll(entries, set_status, activated_state):
    for entry in entries:
        entry.vop_link = set_status
        entry.save()

        data = {
            'payment_token': entry.payment_card_account.psp_token,
            'merchant_slug': entry.scheme_account.scheme.slug,
            'association_id': entry.id,
            'payment_card_account_id': entry.payment_card_account.id,
            'scheme_account_id': entry.scheme_account.id
        }

        send_activation.delay(entry, data)


@shared_task
def send_activation(entry, data, activated_state):
    rep = requests.post(settings.METIS_URL + '/visa/activate/',
                        json=data,
                        headers={'Authorization': 'Token {}'.format(settings.SERVICE_API_KEY),
                                 'Content-Type': 'application/json'})
    if rep.status_code == 201:
        reply = rep.json()
        if reply.get('status') == 'activated':
            entry.vop_link = activated_state
            entry.save()
