from collections import defaultdict
from copy import copy
from pprint import pprint

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
    schemes = defaultdict(dict)
    # Put the schemes into a dict format
    for scheme_status in db_data:
        schemes[scheme_status['scheme_id']][scheme_status['status']] = scheme_status

    output = []
    for scheme_id, present_statuses in schemes.items():
        output.append({
            "scheme_id": scheme_id,
            "statuses": generate_all_statuses(present_statuses)
        })
    return output


def generate_all_statuses(statuses):
    name = list(statuses.values())[0]['name']  # We just need the first name
    all_statuses = []
    for code, description in SchemeAccount.STATUSES:
        all_statuses.append({
            'name': name,
            'count': statuses.get(code, {}).get('count', 0),
            'status': code,
            'description': description
        })
    return all_statuses
