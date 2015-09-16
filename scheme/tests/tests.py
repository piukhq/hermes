import json
from rest_framework.test import APITestCase
from scheme.tests import factories


class TestScheme(APITestCase):
    def test_scheme_list(self):
        factories.SchemeFactory.create()

        response = self.client.get('/schemes/')
        content = json.loads(response.content)
        self.assertEqual(response.status_code, 200)


# GET /schemes/
# GET /schemes/<int:scheme_id>
# POST /schemes/accounts/
# PUT /schemes/accounts/<int:scheme_account_id>
# GET /schemes/accounts/<int:scheme_account_id>
# GET /schemes/accounts/<int:scheme_account_id>