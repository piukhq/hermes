from django.db import connection
from scheme.models import SchemeAccount

def scheme_account_status_data(self):

    cursor = connection.cursor()

    sql = "SELECT sa.scheme_id, ss.name, sa.status, COUNT (status) " \
          "FROM scheme_schemeaccount AS sa " \
          "JOIN scheme_scheme AS ss ON sa.scheme_id = ss.id " \
          "GROUP BY sa.status, ss.name,sa.scheme_id " \
          "ORDER BY sa.scheme_id,sa.status"

    cursor.execute(sql)
    db_data = dictfetchall(cursor)

    # Create a new list to hold the new dictionaries containing all status plus scheme info.
    scheme_status_list = []
    schemes_list = []
    for statusItem in SchemeAccount.STATUSES:
        scheme_dict = {statusItem[0]: statusItem[1]}
        scheme_status_list.append(scheme_dict)

    for item in db_data:

        for scheme_item in scheme_status_list:
            code = list(scheme_item.keys())[0]
            val = list(scheme_item.values())[0]
            if code == item['status']:
                item['description'] = val
                schemes_list.append(item)
            else:
                temp = {
                    'scheme_id': item['scheme_id'],
                    'name': item['name'],
                    'count': 0,
                    'status': code,
                    'description': val
                }
                schemes_list.append(temp)

    return schemes_list


def dictfetchall(cursor):
    "Return all rows from a cursor as a dict"
    columns = [col[0] for col in cursor.description]
    return [
        dict(zip(columns, row))
        for row in cursor.fetchall()
        ]

