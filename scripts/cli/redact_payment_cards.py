"""
This script is to redact payment cards from Spreedly using payment card tokens specified in a CSV
file. This file can be generated using the `collect_payment_card_tokens' command, where the filename
can then be provided to this command as a command line argument.

If Spreedly responds with "payment_method_not_found" then the request is treated as a successful redaction.

The Spreedly Basic Auth credentials are also required to use this command and can be provided as an argument if
the vault settings are not sufficient.
"""
import csv
import json
from typing import TYPE_CHECKING

import requests
from requests import Response
from azure.core.exceptions import ResourceNotFoundError, HttpResponseError
from django.conf import settings
from ubiquity.channel_vault import get_azure_client

if TYPE_CHECKING:
    from django.core.management.base import OutputWrapper
    from azure.keyvault.secrets import SecretClient


class VaultException(Exception):
    pass


# user = {"value": "1Lf7DiKgkcx5Anw7QxWdDxaKtTa"}
# pwd = {"value": "xwMcI4T04SlhP4vFucSj3nTX3O8trwQObdgWnI96SI5s5D5Lk4RCI6D3GdWnNrgP"}
SPREEDLY_OAUTH_USERNAME_VAULT_KEY = "spreedly-oAuthUsername"
SPREEDLY_OAUTH_PASSWORD_VAULT_KEY = "spreedly-oAuthPassword"


def redact_payment_cards(
    *, token_filename: str, spreedly_user: str = None, spreedly_pass: str = None, stdout: "OutputWrapper"
) -> str:
    stdout.write(f"Requested redaction of payment cards from Spreedly...")

    redact_detail_filename = "failed_redacts_details.csv"
    failed_tokens_filename = "failed_tokens_list.csv"

    try:
        with (
            open(token_filename, newline="") as token_file,
            open(redact_detail_filename, "w") as failed_results_f,
            open(failed_tokens_filename, "w") as failed_tokens_list_f,
        ):
            # add header to failed redact details file
            print("tokens,valid_response,status_code,content,error", file=failed_results_f)

            # add header to failed tokens file
            print("tokens", file=failed_tokens_list_f)

            if not (spreedly_user and spreedly_pass):
                client = get_azure_client(settings.VAULT_CONFIG)

            spreedly_username = spreedly_user or _get_azure_secret(client, SPREEDLY_OAUTH_USERNAME_VAULT_KEY)
            spreedly_password = spreedly_pass or _get_azure_secret(client, SPREEDLY_OAUTH_PASSWORD_VAULT_KEY)

            reader = csv.reader(token_file)
            # Skip header
            next(reader)

            total = failed_total = 0
            for row in reader:
                if total > 0 and total in [100, 1000] or total % 10000 == 0:
                    stdout.write(f"Completed {total} redact requests...")

                total += 1
                token = row[0]
                successful, resp = try_redact_request(token, (spreedly_username, spreedly_password))

                if not successful:
                    failed_total += 1
                    print(f"{token}", file=failed_tokens_list_f)
                    if isinstance(resp, Response):
                        print(f'{token},true,{resp.status_code},"{resp.content}",', file=failed_results_f)
                    else:
                        print(f'{token},false,,,"{resp}"', file=failed_results_f)

                    if failed_total == 1:
                        # Allow manually ending script to avoid spamming the Spreedly API
                        if _input(
                            f"WARNING: A redact request has encountered an error."
                            "You can continue the script and have all errors logged or quit now and view the error in"
                            f"{redact_detail_filename}\n\n"
                            "Continue? [y/N]"
                        ):
                            stdout.write("Script continuing...")
                        else:
                            return "Exiting..."

    except FileNotFoundError:
        return "The given token file was not found."
    except VaultException as e:
        return f"Failed to load secrets from the vault: \n{e}"

    result = f"{total - failed_total} of {total} Payment cards redacted successfully\n\n"
    if failed_total > 0:
        result += (
            f"Details of failures can be found in {redact_detail_filename}\n"
            f"To retry only failed tokens, re-run the script with {failed_tokens_filename}\n"
        )

    return result


def try_redact_request(token: str, auth: tuple[str, str]) -> tuple[bool, str] | tuple[bool, Response]:
    success = False
    url = f"{settings.SPREEDLY_BASE_URL}/payment_methods/{token}/redact.json"

    try:
        redact_resp = requests.put(url=url, auth=auth)
    except requests.RequestException as e:
        redact_resp = str(e)
        return success, redact_resp

    try:
        redact_resp_json = redact_resp.json()

        if redact_resp.status_code == 404:
            errors = redact_resp_json.get("errors")
            redact_resp = redact_resp_json
            for err in errors:
                if err.get("key") == "errors.payment_method_not_found":
                    # If the payment method is not found then there's no need to redact.
                    # Any other reason should be treated as a failure.
                    success = True
                    break

        if redact_resp_json and (
            redact_resp_json["transaction"]["succeeded"]
            or redact_resp_json["transaction"]["payment_method"]["storage_state"] == "redacted"
        ):
            success = True

    except KeyError:
        redact_resp = f"Unexpected response returned from Spreedly: {redact_resp.text}"
    except json.JSONDecodeError:
        redact_resp = (
            "Expected JSON response but got the following instead - "
            f"{redact_resp.status_code} - {redact_resp.reason} - {redact_resp.content}"
        )

    return success, redact_resp


def _get_azure_secret(client: "SecretClient", key: str) -> str:
    try:
        secret = client.get_secret(key).value
        return json.loads(secret)["value"]
    except (ResourceNotFoundError, HttpResponseError) as e:
        raise VaultException from e


def _input(msg: str) -> bool:
    valid = {
        "y": True,
        "ye": True,
        "yes": True,
        "n": False,
        "no": False,
    }
    # default to False if empty
    res = input(msg).strip().lower() or "n"
    return valid.get(res, False)
