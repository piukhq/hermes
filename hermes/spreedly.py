import logging

import requests
from django.conf import settings

class SpreedlyError(Exception):
    pass


class Spreedly:
    payment_auth_url = "{}/v1/gateways/{gateway_token}/authorize.json"
    payment_void_url = "{}/v1/transactions/{transaction_token}/void.json"

    def __init__(self, environment_key: str, access_secret: str, currency_code: str = 'GBP'):
        self.environment_key = environment_key
        self.access_secret = access_secret
        self.currency_code = currency_code

        self.auth_resp = None
        self.void_resp = None
        self.transaction_token = None

    def authorise(self, payment_token: str, amount: int, order_id: str, gateway_token) -> None:
        payload = {
            "transaction": {
                "payment_method_token": payment_token,
                "amount": amount,
                "currency_code": self.currency_code,
                "order_id": order_id
            }
        }
        try:
            resp = requests.post(
                self.payment_auth_url.format(settings.SPREEDLY_BASE_URL, gateway_token=gateway_token),
                json=payload,
                auth=(self.environment_key, self.access_secret)
            )
            self.auth_resp = resp.json()
            if not self.auth_resp['transaction']['succeeded']:
                message = "Payment authorisation error - response: {}".format(
                    self.auth_resp['transaction']['response']
                )
                logging.error(message)
                raise SpreedlyError("Spreedly has responded with unsuccessful auth")

            self.transaction_token = self.auth_resp['transaction']['token']

        except requests.RequestException as e:
            raise SpreedlyError("Error authorising payment with Spreedly") from e
        except KeyError as e:
            raise SpreedlyError("Error with auth response format") from e

    def void(self, transaction_token: str) -> None:
        try:
            resp = requests.post(
                self.payment_void_url.format(settings.SPREEDLY_BASE_URL, transaction_token=transaction_token),
                auth=(self.environment_key, self.access_secret)
            )

            self.void_resp = resp.json()
            if not self.void_resp['transaction']['succeeded']:
                message = "Payment void error - response: {}".format(
                    self.void_resp['transaction']['response']
                )
                logging.error(message)
                raise SpreedlyError("Spreedly has responded with unsuccessful void")
        except requests.RequestException as e:
            raise SpreedlyError("Error voiding payment with Spreedly") from e
        except KeyError as e:
            raise SpreedlyError("Error with void response format") from e
