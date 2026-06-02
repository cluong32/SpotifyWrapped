from django.apps import AppConfig


class UsersConfig(AppConfig):
    """
    Configuration class for the 'users' app.

    Attributes:
        default_auto_field (str): Specifies the default auto field type for primary keys.
        name (str): Name of the application, used for application registry.
    """
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'users'
