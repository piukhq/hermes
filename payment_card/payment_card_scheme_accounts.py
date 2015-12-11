from django.db import connection


def payment_card_scheme_accounts(token):
    cursor = connection.cursor()
    sql = ("SELECT sa.id AS scheme_account_id, sa.scheme_id, sa.user_id "
           "FROM payment_card_paymentcardaccount AS pc "
           "JOIN scheme_schemeaccount AS sa "
           "ON pc.user_id = sa.user_id "
           "WHERE pc.token = '{}' "
           "AND sa.status = '1'").format(token)

    cursor.execute(sql)
    return convert_to_dictionary(cursor)


def convert_to_dictionary(cursor):
    """Return all rows from a cursor as a dict"""
    columns = [col[0] for col in cursor.description]
    return [dict(zip(columns, row)) for row in cursor.fetchall()]
