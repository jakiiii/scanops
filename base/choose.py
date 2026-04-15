from django.db import models
from django.utils.translation import gettext_lazy as _


class StrategicValueChoose(models.TextChoices):
    ONE = '1', _('1')
    TWO = '2', _('3')
    THREE = '3', _('3')
    FOUR = '4', _('4')
    FIVE = '5', _('5')


class VulnerabilityLevelChoices(models.TextChoices):
    LOW = 'LOW', _('LOW')
    MEDIUM = 'MEDIUM', _('MEDIUM')
    HIGH = 'HIGH', _('HIGH')


class AnswerYesNo(models.TextChoices):
    NO = 'NO', _('NO')
    YES = 'YES', _('YES')
