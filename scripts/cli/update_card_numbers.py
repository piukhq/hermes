import csv
import re
from typing import TYPE_CHECKING, Any

from django.db import connection

from scheme.models import Scheme, SchemeAccount

if TYPE_CHECKING:
    from django.core.management.base import OutputWrapper


def remaining_invalid_card_numbers(scheme_id: int, valid_card_number_regex: str) -> list[dict[str, str]] | None:
    # Find scheme account objects with card_numbers that don't match the regex pattern
    scheme_accounts = (
        SchemeAccount.objects.filter(scheme_id=scheme_id)
        .exclude(card_number__regex=valid_card_number_regex)
        .values("card_number", "merchant_identifier")
    )
    return scheme_accounts


sql = """
update scheme_schemeaccount
set
    card_number = data_table.valid_number,
    merchant_identifier = data_table.valid_number
from (
    select
        unnest(%s) as invalid_number,
        unnest(%s) as valid_number
) as data_table
where
    is_deleted is false
    and scheme_id = %s
    and (card_number = data_table.invalid_number
         or merchant_identifier = data_table.invalid_number)
"""


def batch_update_scheme_accounts(
    cursor: Any,
    invalid_card_numbers: list[str],
    valid_card_numbers: list[str],
    scheme_id: int,
    batch_size: int,
) -> int:
    count_success = 0
    for i in range(0, len(invalid_card_numbers), batch_size):
        invalid_chunk = invalid_card_numbers[i : i + batch_size]
        valid_chunk = valid_card_numbers[i : i + batch_size]
        cursor.execute(sql, (invalid_chunk, valid_chunk, scheme_id))
        count_success += cursor.rowcount
    return count_success


def attempt_update_scheme_accounts(
    members_filename: str, remaining_members_filename: str, batch_size: int, stdout: "OutputWrapper"
) -> str:
    invalid_card_numbers = []
    valid_card_numbers = []
    valid_card_number_regex = r"^L[A-Za-z]{2}\d{3}$"
    if scheme_id := Scheme.objects.filter(slug="stonegate").values_list("id", flat=True).first():
        with open(members_filename) as members_file:
            reader = csv.DictReader(members_file)
            for row in reader:
                member_id = row["MemberID"]
                member_number = row["MemberNumber"]
                # Check if both MemberID contains numerical data and MemberNumber matches the specified pattern
                if not member_id.isdigit() or not member_number or not re.match(valid_card_number_regex, member_number):
                    stdout.write(f"Invalid data in row: MemberID: {member_id}, MemberNumber: {member_number}")
                    continue
                invalid_card_numbers.append(member_id)
                valid_card_numbers.append(member_number)
            if invalid_card_numbers and valid_card_numbers:
                with connection.cursor() as cursor:
                    count_success = batch_update_scheme_accounts(
                        cursor, invalid_card_numbers, valid_card_numbers, scheme_id, batch_size
                    )
                    if not count_success:
                        stdout.write("No scheme accounts found that matched the provided data")

        if remaining_scheme_accounts := remaining_invalid_card_numbers(scheme_id, valid_card_number_regex):
            with open(remaining_members_filename, "w", newline="") as remaining_members_file:
                csv_writer = csv.DictWriter(remaining_members_file, ["card_number", "merchant_identifier"])
                csv_writer.writeheader()
                csv_writer.writerows(remaining_scheme_accounts)
    else:
        return "The scheme slug stonegate was not found."

    return (
        f"{count_success} of {reader.line_num - 1} Scheme accounts updated, "
        f"{len(remaining_scheme_accounts)} remaining scheme accounts with an invalid format.\n\n"
    )
