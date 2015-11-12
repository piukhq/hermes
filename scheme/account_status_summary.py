from copy import copy
from django.db import connection
from scheme.models import SchemeAccount


def scheme_account_status_data():
    db_data = status_summary_from_db()

    # Create a new list to hold the dictionaries containing all status plus scheme info.
    # Need to have all scheme statuses for each scheme, then update counts
    schemes_list = scheme_summary_list(db_data)
    return schemes_list


def status_summary_from_db():
    cursor = connection.cursor()

    sql = "SELECT sa.scheme_id, ss.name, sa.status, COUNT (status) " \
          "FROM scheme_schemeaccount AS sa " \
          "JOIN scheme_scheme AS ss ON sa.scheme_id = ss.id " \
          "GROUP BY sa.status, ss.name,sa.scheme_id " \
          "ORDER BY sa.scheme_id,sa.status"

    cursor.execute(sql)
    return convert_to_dictionary(cursor)


def convert_to_dictionary(cursor):
    """Return all rows from a cursor as a dict"""
    columns = [col[0] for col in cursor.description]
    return [dict(zip(columns, row)) for row in cursor.fetchall()]


def scheme_summary_list(db_data):
    schemes_list = []
    statuses = SchemeAccount.STATUSES

    scheme_ids = sorted(list({x['scheme_id'] for x in db_data}))
    for scheme_id in scheme_ids:
        schemes_list.append({'scheme_id': scheme_id, 'statuses': []})

    for item in db_data:
        for code, description in statuses:
            scheme_dict = list(filter(lambda scheme: scheme['scheme_id'] == item['scheme_id'], schemes_list))[0]
            if code == item['status']:
                item['description'] = description
                new_item = copy(item)
                new_item.pop('scheme_id')
                scheme_dict['statuses'].append(new_item)
            else:
                new_status = {
                    'name': item['name'],
                    'count': 0,
                    'status': code,
                    'description': description
                }
                scheme_dict['statuses'].append(new_status)

    return schemes_list
