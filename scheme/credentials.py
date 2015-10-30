USER_NAME = 'username'
CARD_NUMBER = 'card_number'
BARCODE = 'barcode'
PASSWORD = 'password'
PLACE_OF_BIRTH = 'place_of_birth'
EMAIL = 'email'
POSTCODE = 'postcode'
MEMORABLE_DATE = 'memorable_date'
PIN = 'pin'
LAST_NAME = 'last_name'

CREDENTIAL_TYPES = (
    (USER_NAME, 'user name'),
    (EMAIL, 'email'),
    (CARD_NUMBER, 'card number'),
    (BARCODE, 'barcode'),
    (PASSWORD, 'password'),
    (PLACE_OF_BIRTH, 'place of birth'),
    (POSTCODE, 'postcode'),
    (MEMORABLE_DATE, 'memorable date'),
    (PIN, 'pin'),
    (LAST_NAME, 'last name'),
)

ENCRYPTED_CREDENTIALS = (
    PASSWORD,
    POSTCODE,
    MEMORABLE_DATE,
    PLACE_OF_BIRTH,
    PIN,
    LAST_NAME,
)
