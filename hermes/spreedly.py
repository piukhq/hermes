import logging

import requests
from django.conf import settings

from ubiquity.channel_vault import SecretKeyName, get_secret_key


class SpreedlyError(Exception):
    UNSUCCESSFUL_RESPONSE = "Spreedly has responded with unsuccessful purchase"


class Spreedly:
    payment_purchase_url = "{}/v1/gateways/{gateway_token}/purchase.json"
    payment_void_url = "{}/v1/transactions/{transaction_token}/void.json"

    def __init__(
        self,
        environment_key: str,
        access_secret: str,
        currency_code: str = "GBP",
        base_url: str = settings.SPREEDLY_BASE_URL,
    ):

        self.base_url = base_url
        self.environment_key = environment_key
        self.access_secret = access_secret
        self.currency_code = currency_code

        self.purchase_resp = None
        self.void_resp = None
        self.transaction_token = ""

    def purchase(self, payment_token: str, amount: int, order_id: str, gateway_token: str = None) -> None:

        if gateway_token is None:
            gateway_token = get_secret_key(SecretKeyName.SPREEDLY_GATEWAY_TOKEN)

        payload = {
            "transaction": {
                "payment_method_token": payment_token,
                "amount": amount,
                "currency_code": self.currency_code,
                "order_id": order_id,
            }
        }
        try:
            resp = requests.post(
                self.payment_purchase_url.format(self.base_url, gateway_token=gateway_token),
                json=payload,
                auth=(self.environment_key, self.access_secret),
            )
            if not resp.ok:
                raise SpreedlyError(f"Error response received from Spreedly - status code: {resp.status_code}")

            self.purchase_resp = resp.json()
            if not self.purchase_resp["transaction"]["succeeded"]:
                resp_msg = self.purchase_resp["transaction"]["response"].get(
                    "message", "no 'message' key present in response"
                )
                logging.exception(f"Payment error - Spreedly response message: {resp_msg}")
                raise SpreedlyError(SpreedlyError.UNSUCCESSFUL_RESPONSE)

            self.transaction_token = self.purchase_resp["transaction"]["token"]

        except requests.RequestException as e:
            raise SpreedlyError("Error with purchase request to Spreedly") from e
        except KeyError as e:
            raise SpreedlyError("Error with purchase response format") from e

    def void(self, transaction_token: str) -> None:
        try:
            resp = requests.post(
                self.payment_void_url.format(self.base_url, transaction_token=transaction_token),
                auth=(self.environment_key, self.access_secret),
            )

            if not resp.ok:
                raise SpreedlyError(f"Error response received from Spreedly - status code: {resp.status_code}")

            self.void_resp = resp.json()
            if not self.void_resp["transaction"]["succeeded"]:
                message = "Payment void error - response: {}".format(self.void_resp["transaction"]["response"])
                logging.exception(message)
                raise SpreedlyError("Spreedly has responded with unsuccessful void")
        except requests.RequestException as e:
            raise SpreedlyError("Error voiding payment with Spreedly") from e
        except KeyError as e:
            raise SpreedlyError("Error with void response format") from e
