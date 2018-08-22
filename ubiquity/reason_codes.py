REASON_CODES = (
    ('X000', 'New data submitted/modified'),
    ('X100', 'Add fields being validated'),
    ('X101', 'Account does not exist'),
    ('X102', 'Add data rejected by merchant'),
    ('X103', 'No authorisation provided'),
    ('X200', 'Enrolment in progress'),
    ('X201', 'Enrolment data rejected by merchant'),
    ('X202', 'Account already exists'),
    ('X203', 'Enrolment complete'),
    ('X300', 'Authorisation correct'),
    ('X301', 'Authorisation in progress'),
    ('X302', 'No authorisation required'),
    ('X303', 'Authorisation data rejected by merchant'),
    ('X304', 'Authorisation expired')
)

CURRENT_STATUS_CODES = (
    (0, 'Pending'),
    (1, 'Active'),
    (403, 'Invalid credentials'),
    (432, 'Invalid mfa'),
    (530, 'End site down'),
    (531, 'IP blocked'),
    (532, 'Tripped captcha'),
    (5, 'Please check your scheme account login details.'),
    (434, 'Account locked on end site'),
    (429, 'Cannot connect, too many retries'),
    (503, 'Too many balance requests running'),
    (520, 'An unknown error has occurred'),
    (9, 'Midas unavailable'),
    (10, 'Wallet only card'),
    (404, 'Agent does not exist on midas'),
    (533, 'Password expired'),
    (900, 'Join'),
    (444, 'No user currently found'),
    (536, 'Error with the configuration or it was not possible to retrieve'),
    (535, 'Request was not sent')
)

# todo double check and confirm codes relations
reason_code_translation = {
    0: 'X100',
    1: 'X300',
    403: 'X303',
    432: 'X303',
    530: None,
    531: None,
    532: None,
    5: 'X303',
    434: 'X304',
    429: None,
    503: None,
    520: None,
    9: None,
    10: 'X103',
    404: 'X101',
    533: 'X304',
    900: 'X200',
    444: 'X101',
    536: None,
    535: None
}
