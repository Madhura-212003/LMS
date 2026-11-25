from django.apps import AppConfig

class LmsConfig(AppConfig):
    name='lms'
    default_auto_field='django.db.models.BigAutoField'
    def ready(self):
        from . import signals
