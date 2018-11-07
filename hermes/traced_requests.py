from ddtrace import patch
patch(requests=True)

import requests  # noqa
