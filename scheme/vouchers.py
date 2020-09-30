from django.template import Template, Context
import arrow

import enum


# must match the enum in Midas - good candidate for moving into a shared library
@enum.unique
class VoucherType(enum.Enum):
    JOIN = 0
    ACCUMULATOR = 1
    STAMPS = 2


@enum.unique
class VoucherState(enum.Enum):
    ISSUED = 0
    IN_PROGRESS = 1
    EXPIRED = 2
    REDEEMED = 3
    CANCELLED = 4


voucher_type_names = {VoucherType.JOIN: "join", VoucherType.ACCUMULATOR: "accumulator", VoucherType.STAMPS: "stamps"}

voucher_state_names = {
    VoucherState.ISSUED: "issued",
    VoucherState.IN_PROGRESS: "inprogress",
    VoucherState.EXPIRED: "expired",
    VoucherState.REDEEMED: "redeemed",
    VoucherState.CANCELLED: "cancelled"
}


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


def get_expiry_date(voucher_scheme, voucher_fields, issue_date):
    if "expiry_date" in voucher_fields:
        expiry_date = arrow.get(voucher_fields["expiry_date"])
    elif issue_date is not None:
        expiry_date = issue_date.shift(months=+voucher_scheme.expiry_months)
    else:
        expiry_date = None

    return expiry_date
