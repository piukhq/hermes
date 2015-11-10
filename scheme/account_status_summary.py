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
    db_data = convert_to_dictionary(cursor)

    # Create a new list to hold the dictionaries containing all status plus scheme info.
    # Need to have all scheme statuses for each scheme, then update counts
    schemes_list = scheme_summary_list(db_data)

    return schemes_list


def convert_to_dictionary(cursor):
    "Return all rows from a cursor as a dict"
    columns = [col[0] for col in cursor.description]
    return [
        dict(zip(columns, row))
        for row in cursor.fetchall()
        ]


def scheme_summary_list(db_data):
    schemes_list = []
    statuses = SchemeAccount.STATUSES

    for item in db_data:
        for scheme_item in statuses:
            code = scheme_item[0]
            val = scheme_item[1]
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
