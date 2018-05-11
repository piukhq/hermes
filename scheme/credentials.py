USER_NAME = 'username'
CARD_NUMBER = 'card_number'
BARCODE = 'barcode'
PASSWORD = 'password'
PLACE_OF_BIRTH = 'place_of_birth'
EMAIL = 'email'
POSTCODE = 'postcode'
MEMORABLE_DATE = 'memorable_date'
PIN = 'pin'
TITLE = 'title'
FIRST_NAME = 'first_name'
LAST_NAME = 'last_name'
FAVOURITE_PLACE = 'favourite_place'
DATE_OF_BIRTH = 'date_of_birth'
PHONE = 'phone'
ADDRESS_1 = 'address_1'
ADDRESS_2 = 'address_2'
TOWN_CITY = 'town_city'
COUNTY = 'county'
COUNTRY = 'country'

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
    (TITLE, 'title'),
    (FIRST_NAME, 'first name'),
    (LAST_NAME, 'last name'),
    (FAVOURITE_PLACE, 'favourite place'),
    (DATE_OF_BIRTH, 'date_of_birth'),
    (PHONE, 'phone number'),
    (ADDRESS_1, 'address 1'),
    (ADDRESS_2, 'address 2'),
    (TOWN_CITY, 'town city'),
    (COUNTY, 'county'),
    (COUNTRY, 'country'),
)

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
)
