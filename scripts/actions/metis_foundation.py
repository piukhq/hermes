from django.conf import settings
from requests import request

from payment_card.enums import RequestMethod


def metis_foundation_request(method: RequestMethod, endpoint: str, payload: dict) -> object:
    response = request(
        method.value,
        settings.METIS_URL + endpoint,
        json=payload,
        headers={
            "Authorization": f"Token {settings.SERVICE_API_KEY}",
            "Content-Type": "application/json",
            "X-azure-ref": None,
        },
    )
    return response.json()
