from dataclasses import dataclass

USER_NAME = "username"
CARD_NUMBER = "card_number"
BARCODE = "barcode"
PASSWORD = "password"
PASSWORD_2 = "password_2"
PLACE_OF_BIRTH = "place_of_birth"
EMAIL = "email"
POSTCODE = "postcode"
MEMORABLE_DATE = "memorable_date"
PIN = "pin"
TITLE = "title"
FIRST_NAME = "first_name"
LAST_NAME = "last_name"
FAVOURITE_PLACE = "favourite_place"
DATE_OF_BIRTH = "date_of_birth"
PHONE = "phone"
PHONE_2 = "phone_2"
GENDER = "gender"
ADDRESS_1 = "address_1"
ADDRESS_2 = "address_2"
ADDRESS_3 = "address_3"
TOWN_CITY = "town_city"
COUNTY = "county"
COUNTRY = "country"
REGULAR_RESTAURANT = "regular_restaurant"
MERCHANT_IDENTIFIER = "merchant_identifier"
PAYMENT_CARD_HASH = "payment_card_hash"

CREDENTIAL_TYPES = (
    (USER_NAME, "user name"),
    (EMAIL, "email"),
    (CARD_NUMBER, "card number"),
    (BARCODE, "barcode"),
    (PASSWORD, "password"),
    (PASSWORD_2, "password 2"),
    (PLACE_OF_BIRTH, "place of birth"),
    (POSTCODE, "postcode"),
    (MEMORABLE_DATE, "memorable date"),
    (PIN, "pin"),
    (TITLE, "title"),
    (FIRST_NAME, "first name"),
    (LAST_NAME, "last name"),
    (FAVOURITE_PLACE, "favourite place"),
    (DATE_OF_BIRTH, "date_of_birth"),
    (PHONE, "phone number"),
    (PHONE_2, "phone number 2"),
    (GENDER, "gender"),
    (ADDRESS_1, "address 1"),
    (ADDRESS_2, "address 2"),
    (ADDRESS_3, "address 3"),
    (TOWN_CITY, "town city"),
    (COUNTY, "county"),
    (COUNTRY, "country"),
    (REGULAR_RESTAURANT, "regular restaurant"),
    (MERCHANT_IDENTIFIER, "merchant identifier"),
    (PAYMENT_CARD_HASH, "payment_card_hash"),
)

DATE_TYPE_CREDENTIALS = (MEMORABLE_DATE, DATE_OF_BIRTH)

ENCRYPTED_CREDENTIALS = (
    PASSWORD,
    POSTCODE,
    MEMORABLE_DATE,
    PLACE_OF_BIRTH,
    PIN,
    TITLE,
    FIRST_NAME,
    LAST_NAME,
    FAVOURITE_PLACE,
    DATE_OF_BIRTH,
    PHONE,
    PHONE_2,
    GENDER,
    ADDRESS_1,
    ADDRESS_2,
    ADDRESS_3,
    TOWN_CITY,
    COUNTY,
    COUNTRY,
    REGULAR_RESTAURANT,
)

CASE_SENSITIVE_CREDENTIALS = (
    USER_NAME,
    PASSWORD,
    PAYMENT_CARD_HASH,
    PIN,
    CARD_NUMBER,
    BARCODE,
    MERCHANT_IDENTIFIER,
)

credential_types_set = {credential_type[0] for credential_type in CREDENTIAL_TYPES}


@dataclass
class CredentialAnswers:
    """
    Holds credential answers and manages conversion between angelia and hermes formats

    A CredentialAnswers instance should be instantiated with credentials in the Angelia format e.g::

        join_credentials = [
            {"credential_slug": "email", "value": "hello@email.com"},
            {"credential_slug": "first_name", "value": "Bobby"},
        ]

        creds = CredentialAnswers(join=join_credentials)

        >>> creds.join
        {"email": "hello@email.com", "first_name": "Bobby"}

    """

    add: dict
    authorise: dict
    register: dict
    join: dict
    merchant: dict

    def __init__(
        self,
        add: list[dict] | None = None,
        authorise: list[dict] | None = None,
        register: list[dict] | None = None,
        join: list[dict] | None = None,
        merchant: list[dict] | None = None,
    ):
        self.add = self._credentials_to_key_pairs(add) if add else {}
        self.authorise = self._credentials_to_key_pairs(authorise) if authorise else {}
        self.register = self._credentials_to_key_pairs(register) if register else {}
        self.join = self._credentials_to_key_pairs(join) if join else {}
        self.merchant = self._credentials_to_key_pairs(merchant) if merchant else {}

    @staticmethod
    def _credentials_to_key_pairs(cred_list: list[dict]) -> dict:
        ret = {}
        for item in cred_list:
            ret[item["credential_slug"]] = item["value"]
        return ret

    def update(
        self,
        add: list[dict] | None = None,
        authorise: list[dict] | None = None,
        register: list[dict] | None = None,
        join: list[dict] | None = None,
        merchant: list[dict] | None = None,
    ) -> None:
        """Update the stored credentials in the instance"""
        if add:
            self.add = self._credentials_to_key_pairs(add)
        if authorise:
            self.authorise = self._credentials_to_key_pairs(authorise)
        if register:
            self.register = self._credentials_to_key_pairs(register)
        if join:
            self.join = self._credentials_to_key_pairs(join)
        if merchant:
            self.merchant = self._credentials_to_key_pairs(merchant)
