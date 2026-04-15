import uuid
from django.db import models
from django.utils.translation import gettext_lazy as _
from django.contrib.auth.models import AbstractUser, BaseUserManager


class UserManager(BaseUserManager):
    use_in_migrations = True

    def _create_user(self, username, email, password, **extra_fields):
        if not username:
            raise ValueError("Username is required.")
        if not password:
            raise ValueError("Password is required.")
        email = self.normalize_email(email or f"{username}@scanops.local")
        user = self.model(username=username, email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_user(self, username, email=None, password=None, **extra_fields):
        extra_fields.setdefault("is_active", True)
        extra_fields.setdefault("is_staff", False)
        extra_fields.setdefault("is_superuser", False)
        extra_fields.setdefault("is_administrator", False)
        extra_fields.setdefault("is_operator", False)
        extra_fields.setdefault("first_name", extra_fields.get("first_name", ""))
        extra_fields.setdefault("last_name", extra_fields.get("last_name", ""))
        return self._create_user(username, email, password, **extra_fields)

    def create_staff(self, username, email=None, password=None, **extra_fields):
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)
        return self.create_user(username, email=email, password=password, **extra_fields)

    def create_superuser(self, username, email=None, password=None, **extra_fields):
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)
        extra_fields.setdefault("is_administrator", True)
        extra_fields.setdefault("is_operator", True)

        if extra_fields.get("is_staff") is not True:
            raise ValueError("Superuser must have is_staff=True.")
        if extra_fields.get("is_superuser") is not True:
            raise ValueError("Superuser must have is_superuser=True.")
        return self._create_user(username, email, password, **extra_fields)


class User(AbstractUser):
    email = models.EmailField(
        unique=True,
        verbose_name=_("Email Address"),
    )
    is_administrator = models.BooleanField(
        default=False,
        verbose_name=_("Is Administrator"),
    )
    is_operator = models.BooleanField(
        default=False,
        verbose_name=_("Is Operator"),
    )
    REQUIRED_FIELDS = ['email', 'first_name', 'last_name']
    objects = UserManager()

    def __str__(self):
        return self.username

    class Meta:
        verbose_name = "User"
        verbose_name_plural = "Users"
        db_table = "tbl_user"
