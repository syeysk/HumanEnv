from django.apps import AppConfig
from gardensunion.base.utils import register_gui
from django.conf import settings


class HumanEnvConfig(AppConfig):
    verbose_name = 'Окружение человека'
    name = 'db'

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        settings.TG_TOKEN = settings.ENV('TG_TOKEN')

    def ready(self):
        from db import gui_models
        register_gui(gui_models, 'GUIHuman', 'GUIContact', 'GUICommunity', 'GUITask', 'GUIMeeting', 'GUISector', 'GUIHumanRelationType', 'GUITaskAim', 'GUIContactType')
