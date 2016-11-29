import csv

from django.core.management.base import BaseCommand

from scheme.models import SchemeAccount
from user.models import CustomUser

# key: export file name.
# model: model to query the objects from.
# fields: field tree used to traverse the model's fields and generate the report. null value signifies a leaf node.
exports = {
    'scheme-accounts': {
        'model': SchemeAccount,
        'fields': {
            'user': {
                'email': None,
            },
            'scheme': {
                'name': None,
            },
            'status_name': None,
            'order': None,
            'card_number': None,
            'barcode': None,
            'action_status': None,
            'manual_answer': None,
            'third_party_identifier': None,
        },
    },
    'users': {
        'model': CustomUser,
        'fields': {
            'email': None,
            'profile': {
                'gender': None,
                'date_of_birth': None,
                'city': None,
                'region': None,
                'postcode': None,
                'country': None,
            },
            'date_joined': None,
        },
    },
}


def get_field_values(obj, field_spec):
    """
    generates a tree of object property values from the given property tree.
    :param obj: the object to traverse.
    :param field_spec: a tree of dicts specifying the fields to obtain.
    :return: a property value tree.
    """
    field_values = {}
    for field, children in field_spec.items():
        attr = getattr(obj, field)
        if children:
            sub_dict = get_field_values(attr, children)
            field_values[field] = sub_dict
        else:
            field_values[field] = attr
    return field_values


def flatten_field_values(field_values, parent_key=''):
    """
    flattens a given a tree of nested dicts into a dictionary with compound key names.

    for example, given the following:
    {'user': {'name': 'Jerry'}}
    return this:
    {'user.name': 'Jerry'}

    this works on unlimited levels of nested dictionaries.
    :param field_values: the dict tree to flatten.
    :param parent_key: the compound dictionary key. this is used for recursion and should be left as default.
    :return: a dictionary mapping compounded key names to leaf node values.
    """
    items = []
    for k, v in field_values.items():
        new_key = '{}.{}'.format(parent_key, k) if parent_key else k
        if isinstance(v, dict):
            items.extend(flatten_field_values(v, new_key).items())
        else:
            items.append((new_key, v))
    return dict(items)


def create_export(spec):
    """
    create an export-ready dataset from the given export specification.
    :param spec: the config to use for the data export.
    :return: a list of dictionaries containing export data.
    """
    model_instances = spec['model'].objects.all()
    field_spec = spec['fields']

    rows = []

    for instance in model_instances:
        field_values = get_field_values(instance, field_spec)
        flat = flatten_field_values(field_values)
        rows.append(flat)

    return rows


def write_csv(rows, filename):
    """
    writes a given list of dicts to a csv file, using dict keys as headings.
    :param rows: a list of dicts to write.
    :param filename: the file to write the csv data to.
    """
    fieldnames = rows[0].keys()

    with open('{}.csv'.format(filename), 'w') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


class Command(BaseCommand):
    help = 'Creates a CSV data export for issue mitigation and reporting purposes.'

    def handle(self, *args, **options):
        for filename, spec in exports.items():
            self.stdout.write(self.style.MIGRATE_LABEL('processing {}.csv'.format(filename)))
            rows = create_export(spec)
            write_csv(rows, filename)
        self.stdout.write(self.style.SUCCESS('data export successful.'))
