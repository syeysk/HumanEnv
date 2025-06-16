import sys
from datetime import date
from pathlib import Path

import gi
import db
from db import (
    BOOK_CONTACT_TYPES,
    BOOK_DID,
    CIRCLES,
    SEXES,
    CONTACT_STATUSES,
    DBAdapter,
)
from sqlalchemy import select

gi.require_version("Gtk", "4.0")
from gi.repository import GLib, Gio, Gtk, GObject

BASE_DIR = Path(__file__).resolve().parent
MENU_MAIN_PATH = BASE_DIR / 'menu_main.xml'
#WIDGET_MAIN_PATH = BASE_DIR / 'widget_main.xml'
DEFAULT_DB_PATH = BASE_DIR / 'default.db'
dbapi = None


#with open(WIDGET_MAIN_PATH) as widget_main_file:
#    widget_main_xml = widget_main_file.read()


def populate_grid(grid, widget_map, start_top_index=0):
    for top_index, (label, entry, button) in enumerate(widget_map, start_top_index):
        grid.attach(label, 0, top_index, 1, 1)
        grid.attach(entry, 1, top_index, 1 if button else 2, 1)
        if button:
            grid.attach(button, 2, top_index, 1, 1)


class EntityEditWindow(Gtk.ApplicationWindow):
    entity_name = None
    entity_class = None

    def __init__(self, *args, entity_id=None, human_id=None, community_id=None, **kwargs):
        super().__init__(*args, **kwargs)
        
        self.human_id = human_id
        self.community_id = community_id

        self.entity = None
        if entity_id:
            query = select(self.entity_class).where(self.entity_class.id == entity_id)
            self.entity = dbapi.session.scalars(query).first()

    @GObject.Signal(arg_types=(int,))
    def entity_added(self, entity_id: int):
        pass

    @GObject.Signal(arg_types=(int, str, str))
    def entity_updated(self, entity_id: int, name: str, value: str):
        pass

    def on_change_any_data(self, field_entry, field_name):
        if isinstance(field_entry, Gtk.SpinButton):
            value = field_entry.get_value()
        else:
            value = field_entry.get_text()
            
        self.change_any_data(field_name, value)

    def on_change_any_data_dropdown(self, field_entry, _pspec, field_name):
        #selected_item = field_entry.props.selected_item
        self.change_any_data(field_name, field_entry.props.selected + 1)

    def change_any_data(self, name, value):
        fields = {name: value}
        if self.entity:
            setattr(self.entity, name, value)
            dbapi.session.commit()
            self.emit('entity_added', self.entity.id, name, value)
        else:
            self.entity = self.entity_class(**fields)
            dbapi.session.add(self.entity)
            dbapi.session.commit()
            self.id_value.set_text(str(self.entity.id))            
            self.emit('entity_added', self.entity.id)


# Inspired by: https://www.reddit.com/r/GTK/comments/1889i8s/gtk4_python_how_to_set_columnview_header_labels/?tl=ru
class EntityColumnView:
    def _on_factory_setup(self, factory, list_item):
        cell = Gtk.Inscription()
        cell._binding = None
        list_item.set_child(cell)

    def _on_factory_bind(self, factory, list_item, what):
        cell = list_item.get_child()
        country = list_item.get_item()
        cell._binding = country.bind_property(what, cell, 'text', GObject.BindingFlags.SYNC_CREATE)

    def _on_factory_unbind(self, factory, list_item, what):
        cell = list_item.get_child()
        if cell._binding:
            cell._binding.unbind()
            cell._binding = None

    def _on_factory_teardown(self, factory, list_item):
        cell = list_item.get_child()
        cell._binding = None

    def __init__(self, item_type, field_names, on_activate, on_add_clicked=None, on_delete_clicked=None):
        # Buttons

        self.buttons_box = Gtk.Box(spacing=6)
        self.buttons_box.props.orientation = Gtk.Orientation.HORIZONTAL
        
        delete_button = Gtk.Button(label='Удалить')
        if on_delete_clicked:
            delete_button.connect('clicked', on_delete_clicked)

        add_button = Gtk.Button(label='Добавить')
        if on_add_clicked:
            add_button.connect('clicked', on_add_clicked)


        select_button = Gtk.Button(label='Выбрать')

        self.buttons_box.append(delete_button)
        self.buttons_box.append(add_button)
        self.buttons_box.append(select_button)

        # Item's list
    
        self.item_type_class = item_type
        self.list_store = Gio.ListStore(item_type=item_type)
        selection = Gtk.SingleSelection(model=self.list_store)
        self.view = Gtk.ColumnView(model=selection)
        self.view.connect('activate', on_activate)
        for field_title, field_name in field_names:
            factory = Gtk.SignalListItemFactory()
            factory.connect('setup', self._on_factory_setup)
            factory.connect('bind', self._on_factory_bind, field_name)
            factory.connect("unbind", self._on_factory_unbind, field_name)
            factory.connect("teardown", self._on_factory_teardown)
            column = Gtk.ColumnViewColumn(title=field_title, factory=factory)
            self.view.append_column(column)

    def append(self, **kwargs):
         self.list_store.append(self.item_type_class(**kwargs))

    def clear(self):
        self.list_store.remove_all()


#@Gtk.Template(string=widget_main_xml)
class HumanWindow(EntityEditWindow, Gtk.ApplicationWindow):
    #__gtype_name__ = "example1"
    entity_name = 'human'
    entity_class = db.Human

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        main_box = Gtk.Box(spacing=6)
        main_box.props.orientation = Gtk.Orientation.VERTICAL
        self.set_child(main_box)

        top_box = Gtk.Box(spacing=6)
        top_box.props.orientation = Gtk.Orientation.HORIZONTAL
        main_box.append(top_box)

        bottom_box = Gtk.Box(spacing=6)
        bottom_box.props.orientation = Gtk.Orientation.VERTICAL
        main_box.append(bottom_box)
        
        top_left_box = Gtk.Grid()
        top_box.append(top_left_box)

        top_right_box = Gtk.Grid()
        top_box.append(top_right_box)

        # Top Left Controllers
        
        photo = Gtk.Picture.new_for_filename(str(BASE_DIR / 'temp.png'))
        top_left_box.attach(photo, 0, 0, 2, 1)

        id_label = Gtk.Label(label='Идентификатор')
        self.id_value = Gtk.Label(label=self.entity.id if self.entity else '')

        sex_label = Gtk.Label(label='Пол')
        sex_entry = Gtk.DropDown()
        sex_entry.props.model = Gtk.StringList(strings=tuple(SEXES.values()))
        sex_entry.props.selected = (self.entity.sex - 1) if self.entity else 0
        sex_entry.connect('notify::selected-item', self.on_change_any_data_dropdown, 'sex')

        birth_year_adjustment = Gtk.Adjustment(upper=3000, step_increment=1, page_increment=10)
        birth_month_adjustment = Gtk.Adjustment(upper=12, step_increment=1, page_increment=10)
        birth_day_adjustment = Gtk.Adjustment(upper=31, step_increment=1, page_increment=10)

        birth_year_label = Gtk.Label(label='Год рождения')
        self.birth_year_entry = Gtk.SpinButton()
        self.birth_year_entry.props.adjustment = birth_year_adjustment
        self.birth_year_entry.set_value(int(self.entity.birth_year) if self.entity else 0)
        self.birth_year_entry.connect('changed', self.on_change_birth_date)
        self.birth_year_entry.connect('changed', self.on_change_any_data, 'birth_year')

        birth_month_label = Gtk.Label(label='Месяц рождения')
        self.birth_month_entry = Gtk.SpinButton()
        self.birth_month_entry.props.adjustment = birth_month_adjustment
        self.birth_month_entry.set_value(int(self.entity.birth_month) if self.entity else 0)
        self.birth_month_entry.connect('changed', self.on_change_birth_date)
        self.birth_month_entry.connect('changed', self.on_change_any_data, 'birth_month')

        birth_day_label = Gtk.Label(label='День рождения')
        self.birth_day_entry = Gtk.SpinButton()
        self.birth_day_entry.props.adjustment = birth_day_adjustment
        self.birth_day_entry.set_value(int(self.entity.birth_day) if self.entity else 0)
        self.birth_day_entry.connect('changed', self.on_change_birth_date)
        self.birth_day_entry.connect('changed', self.on_change_any_data, 'birth_day')

        age_label = Gtk.Label(label='Возраст:')
        self.age_value = Gtk.Label(label='10')

        top_left_map = (
            (id_label, self.id_value, None),
            (sex_label, sex_entry, None),
            (birth_year_label, self.birth_year_entry, None),
            (birth_month_label, self.birth_month_entry, None),
            (birth_day_label, self.birth_day_entry, None),
            (age_label, self.age_value, None),
        )        
        populate_grid(top_left_box, top_left_map, 1)

        # Top Right Controllers

        family_name_label = Gtk.Label(label='Фамилия')
        family_name_entry = Gtk.Entry(text=self.entity.family_name if self.entity else '')
        family_name_entry.connect('changed', self.on_change_any_data, 'family_name')
        first_name_label = Gtk.Label(label='Имя')
        first_name_entry = Gtk.Entry(text=self.entity.first_name if self.entity else '')
        first_name_entry.connect('changed', self.on_change_any_data, 'first_name')
        father_name_label = Gtk.Label(label='Отчество')
        father_name_entry = Gtk.Entry(text=self.entity.father_name if self.entity else '')
        father_name_entry.connect('changed', self.on_change_any_data, 'father_name')

        closing_adjustment = Gtk.Adjustment(upper=20, step_increment=1, page_increment=10)

        closing_label = Gtk.Label(label='Близость')
        closing_entry = Gtk.SpinButton()
        closing_entry.props.adjustment = closing_adjustment
        closing_entry.set_value(int(self.entity.closing) if self.entity else 0)
        closing_entry.connect('changed', self.on_change_any_data, 'closing')

        top_right_map = (
            (family_name_label, family_name_entry, None),
            (first_name_label, first_name_entry, None),
            (father_name_label, father_name_entry, None),
            (closing_label, closing_entry, None),
        )

        populate_grid(top_right_box, top_right_map)
        
        circle_label = Gtk.Label(label='Круг')
        circle_entry = Gtk.DropDown()
        circle_entry.props.model = Gtk.StringList(strings=tuple(CIRCLES.values()))
        circle_entry.props.selected = (self.entity.circle - 1) if self.entity else 0
        circle_entry.connect('notify::selected-item', self.on_change_any_data_dropdown, 'circle')
        top_right_box.attach(circle_label, 0, len(top_right_map), 1, 1)
        top_right_box.attach(circle_entry, 1, len(top_right_map), 2, 1)

        sector_label = Gtk.Label(label='Сектор')
        sector_entry = Gtk.DropDown()
        sector_strings = tuple(sector.name for sector in dbapi.get_sectors())
        sector_entry.props.model = Gtk.StringList(strings=sector_strings)
        sector_entry.props.selected = (self.entity.sector_id - 1) if self.entity else 0
        sector_entry.connect('notify::selected-item', self.on_change_any_data_dropdown, 'sector_id')
        sector_edit_button = Gtk.Button(label='Edit')
        sector_edit_button.connect('clicked', self.on_sector_edit_clicked)
        top_right_box.attach(sector_label, 0, len(top_right_map) + 1, 1, 1)
        top_right_box.attach(sector_entry, 1, len(top_right_map) + 1, 1, 1)
        top_right_box.attach(sector_edit_button, 2, len(top_right_map) + 1, 1, 1)

        book_contact_type_label = Gtk.Label(label='Тип контакта')
        book_contact_type_entry = Gtk.DropDown()
        book_contact_type_entry.props.model = Gtk.StringList(strings=tuple(BOOK_CONTACT_TYPES.values()))
        book_contact_type_entry.props.selected = (self.entity.book_contact_type - 1) if self.entity else 0
        book_contact_type_entry.connect('notify::selected-item', self.on_change_any_data_dropdown, 'book_contact_type')
        top_right_box.attach(book_contact_type_label, 0, len(top_right_map) + 2, 1, 1)
        top_right_box.attach(book_contact_type_entry, 1, len(top_right_map) + 2, 2, 1)

        book_did_label = Gtk.Label(label='Анализ ОИС')
        book_did_entry = Gtk.DropDown()
        book_did_entry.props.model = Gtk.StringList(strings=tuple(BOOK_DID.values()))
        book_did_entry.props.selected = (self.entity.book_did - 1) if self.entity else 0
        book_did_entry.connect('notify::selected-item', self.on_change_any_data_dropdown, 'book_did')
        top_right_box.attach(book_did_label, 0, len(top_right_map) + 3, 1, 1)
        top_right_box.attach(book_did_entry, 1, len(top_right_map) + 3, 2, 1)

        # Bottom Controllers

        contact_columns = (('ID', 'contact_id'), ('Тип', 'contact_type'), ('Значение', 'contact_value'), ('Статус', 'contact_status'))
        self.contacts_column_view = EntityColumnView(
            Contact,
            contact_columns,
            self.on_activate_contact,
            self.on_add_contact_clicked,
        )
        bottom_box.append(self.contacts_column_view.buttons_box)
        bottom_box.append(self.contacts_column_view.view)

        if self.entity:
            self.update_contact_list()

        links_label = Gtk.Label(label='Links')
        bottom_box.append(links_label)
    
    def update_contact_list(self):
        for link_contact in dbapi.session.scalars(select(db.LinkContactHuman).where(db.LinkContactHuman.human_id==self.entity.id)):
            contact = link_contact.contact
            self.contacts_column_view.append(
                contact_id=contact.id,
                contact_type=contact.type.name,
                contact_value=contact.value,
                contact_status=CONTACT_STATUSES[contact.status],
            )

    def on_change_birth_date(self, spin_button):
        birth_date = date(
            self.birth_year_entry.get_value_as_int() or 1,
            self.birth_month_entry.get_value_as_int() or 1,
            self.birth_day_entry.get_value_as_int() or 1,
        )
        age_timedelta = date.today() - birth_date
        self.age_value.set_text(f'{age_timedelta.days // 365} лет')
    
    def on_contact_added(self, widget, contact_id):
        dbapi.session.add(db.LinkContactHuman(human_id=self.entity.id, contact_id=contact_id))
        dbapi.session.commit()
        self.contacts_column_view.clear()
        self.update_contact_list()
    
    def open_contact_window(self, contact_id=None):
        window = ContactWindow(transient_for=self, title='Contact', modal=True, entity_id=contact_id)
        window.connect('entity_added', self.on_contact_added)
        window.present()

    def on_activate_contact(self, column_view, position):
        item = self.contacts_column_view.list_store.get_item(position)
        self.open_contact_window(item.contact_id)
    
    def on_add_contact_clicked(self, _):
        self.open_contact_window()

    def on_sector_edit_clicked(self, button):
        window = SectorListWindow(transient_for=self, title='Sector List', modal=True)
        window.present()     


class ContactTypeWindow(EntityEditWindow, Gtk.ApplicationWindow):
    entity_name = 'contact_type'
    entity_class = db.ContactType

    def __init__(self, *args,  **kwargs):
        super().__init__(*args, **kwargs)

        grid = Gtk.Grid()
        self.set_child(grid)

        id_label = Gtk.Label(label='Идентификатор')
        self.id_value = Gtk.Label(label=self.entity.id if self.entity else '')

        name_label = Gtk.Label(label='Название')
        name_entry = Gtk.Entry(text=self.entity.name if self.entity else '')
        name_entry.connect('changed', self.on_change_any_data, 'name')

        grid_map = (
            (id_label, self.id_value, None),
            (name_label, name_entry, None),
        )
        populate_grid(grid, grid_map)


class SectorWindow(EntityEditWindow, Gtk.ApplicationWindow):
    entity_name = 'sector'
    entity_class = db.Sector

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        grid = Gtk.Grid()
        self.set_child(grid)

        id_label = Gtk.Label(label='Идентификатор')
        self.id_value = Gtk.Label(label=self.entity.id if self.entity else '')

        name_label = Gtk.Label(label='Название')
        name_entry = Gtk.Entry(text=self.entity.name if self.entity else '')
        name_entry.connect('changed', self.on_change_any_data, 'name')

        grid_map = (
            (id_label, self.id_value, None),
            (name_label, name_entry, None),
        )
        populate_grid(grid, grid_map)


class CommunityWindow(EntityEditWindow, Gtk.ApplicationWindow):
    entity_name = 'community'
    entity_class = db.Community

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        grid = Gtk.Grid()
        self.set_child(grid)

        id_label = Gtk.Label(label='Идентификатор')
        self.id_value = Gtk.Label(label=self.entity.id if self.entity else '')

        name_label = Gtk.Label(label='Название')
        name_entry = Gtk.Entry(text=self.entity.name if self.entity else '')
        name_entry.connect('changed', self.on_change_any_data, 'name')

        grid_map = (
            (id_label, self.id_value, None),
            (name_label, name_entry, None),
        )
        populate_grid(grid, grid_map)


class TaskWindow(EntityEditWindow, Gtk.ApplicationWindow):
    entity_name = 'task'
    entity_class = db.Task

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        grid = Gtk.Grid()
        self.set_child(grid)

        id_label = Gtk.Label(label='Идентификатор')
        self.id_value = Gtk.Label(label=self.entity.id if self.entity else '')

        title_label = Gtk.Label(label='Название')
        title_entry = Gtk.Entry(text=self.entity.title if self.entity else '')
        title_entry.connect('changed', self.on_change_any_data, 'title')

        grid_map = (
            (id_label, self.id_value, None),
            (title_label, title_entry, None),
        )
        populate_grid(grid, grid_map)


class ContactTypeListWindow(Gtk.ApplicationWindow):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        box = Gtk.Box()
        box.props.orientation = Gtk.Orientation.VERTICAL
        self.set_child(box)
        
        contact_type_columns = (('ID', 'contact_type_id'), ('Название', 'contact_type_name'))
        self.contact_types_column_view = EntityColumnView(
            ContactType,
            contact_type_columns,
            self.on_activate_contact_type,
            self.on_add_contact_type_clicked,
        )
        box.append(self.contact_types_column_view.buttons_box)
        box.append(self.contact_types_column_view.view)
        
        self.update_contact_type_list()

    def on_contact_type_added(self, widget, _):
        self.contact_types_column_view.clear()
        self.update_contact_type_list()
    
    def open_contact_type_window(self, contact_type_id=None):
        window = ContactTypeWindow(transient_for=self, title='Contact Type', modal=True, entity_id=contact_type_id)
        window.connect('entity_added', self.on_contact_type_added)
        window.present()

    def on_activate_contact_type(self, column_view, position):
        item = self.contact_types_column_view.list_store.get_item(position)
        self.open_contact_type_window(item.contact_type_id)
    
    def on_add_contact_type_clicked(self, _):
        self.open_contact_type_window()

    def update_contact_type_list(self):
        for contact_type in dbapi.get_contact_types():
            self.contact_types_column_view.append(
                contact_type_id=contact_type.id,
                contact_type_name=contact_type.name,
            )


class SectorListWindow(Gtk.ApplicationWindow):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        box = Gtk.Box()
        box.props.orientation = Gtk.Orientation.VERTICAL
        self.set_child(box)
        
        sector_columns = (('ID', 'sector_id'), ('Название', 'sector_name'))
        self.sectors_column_view = EntityColumnView(
            Sector,
            sector_columns,
            self.on_activate_sector,
            self.on_add_sector_clicked,
        )
        box.append(self.sectors_column_view.buttons_box)
        box.append(self.sectors_column_view.view)
        
        self.update_sector_list()

    def on_sector_added(self, widget, _):
        self.sectors_column_view.clear()
        self.update_sector_list()
    
    def open_sector_window(self, sector_id=None):
        window = SectorWindow(transient_for=self, title='Sector', modal=True, entity_id=sector_id)
        window.connect('entity_added', self.on_sector_added)
        window.present()

    def on_activate_sector(self, column_view, position):
        item = self.sectors_column_view.list_store.get_item(position)
        self.open_sector_window(item.sector_id)
    
    def on_add_sector_clicked(self, _):
        self.open_sector_window()

    def update_sector_list(self):
        for sector in dbapi.get_sectors():
            self.sectors_column_view.append(
                sector_id=sector.id,
                sector_name=sector.name,
            )


class ContactWindow(EntityEditWindow, Gtk.ApplicationWindow):
    entity_name = 'contact'
    entity_class = db.Contact

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        grid = Gtk.Grid()
        self.set_child(grid)
        
        id_label = Gtk.Label(label='Идентификатор')
        self.id_value = Gtk.Label(label=self.entity.id if self.entity else '')

        value_label = Gtk.Label(label='Значение')
        value_entry = Gtk.Entry(text=self.entity.value if self.entity else '')
        value_entry.connect('changed', self.on_change_any_data, 'value')

        type_label = Gtk.Label(label='Тип')
        type_entry = Gtk.DropDown()
        type_strings = tuple(contact_type.name for contact_type in dbapi.get_contact_types())
        type_entry.props.model = Gtk.StringList(strings=type_strings)
        type_entry.props.selected = (self.entity.type_id - 1) if self.entity else 0
        type_entry.connect('notify::selected-item', self.on_change_any_data_dropdown, 'type_id')
        type_edit_button = Gtk.Button(label='Edit')
        type_edit_button.connect('clicked', self.on_type_edit_clicked)

        status_label = Gtk.Label(label='Статус')
        status_entry = Gtk.DropDown()
        status_entry.props.model = Gtk.StringList(strings=tuple(CONTACT_STATUSES.values()))
        status_entry.props.selected = (self.entity.status - 1) if self.entity else 0
        status_entry.connect('notify::selected-item', self.on_change_any_data_dropdown, 'status')

        top_right_map = (
            (id_label, self.id_value, None),
            (value_label, value_entry, None),
            (type_label, type_entry, type_edit_button),
            (status_label, status_entry, None),
        )
        populate_grid(grid, top_right_map)
    
    def on_type_edit_clicked(self, button):
        window = ContactTypeListWindow(transient_for=self, title='Contact Type List', modal=True)
        window.present()


class Human(GObject.Object):
    __gtype_name__  = 'Human'
    
    def __init__(self, human_id, human_name):
        super().__init__()
        self._human_id = human_id
        self._human_name = human_name

    @GObject.Property(type=int)
    def human_id(self):
        return self._human_id

    @GObject.Property(type=str)
    def human_name(self):
        return self._human_name


class Contact(GObject.Object):
    __gtype_name__  = 'Contact'

    def __init__(self, contact_id, contact_type, contact_value, contact_status):
        super().__init__()
        self._contact_id = contact_id
        self._contact_type = contact_type
        self._contact_value = contact_value
        self._contact_status = contact_status

    @GObject.Property(type=int)
    def contact_id(self):
        return self._contact_id

    @GObject.Property(type=str)
    def contact_type(self):
        return self._contact_type

    @GObject.Property(type=str)
    def contact_value(self):
        return self._contact_value

    @GObject.Property(type=str)
    def contact_status(self):
        return self._contact_status


class ContactType(GObject.Object):
    __gtype_name__  = 'ContactType'
    
    def __init__(self, contact_type_id, contact_type_name):
        super().__init__()
        self._contact_type_id = contact_type_id
        self._contact_type_name = contact_type_name

    @GObject.Property(type=int)
    def contact_type_id(self):
        return self._contact_type_id

    @GObject.Property(type=str)
    def contact_type_name(self):
        return self._contact_type_name


class Sector(GObject.Object):
    __gtype_name__  = 'Sector'

    def __init__(self, sector_id, sector_name):
        super().__init__()
        self._sector_id = sector_id
        self._sector_name = sector_name

    @GObject.Property(type=int)
    def sector_id(self):
        return self._sector_id

    @GObject.Property(type=str)
    def sector_name(self):
        return self._sector_name


class Community(GObject.Object):
    __gtype_name__  = 'Community'

    def __init__(self, community_id, community_name):
        super().__init__()
        self._community_id = community_id
        self._community_name = community_name

    @GObject.Property(type=int)
    def community_id(self):
        return self._community_id

    @GObject.Property(type=str)
    def community_name(self):
        return self._community_name


class Task(GObject.Object):
    __gtype_name__  = 'Task'

    def __init__(self, task_id, task_title):
        super().__init__()
        self._task_id = task_id
        self._task_title = task_title

    @GObject.Property(type=int)
    def task_id(self):
        return self._task_id

    @GObject.Property(type=str)
    def task_title(self):
        return self._task_title


class AppWindow(Gtk.ApplicationWindow):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.set_default_size(400, 400)
        
        self.props.show_menubar = True
        
        action_add_human = Gio.SimpleAction.new('add_human', None)
        action_add_human.connect('activate', self.on_show_adding_human)
        self.add_action(action_add_human)

        action_add_community = Gio.SimpleAction.new('add_community', None)
        action_add_community.connect('activate', self.on_show_adding_community)
        self.add_action(action_add_community)

        action_add_task = Gio.SimpleAction.new('add_task', None)
        action_add_task.connect('activate', self.on_show_adding_task)
        self.add_action(action_add_task)

        action_add_contact = Gio.SimpleAction.new('add_contact', None)
        action_add_contact.connect('activate', self.on_show_adding_contact)
        self.add_action(action_add_contact)

        action_show_humans = Gio.SimpleAction.new('show_humans', None)
        action_show_humans.connect('activate', self.on_show_humans)
        self.add_action(action_show_humans)

        action_show_communities = Gio.SimpleAction.new('show_communities', None)
        action_show_communities.connect('activate', self.on_show_communities)
        self.add_action(action_show_communities)

        action_show_tasks = Gio.SimpleAction.new('show_tasks', None)
        action_show_tasks.connect('activate', self.on_show_tasks)
        self.add_action(action_show_tasks)

        action_show_contacts = Gio.SimpleAction.new('show_contacts', None)
        action_show_contacts.connect('activate', self.on_show_contacts)
        self.add_action(action_show_contacts)

        self.main_box = None
        self.on_show_humans(None, None)

    def on_show_humans(self, action, value):
        self.clear_and_init_empty_view()
        self.humans_column_view = EntityColumnView(
            Human,
           (('ID', 'human_id'), ('ФИО', 'human_name')),
            self.on_activate_human,
            self.on_show_adding_human,
        )
        self.update_human_list()
        self.main_box.append(self.humans_column_view.buttons_box)
        self.main_box.append(self.humans_column_view.view)

    def clear_and_init_empty_view(self):
        if self.main_box:
            self.main_box = None

        self.main_box = Gtk.Box(spacing=6)
        self.main_box.props.orientation = Gtk.Orientation.VERTICAL
        self.set_child(self.main_box)

    def on_show_communities(self, action, value):
        self.clear_and_init_empty_view()
        self.communities_column_view = EntityColumnView(
            Community,
           (('ID', 'community_id'), ('Название', 'community_name')),
            self.on_activate_community,
            self.on_show_adding_community,
        )
        self.update_community_list()
        self.main_box.append(self.communities_column_view.buttons_box)
        self.main_box.append(self.communities_column_view.view)

    def on_show_tasks(self, action, value):
        self.clear_and_init_empty_view()
        self.tasks_column_view = EntityColumnView(
            Task,
           (('ID', 'task_id'), ('Название', 'task_title')),
            self.on_activate_task,
            self.on_show_adding_task,
        )
        self.update_task_list()
        self.main_box.append(self.tasks_column_view.buttons_box)
        self.main_box.append(self.tasks_column_view.view)

    def on_show_contacts(self, action, value):
        self.clear_and_init_empty_view()
        self.contacts_column_view = EntityColumnView(
            Contact,
           (('ID', 'contact_id'), ('Значение', 'contact_value')),
            self.on_activate_contact,
            self.on_show_adding_contact,
        )
        self.update_contact_list()
        self.main_box.append(self.contacts_column_view.buttons_box)
        self.main_box.append(self.contacts_column_view.view)

    def on_show_map(self, action, value):
        pass

    def on_show_aims(self, action, value):
        pass

    def on_show_adding_human(self, action, value=None):
        self.open_human_window()

    def on_show_adding_community(self, action, value=None):
        self.open_community_window()

    def on_show_adding_task(self, action, value=None):
        self.open_task_window()

    def on_show_adding_contact(self, action, value=None):
        self.open_contact_window()

    def on_show_settings(self, action, value):
        pass
    
    def on_human_added(self, widget, _):
        self.humans_column_view.clear()
        self.update_human_list()

    def on_community_added(self, widget, _):
        self.communities_column_view.clear()
        self.update_community_list()

    def on_task_added(self, widget, _):
        self.tasks_column_view.clear()
        self.update_task_list()

    def on_contact_added(self, widget, _):
        self.contacts_column_view.clear()
        self.update_contact_list()

    def update_human_list(self):
        for human in dbapi.get_humans():
            self.humans_column_view.append(
                human_id=human.id,
                human_name=human.first_name,
            )

    def update_community_list(self):
        for community in dbapi.get_communities():
            self.communities_column_view.append(
                community_id=community.id,
                community_name=community.name,
            )

    def update_task_list(self):
        for task in dbapi.get_tasks():
            self.tasks_column_view.append(
                task_id=task.id,
                task_title=task.title,
            )

    def update_contact_list(self):
        for contact in dbapi.get_contacts():
            self.contacts_column_view.append(
                contact_id=contact.id,
                contact_type=contact.type.name,
                contact_value=contact.value,
                contact_status=CONTACT_STATUSES[contact.status],
            )

    def on_activate_human(self, column_view, position):
        item = self.humans_column_view.list_store.get_item(position)
        self.open_human_window(item.human_id)

    def on_activate_community(self, column_view, position):
        item = self.communities_column_view.list_store.get_item(position)
        self.open_community_window(item.community_id)

    def on_activate_task(self, column_view, position):
        item = self.tasks_column_view.list_store.get_item(position)
        self.open_task_window(item.task_id)

    def on_activate_contact(self, column_view, position):
        item = self.contacts_column_view.list_store.get_item(position)
        self.open_contact_window(item.contact_id)

    def open_human_window(self, human_id=None):
        window = HumanWindow(transient_for=self, title='Human', modal=True, entity_id=human_id)
        window.connect('entity_added', self.on_human_added)
        window.present()

    def open_community_window(self, community_id=None):
        window = CommunityWindow(transient_for=self, title='Community', modal=True, entity_id=community_id)
        window.connect('entity_added', self.on_community_added)
        window.present()

    def open_task_window(self, task_id=None):
        window = TaskWindow(transient_for=self, title='Task', modal=True, entity_id=task_id)
        window.connect('entity_added', self.on_task_added)
        window.present()

    def open_contact_window(self, contact_id=None):
        window = ContactWindow(transient_for=self, title='Contact', modal=True, entity_id=contact_id)
        window.connect('entity_added', self.on_contact_added)
        window.present()


class MyApplication(Gtk.Application):
    def __init__(self):
        super().__init__(application_id='ru.syeysk.HumEnv')
        GLib.set_application_name('Human Environment Builder')

    def do_startup(self):
        Gtk.Application.do_startup(self)
        
        with open(MENU_MAIN_PATH) as menu_main_file:
            builder = Gtk.Builder.new_from_string(menu_main_file.read(), -1)

        self.set_menubar(builder.get_object('menubar'))

    def do_activate(self):
        window = AppWindow(application=self, title='Human Environment')
        window.present()


with DBAdapter(DEFAULT_DB_PATH) as dbapi:
    app = MyApplication()
    exit_status = app.run(sys.argv)

sys.exit(exit_status)
