import enum

import arrow
from django.template import Context, Template


@enum.unique
class VoucherState(enum.Enum):
    ISSUED = 0
    IN_PROGRESS = 1
    EXPIRED = 2
    REDEEMED = 3
    CANCELLED = 4
    PENDING = 5


class VoucherStateStr(str, enum.Enum):
    ISSUED = "issued"
    IN_PROGRESS = "inprogress"
    EXPIRED = "expired"
    REDEEMED = "redeemed"
    CANCELLED = "cancelled"
    PENDING = "pending"


def apply_template(template_string, *, voucher_scheme, earn_value, earn_target_value):
    """
    Applies a set of context variables to the given template.
    Context is pulled from the given voucher scheme and additional keyword arguments.

    Example template:
        "{{earn_prefix}}{{earn_target_remaining}} left to go!"
    Becomes:
        "£30 left to go!"
    """
    template = Template(template_string)
    context = Context(
        {
            k: getattr(voucher_scheme, k)
            for k in [
                "earn_currency",
                "earn_prefix",
                "earn_suffix",
                "burn_currency",
                "burn_prefix",
                "burn_suffix",
                "burn_value",
            ]
        }
    )

    context["earn_value"] = earn_value
    context["earn_target_remaining"] = max(earn_target_value - earn_value, 0)

    return template.render(context)


def get_expiry_date(voucher_fields):
    if "expiry_date" in voucher_fields:
        expiry_date = arrow.get(voucher_fields["expiry_date"])
    else:
        expiry_date = None

    return expiry_date
