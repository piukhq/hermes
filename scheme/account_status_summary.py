from django.db import connection


def scheme_account_status_data(self):
    cursor = connection.cursor()

    sql = "SELECT scheme_id, status, COUNT (status) " \
          "FROM scheme_schemeaccount " \
          "GROUP BY scheme_id, status " \
          "ORDER BY scheme_id, status"

    cursor.execute(sql)

    return dictfetchall(cursor)


def dictfetchall(cursor):
    "Return all rows from a cursor as a dict"
    columns = [col[0] for col in cursor.description]
    return [
        dict(zip(columns, row))
        for row in cursor.fetchall()
        ]
