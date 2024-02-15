from typing import TYPE_CHECKING
from urllib.parse import urlparse

import psycopg2

if TYPE_CHECKING:
    from django.core.management.base import OutputWrapper

BATCH_SIZE = 1_000


def collect_tokens(*, channel: str, output_path: str, postgres_uri: str, stdout: "OutputWrapper") -> str:
    uri = urlparse(postgres_uri)
    if not (uri.scheme and uri.path and uri.username and uri.port):
        return f"Unable to parse postgres_uri '{postgres_uri}'"

    stdout.write(f"Requested collection of payment card accounts' tokens for channel: '{channel}'")
    stdout.write(f"Output will be written to '{output_path}'")
    stdout.write("Connecting to Database with the following parameters:")
    stdout.write(f"* scheme: '{uri.scheme}'")
    stdout.write(f"* db name: '{uri.path.replace('/', '')}'")
    stdout.write(f"* user: '{uri.username}'")
    stdout.write(f"* password: '{uri.password}'")
    stdout.write(f"* port: '{uri.port}'")

    if input("Continue (y/n)? ") not in ("y", "yes"):
        return "Exiting"

    stdout.write("Collecting tokens...")

    sql = """
        SELECT
            DISTINCT (hpca.body ->> 'token') AS "token"
        FROM
            history_historicalpaymentcardaccount hpca
        WHERE
            hpca.channel = %s
        AND
            (hpca.body ->> 'id')::int NOT IN (
                SELECT
                    pca.id
                FROM
                    payment_card_paymentcardaccount pca
                WHERE
                    pca.is_deleted = false
            )
    """

    # NB: using psycopg2 directly to enable connecting to custom postgres instances based on provided URI
    with psycopg2.connect(postgres_uri) as conn, open(output_path, "w") as output:
        print("tokens,", file=output)
        with conn.cursor() as cursor:
            cursor.execute(sql, [channel])
            while True:
                lines = cursor.fetchmany(size=BATCH_SIZE)
                if not lines:
                    break

                for line in lines:
                    print(f"{line[0]},", file=output)

    return "Tokens collected successfully."
