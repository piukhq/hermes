from collections.abc import Callable, Generator
from dataclasses import dataclass
from typing import TYPE_CHECKING, Literal, NamedTuple, TypedDict
from unittest.mock import patch
from uuid import uuid4

import pytest
from pytest_mock import MockerFixture

from payment_card.enums import RequestMethod
from payment_card.models import PaymentCardAccount
from payment_card.tests.factories import PaymentCardAccountFactory, PaymentCardFactory
from scheme.models import SchemeAccount
from scheme.tests.factories import (
    SchemeAccountFactory,
    SchemeCredentialAnswerFactory,
    SchemeCredentialQuestionFactory,
    SchemeFactory,
)
from scripts.tasks.file_script_tasks.rtbf_tasks import _right_to_be_forgotten
from ubiquity.models import VopActivation
from ubiquity.tests.factories import (
    PaymentCardAccountEntryFactory,
    PaymentCardSchemeEntryFactory,
    PllUserAssociationFactory,
    SchemeAccountEntryFactory,
)
from user.models import CustomUser
from user.tests.factories import UserFactory

if TYPE_CHECKING:
    from payment_card.models import PaymentCard

    class PaymentSchemesType(TypedDict):
        visa: PaymentCard
        amex: PaymentCard
        mastercard: PaymentCard


@dataclass
class UserInput:
    email: str
    external_id: str


@dataclass
class PcardInput:
    name_on_card: str
    payment_scheme_slug: Literal["visa", "amex", "mastercard"]
    last_man_standing: bool = True


@dataclass
class McardInput:
    alt_main_answer: str
    scheme: str
    last_man_standing: bool = True


@dataclass
class ParametrizeInput:
    user: UserInput
    pcards: list[PcardInput]
    mcards: list[McardInput]


class WalletUserData(NamedTuple):
    model: CustomUser
    input_data: UserInput


class WalletPcardData(NamedTuple):
    model: PaymentCardAccount
    input_data: PcardInput
    activations: list[VopActivation]


class WalletMcardData(NamedTuple):
    model: SchemeAccount
    input_data: McardInput


@dataclass
class Wallet:
    user_data: WalletUserData
    pcards_data: list[WalletPcardData]
    mcards_data: list[WalletMcardData]


@pytest.fixture(autouse=True)
def stop_history_signals() -> Generator[None, None, None]:
    with patch("history.signals.record_history"):
        yield


@pytest.fixture()
def payment_schemes() -> "PaymentSchemesType":
    schemes: "PaymentSchemesType" = {
        "visa": PaymentCardFactory(slug="visa"),
        "amex": PaymentCardFactory(slug="amex"),
        "mastercard": PaymentCardFactory(slug="mastercard"),
    }

    return schemes


def _create_mcards(user: CustomUser, extra_user: CustomUser, mcards_data: list[McardInput]) -> list[WalletMcardData]:
    created_mcards: list[WalletMcardData] = []
    available_schemes = {}
    for mcard_data in mcards_data:
        if mcard_data.scheme not in available_schemes:
            _new_scheme = SchemeFactory(slug=mcard_data.scheme)
            question = SchemeCredentialQuestionFactory(scheme=_new_scheme)
            available_schemes[mcard_data.scheme] = _new_scheme, question

        scheme, question = available_schemes[mcard_data.scheme]
        mcard = SchemeAccountFactory(alt_main_answer=mcard_data.alt_main_answer, scheme=scheme)
        mcard_link = SchemeAccountEntryFactory(user=user, scheme_account=mcard)
        SchemeCredentialAnswerFactory(question=question, scheme_account_entry=mcard_link)
        created_mcards.append(WalletMcardData(mcard, mcard_data))

        if not mcard_data.last_man_standing:
            mcard_link = SchemeAccountEntryFactory(user=extra_user, scheme_account=mcard)
            SchemeCredentialAnswerFactory(question=question, scheme_account_entry=mcard_link)

    return created_mcards


def _create_pcards(
    user: CustomUser,
    extra_user: CustomUser,
    created_mcards: list[WalletMcardData],
    pcards_data: list[PcardInput],
    payment_schemes: "PaymentSchemesType",
) -> list[WalletPcardData]:
    created_pcards: list[WalletPcardData] = []
    for pcard_data in pcards_data:
        vop_activations = []
        pcard = PaymentCardAccountFactory(
            payment_card=payment_schemes[pcard_data.payment_scheme_slug], name_on_card=pcard_data.name_on_card
        )
        PaymentCardAccountEntryFactory(user=user, payment_card_account=pcard)

        if not pcard_data.last_man_standing:
            PaymentCardAccountEntryFactory(user=extra_user, payment_card_account=pcard)

        for mcard_to_link, mcard_data in created_mcards:
            if pcard_data.payment_scheme_slug == "visa":
                activation = VopActivation(
                    activation_id=str(uuid4()),
                    payment_card_account=pcard,
                    scheme=mcard_to_link.scheme,
                    status=VopActivation.ACTIVATED,
                )
                activation.save()
                vop_activations.append(activation)

            pll = PaymentCardSchemeEntryFactory(scheme_account=mcard_to_link, payment_card_account=pcard)
            PllUserAssociationFactory(user=user, pll=pll)

            if not (mcard_data.last_man_standing or pcard_data.last_man_standing):
                PllUserAssociationFactory(user=extra_user, pll=pll)

        created_pcards.append(WalletPcardData(pcard, pcard_data, vop_activations))

    return created_pcards


@pytest.fixture()
def setup_wallet(
    payment_schemes: "PaymentSchemesType",
) -> Generator[Callable[[ParametrizeInput], Wallet], None, None]:
    wallet: Wallet | None = None

    def _factory(init_data: ParametrizeInput) -> Wallet:
        nonlocal wallet

        user = UserFactory(email=init_data.user.email, external_id=init_data.user.external_id)
        extra_user = UserFactory()

        created_mcards = _create_mcards(user, extra_user, init_data.mcards)
        created_pcards = _create_pcards(user, extra_user, created_mcards, init_data.pcards, payment_schemes)

        wallet = Wallet(
            user_data=WalletUserData(user, init_data.user),
            pcards_data=created_pcards,
            mcards_data=created_mcards,
        )
        return wallet

    yield _factory

    if wallet:
        wallet.user_data.model.delete()

        for pcard, _, activations in wallet.pcards_data:
            for activation in activations:
                activation.delete()

            pcard.delete()

        for mcard, _ in wallet.mcards_data:
            mcard.delete()

        for scheme in payment_schemes.values():
            scheme.delete()


@pytest.mark.parametrize(
    ("starting_data",),
    (
        pytest.param(
            ParametrizeInput(
                user=UserInput(
                    email="test@email.com",
                    external_id="test external id",
                ),
                pcards=[
                    PcardInput(
                        name_on_card="test name on card",
                        payment_scheme_slug="visa",
                    ),
                ],
                mcards=[
                    McardInput(
                        alt_main_answer="test alt main answer",
                        scheme="test-scheme-1",
                    )
                ],
            ),
            id="1 mcard 1 visa pcard",
        ),
        pytest.param(
            ParametrizeInput(
                user=UserInput(
                    email="",
                    external_id="test external id",
                ),
                pcards=[
                    PcardInput(
                        name_on_card="test name on card",
                        payment_scheme_slug="mastercard",
                    ),
                ],
                mcards=[
                    McardInput(
                        alt_main_answer="test alt main answer",
                        scheme="test-scheme-1",
                    )
                ],
            ),
            id="1 mcard 1 mastercard pcard, no user email",
        ),
        pytest.param(
            ParametrizeInput(
                user=UserInput(
                    email="test@email.com",
                    external_id="",
                ),
                pcards=[
                    PcardInput(
                        name_on_card="test name on card 1",
                        payment_scheme_slug="amex",
                    ),
                    PcardInput(
                        name_on_card="test name on card 2",
                        payment_scheme_slug="visa",
                    ),
                ],
                mcards=[
                    McardInput(
                        alt_main_answer="test alt main answer",
                        scheme="test-scheme-1",
                    )
                ],
            ),
            id="1 mcard, 2 pcards (visa and amex), no external id",
        ),
        pytest.param(
            ParametrizeInput(
                user=UserInput(
                    email="test@email.com",
                    external_id="",
                ),
                pcards=[
                    PcardInput(
                        name_on_card="test name on card 1",
                        payment_scheme_slug="mastercard",
                    ),
                ],
                mcards=[
                    McardInput(
                        alt_main_answer="test alt main answer 1",
                        scheme="test-scheme-1",
                    ),
                    McardInput(
                        alt_main_answer="test alt main answer 2",
                        scheme="test-scheme-2",
                    ),
                ],
            ),
            id="2 mcards, 1 mastercard pcard",
        ),
        pytest.param(
            ParametrizeInput(
                user=UserInput(
                    email="test@email.com",
                    external_id="",
                ),
                pcards=[
                    PcardInput(
                        name_on_card="test name on card 1",
                        payment_scheme_slug="amex",
                    ),
                    PcardInput(
                        name_on_card="test name on card 2",
                        payment_scheme_slug="visa",
                    ),
                ],
                mcards=[
                    McardInput(
                        alt_main_answer="test alt main answer 1",
                        scheme="test-scheme-1",
                    ),
                    McardInput(
                        alt_main_answer="",
                        scheme="test-scheme-2",
                    ),
                ],
            ),
            id="2 mcards, 2 pcards (visa and amex), no alt_main_answer for one card",
        ),
        pytest.param(
            ParametrizeInput(
                user=UserInput(
                    email="test@email.com",
                    external_id="",
                ),
                pcards=[
                    PcardInput(
                        name_on_card="test name on card 1",
                        payment_scheme_slug="amex",
                        last_man_standing=False,
                    ),
                    PcardInput(
                        name_on_card="test name on card 2",
                        payment_scheme_slug="visa",
                    ),
                ],
                mcards=[
                    McardInput(
                        alt_main_answer="test alt main answer 1",
                        scheme="test-scheme-1",
                    ),
                    McardInput(
                        alt_main_answer="test alt main answer 2",
                        scheme="test-scheme-2",
                        last_man_standing=False,
                    ),
                ],
            ),
            id="2 mcards, 2 pcards (visa and amex), 1 pcard and 1 mcard linked in another wallet",
        ),
    ),
)
@pytest.mark.django_db
def test__right_to_be_forgotten(
    setup_wallet: Callable[[ParametrizeInput], Wallet],
    mocker: MockerFixture,
    starting_data: ParametrizeInput,
):
    test_entry_id = 0
    wallet = setup_wallet(starting_data)
    user, user_input = wallet.user_data

    mock_metis_request = mocker.patch("payment_card.metis.metis_request")
    _right_to_be_forgotten(str(user.id), test_entry_id, "0,test")

    # check user

    user.refresh_from_db()
    assert user.is_active is False
    assert not user.email or user.email != user_input.email
    assert not user.external_id or user.external_id != user_input.external_id
    assert user.delete_token is not None
    assert not hasattr(user, "profile")
    assert not hasattr(user, "serviceconsent")

    # check links to cards and pll
    assert user.plluserassociation_set.count() == 0
    assert user.scheme_account_set.count() == 0
    assert user.payment_card_account_set.count() == 0

    # check membership cards
    for mcard, mcard_input in wallet.mcards_data:
        mcard.refresh_from_db()

        if mcard_input.last_man_standing:
            assert not mcard.alt_main_answer or mcard.alt_main_answer != mcard_input.alt_main_answer
            assert mcard.is_deleted is True
            assert mcard.paymentcardschemeentry_set.count() == 0
            assert mcard.schemeaccountentry_set.count() == 0
        else:
            assert mcard.alt_main_answer == mcard_input.alt_main_answer
            assert mcard.is_deleted is False
            assert mcard.paymentcardschemeentry_set.count() == 1
            assert mcard.schemeaccountentry_set.count() == 1
            assert mcard.schemeaccountentry_set.filter(user=user).count() == 0

    expected_mocked_metis_calls = []

    # check payment cards
    for pcard, pcard_input, activations in wallet.pcards_data:
        pcard.refresh_from_db()

        if pcard_input.last_man_standing:
            assert not pcard.name_on_card or pcard.name_on_card != pcard_input.name_on_card
            assert pcard.is_deleted is True
            assert pcard.paymentcardschemeentry_set.count() == 0
            assert pcard.paymentcardaccountentry_set.count() == 0

            # VOP Activations
            for activation in activations:
                activation.refresh_from_db(fields=["status"])
                assert activation.status == VopActivation.DEACTIVATING

            expected_metis_call_payload = {
                "id": pcard.id,
                "payment_token": pcard.psp_token,
                "card_token": pcard.token,
                "partner_slug": pcard.payment_card.slug,
                "redact_only": False,
                "date": int(pcard.created.timestamp()),
            }
            if activations:
                expected_metis_call_payload["activations"] = {
                    act.id: {
                        "scheme": act.scheme.slug,
                        "activation_id": act.activation_id,
                    }
                    for act in activations
                }

            expected_mocked_metis_calls.append(
                mocker.call(
                    RequestMethod.POST,
                    "/payment_service/payment_card/unenrol_and_redact",
                    expected_metis_call_payload,
                    {
                        "X-Priority": 4,
                        "X-Azure-Ref": f"Triggered by django admin FileScript of id {test_entry_id}",
                    },
                )
            )
        else:
            assert pcard.name_on_card == pcard_input.name_on_card
            assert pcard.is_deleted is False
            assert pcard.paymentcardschemeentry_set.count() == 1
            assert pcard.paymentcardaccountentry_set.count() == 1
            assert pcard.paymentcardaccountentry_set.filter(user=user).count() == 0

    # check calls to metis
    def sort_key(call: mocker.call) -> int:
        return call.args[2]["id"]

    assert list(mock_metis_request.delay.mock_calls).sort(key=sort_key) == expected_mocked_metis_calls.sort(
        key=sort_key
    )
