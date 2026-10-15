from PyQt6.QtWidgets import QVBoxLayout, QHBoxLayout

from db.gui_actions import ActionsHumanWidget
from db.models import (
    Community,
    Contact,
    Human,
    Task,
    Meeting,
    ContactType,
    HumanRelationType,
    Sector,
    TaskAim,
)


class GUIHuman:
    dj_model = Human
    # table_class = EntitiesList
    # window_name = 'scetch'
    table_fields = ['family_name', 'first_name']
    # actions_class = ActionsHumanWidget
    field_order = 'family_name'
    fields_search = ['family_name', 'first_name', 'father_name']
    window_fields =  ['sex', 'birth_year', 'birth_month', 'birth_day', 'family_name', 'first_name', 'father_name', 'closing', 'circle', 'sector', 'book_contact_type', 'book_did']


class GUICommunity:
    dj_model = Community
    # table_class = EntitiesList
    # window_class = CommunityWindow
    table_fields = ['name']
    window_fields = ['name']


class GUITask:
    dj_model = Task
    # table_class = EntitiesList
    # window_class = TaskWindow
    table_fields = ['has_done', 'title']
    window_fields = ['has_done', 'title', 'aim']


class GUIContact:
    dj_model = Contact
    # table_class = EntitiesList
    # window_class = ContactWindow
    table_fields = ['type', 'value', 'status']
    window_fields = ['type', 'value', 'status']


class GUIMeeting:
    dj_model = Meeting
    # table_class = EntitiesList
    # window_class = MeetingWindow
    table_fields = ['title']
    window_fields = ['title', 'description', 'date']
 

class GUISector:
    dj_model = Sector
    fields_search = ['name']
    window_fields = ['name']
    table_fields = ['name']
    show_on_main = False


class GUIHumanRelationType:
    dj_model = HumanRelationType
    fields_search = ['name']
    window_fields = ['name']
    table_fields = ['name']
    show_on_main = False


class GUITaskAim:
    dj_model = TaskAim
    fields_search = ['name']
    window_fields = ['name']
    table_fields = ['name']
    show_on_main = False


class GUIContactType:
    dj_model = ContactType
    fields_search = ['name']
    window_fields = ['name']
    table_fields = ['name']
    show_on_main = False
