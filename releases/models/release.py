import json

from django.db import models
from django_countries.fields import CountryField
from django.core.validators import ValidationError, FileExtensionValidator
from django.urls import reverse
from django.utils import timezone

from releases.managers import ReleaseManager, SubmittedReleaseManager
from users.models import Profile, Label
from users.models import ProfileCurrency
from .release_trades_info import ReleaseTradesInfo
from .release_wholesale_info import ReleaseWholesaleInfo
from .release_wholesale_price import ReleaseWholesalePrice
from .marketing_infos import MarketingInfos

from configuration.settings import BASE_DIR

with open(f"{BASE_DIR}/music_genres.json", "r") as file:
    BASE_STYLE_CHOICES = list(json.loads(file.read())['all'].items())


def validate_file_size(value):
    filesize = value.size

    if filesize > 1048576:
        raise ValidationError("The maximum file size that can be uploaded is 1MB")
    else:
        return value


class Release(models.Model):
    profile = models.ForeignKey(
        Profile,
        on_delete=models.CASCADE,
        related_name='release'
    )
    band_name = models.CharField(
        max_length=250,
        verbose_name='Band name(s)',
        help_text='Enter band name here. If split release - add band names with“/“ i.e. Nokturnal Mortum / Drudkh',
    )
    country = CountryField(
        verbose_name='Band country',
        blank=True,
        null=True
    )
    album_title = models.CharField(
        max_length=250,
        verbose_name='Album title'
    )
    release_date = models.DateField(
        verbose_name='Release date',
        help_text='For past/old releases exact date is not important, feel free just to select January 1st, but with '
                  'correct year. For recent/upcoming releases - please try to set the date exactly. This release will '
                  'be shown in Upcoming Releases section.',
        blank=True,
        null=True
    )

    submitted_at = models.DateTimeField(
        verbose_name="submitted date",
        null=True,
        blank=True
    )

    label = models.ForeignKey(
        Label,
        on_delete=models.CASCADE,
        related_name='releases',
        blank=True,
        null=True
    )


    base_style = models.CharField(
        max_length=250,
        choices=BASE_STYLE_CHOICES
    )
    cover_image = models.ImageField(
        upload_to='images/covers/',
        verbose_name='Front cover image',
        help_text='Select image with minimum size of 800x800 pixel',
        blank=True,
        null=True
    )

    class Formats(models.TextChoices):
        CD = 'CD', 'CD'
        VINYL = 'Vinyl', 'Vinyl'
        TAPE = 'Tape', 'Tape'
        DVD = 'DVD', 'DVD'

    format = models.CharField(
        max_length=5,
        choices=Formats.choices,
        default='CD'
    )
    sample = models.FileField(
        upload_to='audios/releases/',
        validators=[validate_file_size, FileExtensionValidator(['mp3'])],
        help_text='Upload up to 1 minute sample of the album to give fellow label owners a taste of this release',
        blank=True,
        null=True
    )
    media_format_details = models.CharField(
        max_length=250,
        help_text='E.g. Digipak, 2xGatefold etc.',
        blank=True,
        null=True
    )
    limited_edition = models.PositiveIntegerField(
        blank=True,
        null=True
    )

    is_submitted = models.BooleanField(default=False)

    objects = ReleaseManager()
    submitted = SubmittedReleaseManager()

    def save(self, force_insert=False, force_update=False, using=None,
             update_fields=None):
        is_new = self.id is None
        super().save(force_insert, force_update)
        if is_new:
            ReleaseTradesInfo.objects.create(release=self)
            ReleaseWholesaleInfo.objects.create(release=self)
            MarketingInfos.objects.create(release=self)

    def divide_media_format(self):
        if self.media_format_details is None:
            return None
        return " | ".join(self.media_format_details.split(", "))

    def currencies_without_price(self):
        profile_currencies = self.profile.currencies
        release_currencies_ids = ReleaseWholesalePrice.objects.filter(release=self).values_list('currency', flat=True)
        release_currencies = ProfileCurrency.objects.filter(id__in=release_currencies_ids)
        currency_choices = profile_currencies.exclude(id__in=release_currencies)

        return currency_choices

    def get_wishlist_addition_url(self):
        return reverse("add_to_wishlist", args=[self.id])

    def wholesale_prices_string(self):
        return ", ".join([f"{wholesale.price} ({wholesale.currency.currency})"
                   for wholesale in self.wholesale_prices.all()])

    def get_date(self):
        if self.release_date is None:
            return ""
        months_since = (timezone.now().date() - self.release_date).days // 30
        if months_since > 6:
            return self.release_date.year
        else:
            return self.release_date
