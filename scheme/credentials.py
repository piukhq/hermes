USER_NAME = 'username'
CARD_NUMBER = 'card_number'
BARCODE = 'barcode'
PASSWORD = 'password'
PLACE_OF_BIRTH = 'place_of_birth'
EMAIL = 'email'
POSTCODE = 'postcode'
MEMORABLE_DATE = 'memorable_date'

CREDENTIAL_TYPES = (
    (USER_NAME, 'user name'),
    (EMAIL, 'email'),
    (CARD_NUMBER, 'card number'),
    (BARCODE, 'barcode'),
    (PASSWORD, 'password'),
    (PLACE_OF_BIRTH, 'place of birth'),
    (POSTCODE, 'postcode'),
    (MEMORABLE_DATE, 'memorable date'),
)

ENCRYPTED_CREDENTIALS = (
    PASSWORD,
    POSTCODE,
    MEMORABLE_DATE,
    PLACE_OF_BIRTH
)
