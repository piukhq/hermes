from django.core.management.base import BaseCommand, CommandParser

from scripts.cli.barclays_wipe import wipe_barclays_data
from scripts.cli.client_decommission import decommission_client
from scripts.cli.collect_payment_card_tokens import collect_tokens
from scripts.cli.redact_payment_cards import redact_payment_cards
from scripts.cli.update_card_numbers import attempt_update_scheme_accounts
from scripts.cli.visa_vop import run_activations_by_scheme_slug, run_deactivations_by_scheme_slug

available_scripts = {
    "client-decommission": {
        "fn": decommission_client,
        "script_kwargs": {
            # NB these will be in the format:
            # "dest name": {
            #   "flags": *name_or_flags,
            #   other parameters accepted by the .add_argument(...) method
            # }
            "client_name": {
                "flags": ["--client-name", "-c"],
                "type": str,
                "help": "name field of the ClientApplication to decommission",
                "required": True,
            },
            "exclude_test_users": {
                "flags": ["--exclude-test-users", "-e"],
                "action": "store_true",
                "help": "excludes test users from deletion by adding filters `is_staff=False` and `is_tester=False`",
            },
            "batch_size": {
                "flags": ["--batch-size", "-b"],
                "type": int,
                "required": False,
                "default": 1000,
                "help": "users to be processed batch size, defaults to 1000",
            },
            "log_path": {
                "flags": ["--log-path", "-p"],
                "type": str,
                "required": False,
                "default": "/tmp/client_decommission.log",
                "help": (
                    "during script execution the normal hermes logging will be redirected to this file, "
                    "defaults to '/tmp/client_decommission.log'"
                ),
            },
            "is_dry_run": {
                "flags": ["--dry-run", "-d"],
                "action": "store_true",
                "help": "show what data will be impacted without actually making any modifications",
            },
        },
    },
    "barclays-wipe": {
        "fn": wipe_barclays_data,
        "script_kwargs": {},
    },
    "vop-deactivation-by-scheme": {
        "fn": run_deactivations_by_scheme_slug,
        "script_kwargs": {
            "scheme_slug": {
                "flags": ["--scheme-slug", "-s"],
                "type": str,
                "help": "Scheme.slug to deactivate VOPActivations for",
                "required": True,
            },
            "use_default": {
                "flags": ["--use-default-group", "-D"],
                "action": "store_true",
                "help": "Use default VOPMerchantGroup for deactivation",
            },
            "group_name": {
                "flags": ["--group-name", "-g"],
                "type": str,
                "help": (
                    "use specified VOPMerchantGroup.group_name for deactivation, requires --use-default to be False"
                ),
                "required": False,
            },
            "log_path": {
                "flags": ["--log-path", "-l"],
                "type": str,
                "help": "Write logs for failed deactivations to this file, defaults to '/tmp/vop_deactivation.log'",
                "default": "/tmp/vop_deactivation.log",
                "required": False,
            },
        },
    },
    "vop-activation-by-scheme": {
        "fn": run_activations_by_scheme_slug,
        "script_kwargs": {
            "scheme_slug": {
                "flags": ["--scheme-slug", "-s"],
                "type": str,
                "help": "Scheme.slug to activate VOPActivations for",
                "required": True,
            },
            "use_default": {
                "flags": ["--use-default-group", "-D"],
                "action": "store_true",
                "help": "Use default VOPMerchantGroup for activation",
                "required": False,
            },
            "group_name": {
                "flags": ["--group-name", "-g"],
                "type": str,
                "help": "use specified VOPMerchantGroup.group_name for activation, requires --use-default to be False",
                "required": False,
            },
            "log_path": {
                "flags": ["--log-path", "-l"],
                "type": str,
                "help": "Write logs for failed activations to this file, defaults to '/tmp/vop_activation.log'",
                "default": "/tmp/vop_activation.log",
                "required": False,
            },
        },
    },
    "collect-payment-card-tokens": {
        "fn": collect_tokens,
        "script_kwargs": {
            "channel": {
                "flags": ["--channel", "-c"],
                "type": str,
                "help": "collect tokens for payment cards that belong to this channel",
                "required": True,
            },
            "output_path": {
                "flags": ["--output-path", "-o"],
                "type": str,
                "help": "collected tokens output file path. Defaults to '/tmp/tokens.csv'",
                "default": "/tmp/tokens.csv",
            },
            "postgres_uri": {
                "flags": ["--postgres-uri", "-u"],
                "type": str,
                "help": "Postgres URI",
                "required": True,
            },
        },
    },
    "redact-payment-cards": {
        "fn": redact_payment_cards,
        "script_kwargs": {
            "token_filename": {
                "flags": ["--filepath", "-f"],
                "type": str,
                "help": "Filepath of payment card tokens to redact from Spreedly. "
                "This can be generated via the collect-payment-card-tokens command.",
                "required": True,
            },
            "spreedly_user": {
                "flags": ["--spreedly-user", "-u"],
                "type": str,
                "help": "Username for Basic Auth to access Spreedly redact endpoint.",
                "required": False,
            },
            "spreedly_pass": {
                "flags": ["--spreedly-pass", "-p"],
                "type": str,
                "help": "Password for Basic Auth to access Spreedly redact endpoint.",
                "required": False,
            },
            "output_folder": {
                "flags": ["--output-folder", "-o"],
                "type": str,
                "help": "The destination folder to output error detail and retry files. Defaults to '/tmp/'",
                "required": False,
                "default": "/tmp/",
            },
        },
    },
    "update-mixr-card-numbers": {
        "fn": attempt_update_scheme_accounts,
        "script_kwargs": {
            "members_filename": {
                "flags": ["--filepath", "-f"],
                "type": str,
                "help": "Filepath of card numbers to be updated.",
                "required": True,
            },
            "remaining_members_filename": {
                "flags": ["--output-path", "-o"],
                "type": str,
                "help": "The destination file path to output the remaining invalid card numbers",
                "default": "/tmp/remaining-invalid.csv",
            },
            "batch_size": {
                "flags": ["--batch-size", "-b"],
                "type": int,
                "required": False,
                "default": 5000,
                "help": "updates to be processed batch size, defaults to 5000",
            },
        },
    },
}


class Command(BaseCommand):
    help = "Runs one of the available scripts"

    def add_arguments(self, parser: CommandParser):
        subparsers = parser.add_subparsers(title="available scripts", dest="script_name", required=True)
        for script_name, script_info in available_scripts.items():
            subparser = subparsers.add_parser(script_name)
            for arg_name, arg_info in script_info["script_kwargs"].items():
                flags = arg_info.pop("flags")
                subparser.add_argument(*flags, **arg_info, dest=arg_name)

    def handle(self, *args, **kwargs):
        script_name = kwargs["script_name"]
        script_kwargs = {k: kwargs[k] for k in available_scripts[script_name]["script_kwargs"]}
        self.stdout.write(f"Starting '{script_name}' with parameters {script_kwargs}")

        if msg := available_scripts[script_name]["fn"](**script_kwargs, stdout=self.stdout):
            self.stdout.write(msg)

        self.stdout.write("execution completed.")
