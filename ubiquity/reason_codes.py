from typing import Tuple

PENDING = "pending"
AUTHORISED = "authorised"
UNAUTHORISED = "unauthorised"
FAILED = "failed"
DELETED = "deleted"

REASON_CODES = (
    ("X000", "New data submitted/modified"),
    ("X100", "Add fields being validated"),
    ("X101", "Account does not exist"),
    ("X102", "Add data rejected by merchant"),
    ("X103", "No authorisation provided"),
    ("X104", "Update failed. Delete and re-add card."),
    ("X105", "Account not registered"),
    ("X200", "Enrolment in progress"),
    ("X201", "Enrolment data rejected by merchant"),
    ("X202", "Account already exists"),
    ("X203", "Enrolment complete"),
    ("X300", "Authorisation correct"),
    ("X301", "Authorisation in progress"),
    ("X302", "No authorisation required"),
    ("X303", "Authorisation data rejected by merchant"),
    ("X304", "Authorisation expired"),
)

CURRENT_STATUS_CODES = (
    (0, "Pending"),
    (1, "Active"),
    (5, "Please check your scheme account login details."),
    (9, "Midas unavailable"),
    (10, "Wallet only card"),
    (204, "Pending manual check"),
    (401, "Failed validation"),
    (403, "Invalid credentials"),
    (404, "Agent does not exist on midas"),
    (406, "Pre-registered card"),
    (429, "Cannot connect, too many retries"),
    (432, "Invalid mfa"),
    (434, "Account locked on end site"),
    (436, "Invalid card_number"),
    (437, "You can only Link one card per day."),
    (438, "Unknown Card number"),
    (439, "General Error such as incorrect user details"),
    (441, "Join in progress"),  # Error raised by Iceland when attempting second join during a join in progress
    (442, "Asynchronous join in progress"),
    (443, "Asynchronous registration in progress"),
    (444, "No user currently found"),
    (445, "Account already exists"),
    (446, "Update failed. Delete and re-add card."),
    (447, "Scheme requested account deletion"),
    (503, "Too many balance requests running"),
    (520, "An unknown error has occurred"),
    (530, "End site down"),
    (531, "IP blocked"),
    (532, "Tripped captcha"),
    (533, "Password expired"),
    (535, "Request was not sent"),
    (536, "Error with the configuration or it was not possible to retrieve"),
    (537, "Service connection error"),
    (538, "A system error occurred during join"),
    (900, "Join"),
    (901, "Enrol Failed"),
    (902, "Registration Failed"),
)

# status codes in SchemeAccount.SYSTEM_ACTION_REQUIRED will not have any reason code associated with them
# as they will be mapped to either pending or active via the `get_translated_status()` function.
reason_code_translation = {
    0: ["X100"],
    1: ["X300"],
    5: ["X303"],
    9: [],
    10: ["X103"],
    204: ["X100"],
    401: ["X102"],
    403: ["X303"],
    404: [],
    406: ["X105"],
    429: [],
    432: ["X303"],
    434: ["X304"],
    436: ["X102"],
    437: [],
    438: ["X105"],
    439: ["X104"],
    441: ["X201"],
    442: ["X200"],
    443: ["X200"],
    # 443 (Async Registration in Progress) returns X200 (Enrolment in progress). Even though this isn't strictly
    # accurate, this is to avoid potential Barclays issues involving new reason codes.
    444: ["X101"],
    445: ["X202"],
    446: ["X104"],
    447: ["X304"],
    503: [],
    520: [],
    530: [],
    531: [],
    532: [],
    533: ["X304"],
    535: [],
    536: [],
    537: [],
    538: [],
    900: ["X201"],
    901: ["X201"],
    902: ["X105"],
}

ubiquity_status_translation = {
    0: PENDING,
    1: AUTHORISED,
    5: UNAUTHORISED,
    9: FAILED,
    10: UNAUTHORISED,
    204: PENDING,
    401: FAILED,
    403: FAILED,
    404: UNAUTHORISED,
    406: FAILED,
    429: FAILED,
    432: UNAUTHORISED,
    434: FAILED,
    436: FAILED,
    437: FAILED,
    438: FAILED,
    439: FAILED,
    441: FAILED,
    442: PENDING,
    443: PENDING,
    444: FAILED,
    445: FAILED,
    446: FAILED,
    447: FAILED,
    503: FAILED,
    520: FAILED,
    530: FAILED,
    531: FAILED,
    532: FAILED,
    533: UNAUTHORISED,
    535: FAILED,
    536: FAILED,
    537: FAILED,
    538: FAILED,
    900: FAILED,
    901: FAILED,
    902: FAILED,
}


def get_state_reason_code_and_text(status_code: int) -> Tuple[str, list, str]:
    state = ubiquity_status_translation[status_code]
    reason_codes = reason_code_translation[status_code]
    error_text = dict(CURRENT_STATUS_CODES)[status_code]
    return state, reason_codes, error_text
