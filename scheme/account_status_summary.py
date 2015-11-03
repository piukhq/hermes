from django.db import connection


def scheme_account_status_data(self):
    cursor = connection.cursor()

    sql = "SELECT status, COUNT (status)" \
          "FROM scheme_schemeaccount" \
          "GROUP BY status" \
          "ORDER BY status"

    cursor.execute(sql)

    data = cursor.fetchall()
    return data
