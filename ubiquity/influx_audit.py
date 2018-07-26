from django.conf import settings
from influxdb import InfluxDBClient


class InfluxAudit(object):
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
        user_set = ",".join(str(u.id) for u in card_link.payment_card_account.user_set.all())
        return {
            "measurement": settings.INFLUX_DB_NAME,
            "tags": {
                "payment_card_account": card_link.payment_card_account.id,
                "user_set": user_set
            },
            "fields": {
                "scheme_account": card_link.scheme_account.id
            }
        }

    def write_to_db(self, link_data, many=False):
        """
        :param link_data:
        :type link_data: list of ubiquity.models.PaymentCardSchemeEntry

        :param many:
        :type many: bool
        """
        link_data = link_data if many else [link_data]
        json_payload = [self._format_audit_entry(link) for link in link_data]
        self.client.write_points(json_payload)

    def query_db(self):
        """
        TESTING ENDPOINT
        :return: json string
        """
        return self.client.query('SELECT * FROM {}'.format(settings.INFLUX_DB_NAME)).raw


audit = InfluxAudit()
