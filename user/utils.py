from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from datetime import datetime


@dataclass
class MagicLinkData:
    bundle_id: str
    slug: str
    external_name: str
    email: str
    email_from: str
    subject: str
    template: str
    url: str
    token: str
    expiry_date: 'datetime'
    locale: str
