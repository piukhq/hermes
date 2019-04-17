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
PHONE_2 = 'phone_2'
GENDER = 'gender'
ADDRESS_1 = 'address_1'
ADDRESS_2 = 'address_2'
ADDRESS_3 = 'address_3'
TOWN_CITY = 'town_city'
COUNTY = 'county'
COUNTRY = 'country'
REGULAR_RESTAURANT = 'regular_restaurant'
MERCHANT_IDENTIFIER = 'merchant_identifier'

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
    (PHONE_2, 'phone number 2'),
    (GENDER, 'gender'),
    (ADDRESS_1, 'address 1'),
    (ADDRESS_2, 'address 2'),
    (ADDRESS_3, 'address 3'),
    (TOWN_CITY, 'town city'),
    (COUNTY, 'county'),
    (COUNTRY, 'country'),
    (REGULAR_RESTAURANT, 'regular restaurant'),
    (MERCHANT_IDENTIFIER, 'merchant identifier')
)

DATE_TYPE_CREDENTIALS = (
    MEMORABLE_DATE,
    DATE_OF_BIRTH
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

credential_types_set = {credential_type[0] for credential_type in CREDENTIAL_TYPES}
