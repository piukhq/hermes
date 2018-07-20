from django.conf import settings
from influxdb import InfluxDBClient


class InfluxAudit:
    client = None

    def __init__(self):
        self.client = InfluxDBClient(**settings.INFLUX_DB_CONFIG)

        if settings.INFLUX_DB_NAME not in self.client.get_list_database():
            self.client.create_database(settings.INFLUX_DB_NAME)

        self.client.switch_database(settings.INFLUX_DB_NAME)

    @staticmethod
    def _format_audit_entry(card_link):
        """
        :param card_link:
        :type card_link: ubiquity.models.PaymentCardSchemeEntry
        """
        return {
            "measurement": "cards_active_link",
            "tags": {
                "payment_card_account": card_link.payment_card_account.id
            },
            "fields": {
                # "user_set": [u.id for u in card_link.payment_card_account.user_set.all()],
                "payment_card_account": card_link.payment_card_account.id,
                "scheme_account": card_link.scheme_account.id
            }
        }

    def write_to_db(self, link_data, many=False):
        if many:
            json_payload = [self._format_audit_entry(link) for link in link_data]
        else:
            json_payload = [self._format_audit_entry(link_data)]

        self.client.write_points(json_payload)

    def query_db(self):
        return self.client.query('SELECT * FROM "cards_active_link"').raw
