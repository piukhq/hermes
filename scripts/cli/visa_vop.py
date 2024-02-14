import json
from typing import TYPE_CHECKING

import requests
from django.conf import settings
from tqdm import tqdm

from payment_card.models import VopMerchantGroup
from scheme.models import Scheme
from ubiquity.models import PaymentCardSchemeEntry, VopActivation

if TYPE_CHECKING:
    from django.core.management.base import OutputWrapper


class MerchantVisaVOPActivation:
    headers = {"Authorization": f"Token {settings.SERVICE_API_KEY}"}

    def __init__(
        self, stdout: "OutputWrapper", *, scheme_slug: str, use_default: bool, group_name: str | None, log_path: str
    ) -> None:
        self.log_path = log_path
        self.stdout = stdout
        self.succeeded: int = 0
        self.failed: int = 0
        self.scheme = Scheme.objects.get(slug=scheme_slug)
        self.payment_cards_ids = (
            PaymentCardSchemeEntry.objects.values_list("payment_card_account_id", flat=True)
            .filter(
                payment_card_account__payment_card__slug="visa",
                scheme_account__scheme_id=self.scheme.id,
                active_link=True,
            )
            .all()
        )

        match use_default, group_name:
            case True, _:
                self.merchant_group = VopMerchantGroup.cached_group_lookup(None)
            case False, None:
                self.merchant_group = VopMerchantGroup.cached_group_lookup(self.scheme.vop_merchant_group_id)
            case False, group_name:
                self.merchant_group = VopMerchantGroup.objects.get(group_name=group_name)

    def run_deactivations(self) -> None:
        activations = VopActivation.objects.select_related("payment_card_account").filter(
            payment_card_account_id__in=self.payment_cards_ids,
            scheme=self.scheme,
            status=VopActivation.ACTIVATED,
        )
        self.stdout.write(f"Deactivating {activations.count()} activations")

        with open(self.log_path, "w") as f:
            for activation in tqdm(activations.all()):
                resp = requests.post(
                    settings.METIS_URL + "/visa/deactivate/",
                    json={
                        "payment_token": activation.payment_card_account.psp_token,
                        "partner_slug": "visa",
                        "offer_id": self.merchant_group.offer_id,
                        "activation_id": activation.activation_id,
                        "id": activation.payment_card_account.id,
                    },
                    headers=self.headers,
                )
                if resp.status_code == 201:
                    activation.status = VopActivation.DEACTIVATED
                    activation.save(update_fields=["status"])
                    self.succeeded += 1
                else:
                    print(
                        f"Activation {activation.id} failed to deactivate, "
                        f"reason:\n{json.dumps(resp.json(), indent=4)}",
                        file=f,
                    )
                    self.failed += 1

        self.stdout.write(f"{self.succeeded} deactivations succeeded")
        if self.failed:
            self.stdout.write(f"{self.failed} deactivations failed, please check {self.log_path} for details")

    def run_activations(self) -> None:
        activations = VopActivation.objects.select_related("payment_card_account").filter(
            payment_card_account_id__in=self.payment_cards_ids,
            scheme=self.scheme,
            status=VopActivation.DEACTIVATED,
        )
        self.stdout.write(f"Activating {activations.count()} activations")
        with open(self.log_path, "w") as f:
            for activation in tqdm(activations.all()):
                resp = requests.post(
                    settings.METIS_URL + "/visa/activate/",
                    json={
                        "payment_token": activation.payment_card_account.psp_token,
                        "partner_slug": "visa",
                        "offer_id": self.merchant_group.offer_id,
                        "merchant_group": self.merchant_group.group_name,
                        "merchant_slug": self.scheme.slug,
                        "id": activation.payment_card_account.id,
                    },
                    headers=self.headers,
                )

                if resp.status_code == 201:
                    activation.activation_id = resp.json()["activation_id"]
                    activation.status = VopActivation.ACTIVATED
                    activation.save(update_fields=["status", "activation_id"])
                    self.succeeded += 1
                else:
                    print(
                        f"Activation {activation.id} failed to activate, reason:\n{json.dumps(resp.json(), indent=4)}",
                        file=f,
                    )
                    self.failed += 1

        self.stdout.write(f"{self.succeeded} activations succeeded")
        if self.failed:
            self.stdout.write(f"{self.failed} activations failed, please check {self.log_path} for details")


def run_deactivations_by_scheme_slug(
    stdout: "OutputWrapper", scheme_slug: str, use_default: bool, group_name: str | None, log_path: str
) -> None:
    MerchantVisaVOPActivation(
        stdout,
        scheme_slug=scheme_slug,
        use_default=use_default,
        group_name=group_name,
        log_path=log_path,
    ).run_deactivations()


def run_activations_by_scheme_slug(
    stdout: "OutputWrapper", scheme_slug: str, use_default: bool, group_name: str | None, log_path: str
) -> None:
    MerchantVisaVOPActivation(
        stdout,
        scheme_slug=scheme_slug,
        use_default=use_default,
        group_name=group_name,
        log_path=log_path,
    ).run_activations()
