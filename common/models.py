from django.db import models


class Image(models.Model):
    DRAFT = 0
    PUBLISHED = 1

    STATUSES = (
        (DRAFT, 'draft'),
        (PUBLISHED, 'published'),
    )

    HERO = 0
    BANNER = 1
    OFFER = 2
    ICON = 3
    ASSET = 4
    REFERENCE = 5
    PERSONAL_OFFERS = 6
    PROMOTIONS = 7
    TIER = 8
    ALT_HERO = 9

    TYPES = (
        (HERO, 'hero'),
        (BANNER, 'banner'),
        (OFFER, 'offers'),
        (ICON, 'icon'),
        (ASSET, 'asset'),
        (REFERENCE, 'reference'),
        (PERSONAL_OFFERS, 'personal offers'),
        (PROMOTIONS, 'promotions'),
        (TIER, 'tier'),
        (ALT_HERO, 'alternative hero')
    )

    image_type_code = models.IntegerField(choices=TYPES)
    size_code = models.CharField(max_length=30, blank=True)
    image = models.ImageField(upload_to="schemes")
    strap_line = models.CharField(max_length=50, blank=True)
    description = models.CharField(max_length=300)
    url = models.URLField(null=True, blank=True)
    call_to_action = models.CharField(max_length=150)
    order = models.IntegerField()
    status = models.IntegerField(default=DRAFT, choices=STATUSES)
    start_date = models.DateTimeField()
    end_date = models.DateTimeField(blank=True, null=True)
    created = models.DateTimeField(auto_now_add=True)
    all_objects = models.Manager()
    reward_tier = models.IntegerField(default=0)
    encoding = models.CharField(max_length=30, null=True, blank=True)

    def image_type_code_name(self):
        return dict(self.TYPES)[self.image_type_code]

    def __str__(self):
        return '({}) {}'.format(self.image_type_code_name(), self.description)

    class Meta:
        abstract = True

    def ubiquity_format(self) -> dict:
        if self.encoding:
            encoding = self.encoding
        else:
            try:
                encoding = self.image.name.split('.')[-1].replace('/', '')
            except (IndexError, AttributeError):
                encoding = None

        return {
            'payload': {
                'id': self.id,
                'type': self.image_type_code,
                'url': self.image.url,
                'description': self.description,
                'encoding': encoding,

            },
            'validity': {
                'start_date': self.start_date.timestamp() if self.start_date else None,
                'end_date': self.end_date.timestamp() if self.end_date else None
            }
        }


def check_active_image(validity: dict, date: int) -> bool:
    start = validity.get('start_date')
    end = validity.get('end_date')

    if start is not None and start <= date:
        if end is not None and date >= end:
            return False
        else:
            return True
    else:
        return False
