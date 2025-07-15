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
from jinja2 import Template
from sqlalchemy import select, delete

gi.require_version('Gtk', '4.0')
from gi.repository import GLib, Gio, Gtk, GObject
from circle_map import CircleMapWindow

BASE_DIR = Path(__file__).resolve().parent
MENU_MAIN_PATH = BASE_DIR / 'menu_main.xml'
DBS_DIR = BASE_DIR / 'dbs'

DB_UUID = '8eafafd12f1a4bf4b8d4cfe5ae3b39e8'
DB_DIR = DBS_DIR / DB_UUID
DB_PATH = DB_DIR / 'sqlite3.db'
DB_NAME_PATH = DB_DIR / 'name.txt'
DB_PHOTOS_DIR = DB_DIR / 'photos'

FIELD_ID_SIZE = 30
dbapi = None

class EntityEditWindow(Gtk.ApplicationWindow):
    entity_name = None
    entity_class = None

    def __init__(self, *args, entity_id=None, **kwargs):
        super().__init__(*args, **kwargs)
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

    def on_change_any_data_dropdown(self, dropdown, _pspec, field_name):
        item = dropdown.get_selected_item()
        self.change_any_data(field_name, item.item_id)

    def change_any_data(self, name, value):
        fields = {name: value}
        if self.entity:
            setattr(self.entity, name, value)
            dbapi.session.commit()
            self.emit('entity_updated', self.entity.id, name, value)
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
        item = list_item.get_item()
        cell._binding = item.bind_property(what, cell, 'text', GObject.BindingFlags.SYNC_CREATE)

    def _on_factory_unbind(self, factory, list_item, what):
        cell = list_item.get_child()
        if cell._binding:
            cell._binding.unbind()
            cell._binding = None

    def _on_factory_teardown(self, factory, list_item):
        cell = list_item.get_child()
        cell._binding = None

    def __init__(self, parent_window, item_type, on_entity_added=None, on_entity_deleted=None, on_entity_selected=None):
        # Buttons

        self.parent_window = parent_window
        self.on_entity_added = on_entity_added
        self.on_entity_selected = on_entity_selected
        self.on_entity_deleted = on_entity_deleted

        buttons_box = Gtk.Box(spacing=6)
        buttons_box.props.orientation = Gtk.Orientation.HORIZONTAL
        
        if on_entity_deleted:
            delete_button = Gtk.Button(label='Удалить')
            delete_button.connect('clicked',self.on_delete_item_clicked)
            buttons_box.append(delete_button)

        if on_entity_added:
            add_button = Gtk.Button(label='Добавить')
            add_button.connect('clicked', self.on_add_item_clicked)
            buttons_box.append(add_button)

        if on_entity_selected:
            select_button = Gtk.Button(label='Выбрать')
            select_button.connect('clicked', self.on_select_item_clicked)            
            buttons_box.append(select_button)

        sign_label = Gtk.Label(label=f'{item_type.__gtype_name__} list')
        buttons_box.append(sign_label)

        # Item's list
    
        self.item_type_class = item_type
        self.list_store = Gio.ListStore(item_type=item_type)
        selection = Gtk.SingleSelection(model=self.list_store)
        view = Gtk.ColumnView(model=selection)
        view.connect('activate', self.on_activate_item)
        for field_title, field_name, size in item_type.columns:
            factory = Gtk.SignalListItemFactory()
            factory.connect('setup', self._on_factory_setup)
            factory.connect('bind', self._on_factory_bind, field_name)
            factory.connect('unbind', self._on_factory_unbind, field_name)
            factory.connect("teardown", self._on_factory_teardown)
            column = Gtk.ColumnViewColumn(title=field_title, factory=factory)
            if size:
                column.props.fixed_width = size
            else:
                column.props.expand = True

            view.append_column(column)

        self.box = Gtk.Box(spacing=2)
        self.box.props.orientation = Gtk.Orientation.VERTICAL
        self.box.append(buttons_box)
        self.box.append(view)
        self.selection = selection

    def append(self, db_object):
         self.list_store.append(self.item_type_class.from_db_object(db_object))

    def clear(self):
        self.list_store.remove_all()

    def open_adding_item_window(self, entity_id=None):
        window = self.item_type_class.window(
            transient_for=self.parent_window,
            title=self.item_type_class.__gtype_name__,
            modal=True,
            entity_id=entity_id,
        )
        window.connect('entity_added', self.on_entity_added)
        window.present()

    def on_activate_item(self, column_view, position):
        item = self.list_store.get_item(position)
        self.open_adding_item_window(item.entity_id)

    def on_add_item_clicked(self, _):
        self.open_adding_item_window()

    def on_select_item_clicked(self, _):
        window = EntityListToSelectWindow(
            entity_type_class=self.item_type_class,
            transient_for=self.parent_window,
            title=self.item_type_class.__gtype_name__,
            modal=True,
        )
        window.connect('entity_selected', self.on_entity_selected)
        window.present()

    def on_delete_item_clicked(self, _):
        selected_item = self.selection.props.selected_item
        self.on_entity_deleted(selected_item.entity_id)


class LinkedEntityColumnView(EntityColumnView):
    def __init__(self, parent_window, item_type, linking_table, item_main, item_slave):
        self.linking_table = linking_table
        self.item_main = item_main
        self.item_slave = item_slave
        super().__init__(parent_window, item_type, self.on_entity_added, self.on_entity_deleted, self.on_entity_added)

    def update_list(self):
        query = select(self.linking_table).where(getattr(self.linking_table, f'{self.item_main}_id')==self.parent_window.entity.id)
        for link in dbapi.session.scalars(query):
            self.append(getattr(link, self.item_slave))

    def on_entity_added(self, widget, linked_entity_id):
        cond_left = getattr(self.linking_table, f'{self.item_main}_id') == self.parent_window.entity.id
        cond_right = getattr(self.linking_table, f'{self.item_slave}_id') == linked_entity_id
        if not dbapi.session.scalar(select(self.linking_table).where(cond_left, cond_right)):
            kwargs = {f'{self.item_main}_id': self.parent_window.entity.id, f'{self.item_slave}_id': linked_entity_id}
            dbapi.session.add(self.linking_table(**kwargs))
            dbapi.session.commit()
            self.clear()
            self.update_list()

    def on_entity_deleted(self, entity_id):
        cond_left = getattr(self.linking_table, f'{self.item_main}_id') == self.parent_window.entity.id
        cond_right = getattr(self.linking_table, f'{self.item_slave}_id') == entity_id
        dbapi.session.execute(delete(self.linking_table).where(cond_left, cond_right))
        dbapi.session.commit()
        self.clear()
        self.update_list()


class SelectingEntityColumnView(EntityColumnView):
    def __init__(self, parent_window, item_type, on_entity_selected):
        super().__init__(parent_window, item_type, on_entity_selected=on_entity_selected)

    def on_activate_item(self, column_view, position):
        item = self.list_store.get_item(position)
        self.on_entity_selected(item.entity_id)


class EntityListWindow(Gtk.ApplicationWindow):
    def __init__(self, entity_type_class, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        self.entity_type_class = entity_type_class
        self.entity_db_class = getattr(db, entity_type_class.__gtype_name__)

        box = Gtk.Box()
        box.props.margin_top = 6
        box.props.margin_bottom = 6
        box.props.margin_start = 6
        box.props.margin_end = 6
        box.props.orientation = Gtk.Orientation.VERTICAL
        self.set_child(box)
        self.column_view = EntityColumnView(
            self,
            self.entity_type_class,
            self.on_entity_added,
            self.on_entity_deleted,
        )
        box.append(self.column_view.box)
        self.update_list()

    def on_entity_added(self, widget, _):
        self.column_view.clear()
        self.update_list()

    def on_entity_deleted(self, entity_id):
        dbapi.session.execute(delete(self.entity_db_class).where(self.entity_db_class.id==entity_id))
        dbapi.session.commit()
        self.column_view.clear()
        self.update_list()

    def update_list(self):
        for entity in dbapi.session.scalars(select(self.entity_db_class)):
            self.column_view.append(entity)


class EntityListToSelectWindow(Gtk.ApplicationWindow):
    def __init__(self, entity_type_class, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.entity_type_class = entity_type_class
        self.entity_db_class = getattr(db, entity_type_class.__gtype_name__)

        box = Gtk.Box()
        box.props.margin_top = 6
        box.props.margin_bottom = 6
        box.props.margin_start = 6
        box.props.margin_end = 6
        box.props.orientation = Gtk.Orientation.VERTICAL
        self.set_child(box)
        self.column_view = SelectingEntityColumnView(
            self,
            self.entity_type_class,
            self.on_entity_selected,
        )
        box.append(self.column_view.box)
        for entity in dbapi.session.scalars(select(self.entity_db_class)):
            self.column_view.append(entity)

    @GObject.Signal(arg_types=(int,))
    def entity_selected(self, entity_id: int):
        pass

    def on_entity_selected(self, selected_id):
        self.emit('entity_selected', selected_id)
        self.close()


class ItemDropDown(GObject.Object):
    __gtype_name__  = 'ItemDropDown'

    def __init__(self, item_id, name):
        super().__init__()
        self._item_id = item_id
        self._name = name

    @GObject.Property(type=int)
    def item_id(self):
        return self._item_id

    @GObject.Property(type=str)
    def name(self):
        return self._name


class UniDropDown(Gtk.DropDown):
    def __init__(self, tupples=None):
        super().__init__()
        factory = Gtk.SignalListItemFactory()
        factory.connect('setup', self._on_setup)
        factory.connect('bind', self._on_bind)
        self.store = Gio.ListStore.new(ItemDropDown)
        selection = Gtk.SingleSelection()
        selection.set_model(self.store)
        self.set_factory(factory)
        self.set_model(selection)
        
        if tupples:
            for item_id, item_name in tupples:
                self.append(item_id, item_name)

    def _on_setup(self, widget, item):
        """Setup the widget to show in the Gtk.Listview"""
        label = Gtk.Label()
        item.set_child(label)

    def _on_bind(self, widget, item):
        """bind data from the store object to the widget"""
        label = item.get_child()
        obj = item.get_item()
        label.set_text(obj.name)

    def append(self, item_id, item_name):
        self.store.append(ItemDropDown(item_id, item_name))


class WindowBuilder:
    def __init__(self, path_to_xml, context, parent_window=None):
        import xml.etree.ElementTree as ET
        self.parent_window = parent_window
        with open(path_to_xml, encoding='utf-8') as file_xml:
            template = Template(file_xml.read())
            templated_xml: str = template.render(context)

        root = ET.fromstring(templated_xml)
        self.parents = []
        self._go(root)
        
    def _go(self, node):
        tag = node.tag
        if tag == 'Row':
            data = self.parents[-1][2]
            data['x'] = 0
            data['y'] += 1
        else:
            if tag == 'EntityColumnView':
                gtkclass = LinkedEntityColumnView
            elif tag == 'UniDropDown':
                gtkclass = UniDropDown
            elif tag == 'Picture':
                gtkclass = Gtk.Picture.new_for_filename
            else:
                gtkclass = getattr(Gtk, tag)

            kwargs = {}

            if tag in ('Label', 'Button'):
                kwargs['label'] = node.text
            elif tag == 'Entry':
                kwargs['text'] = node.text
            elif tag == 'EntityColumnView':
                kwargs['parent_window'] = self.parent_window
                kwargs['item_type'] = globals()[node.attrib.pop('item_type')]
                kwargs['linking_table'] = getattr(db, node.attrib.pop('linking_table'))
                kwargs['item_main'] = node.attrib.pop('item_main')
                kwargs['item_slave'] = node.attrib.pop('item_slave')
            elif tag == 'Picture':
                kwargs['filename'] = str(BASE_DIR / node.attrib.pop('filename'))
            
            colspan = int(node.attrib.pop('colspan', '1'))

            gtkelem = gtkclass(**kwargs)
            for attr_name, attr_value in node.attrib.items():
                if attr_name == 'id':
                    setattr(self, attr_value, gtkelem)
                else:
                    if attr_name in {'selected', 'xalign', 'spacing', 'margin_top', 'margin_start', 'margin_bottom', 'margin_end', 'column_spacing', 'row_spacing'}:
                        attr_value = int(attr_value) if attr_value else 0

                    setattr(gtkelem.props, attr_name, attr_value)
        
            if self.parents:
                parent_gtk, parent_type, data = self.parents[-1]
                if parent_type == 'Grid':
                    if tag == 'EntityColumnView':
                        parent_gtk.attach(gtkelem.box, data['x'], data['y'], colspan, 1)
                        data['y'] += 6
                    else:
                        parent_gtk.attach(gtkelem, data['x'], data['y'], colspan, 1)

                    data['x'] += 1
                elif parent_type == 'Box':
                    if tag == 'EntityColumnView':
                        parent_gtk.append(gtkelem.box)
                    else:
                        parent_gtk.append(gtkelem)
        
            if tag == 'Grid':
                self.parents.append((gtkelem, tag, {'x': 0, 'y': -1}))
            elif tag == 'Box':
                self.parents.append((gtkelem, tag, None))

        for child in node:
            self._go(child)

        if tag in {'Grid', 'Box'}:
            if self.parents:
                self.parents.pop(-1)


class HumanWindow(EntityEditWindow, Gtk.ApplicationWindow):
    entity_name = 'human'
    entity_class = db.Human

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        builder = WindowBuilder(BASE_DIR / 'human.xml', {'entity': self.entity}, parent_window=self)
        self.set_child(builder.main_box)
        self.id_value = builder.id_value

        builder.main_box.props.orientation = Gtk.Orientation.VERTICAL        
        builder.top_box.props.orientation = Gtk.Orientation.HORIZONTAL
        builder.bottom_box.props.orientation = Gtk.Orientation.VERTICAL

        # Top Left Controllers

        for item_id, item_name in SEXES.items():
            builder.sex_entry.append(item_id=item_id, item_name=item_name)

        builder.sex_entry.props.selected = (self.entity.sex - 1) if self.entity else 0
        builder.sex_entry.connect('notify::selected-item', self.on_change_any_data_dropdown, 'sex')

        birth_year_adjustment = Gtk.Adjustment(upper=3000, step_increment=1, page_increment=10)
        birth_month_adjustment = Gtk.Adjustment(upper=12, step_increment=1, page_increment=10)
        birth_day_adjustment = Gtk.Adjustment(upper=31, step_increment=1, page_increment=10)

        self.birth_year_entry = builder.birth_year_entry
        self.birth_year_entry.props.adjustment = birth_year_adjustment
        self.birth_year_entry.set_value(int(self.entity.birth_year) if self.entity else 0)
        self.birth_year_entry.connect('changed', self.on_change_birth_date)
        self.birth_year_entry.connect('changed', self.on_change_any_data, 'birth_year')

        self.birth_month_entry = builder.birth_month_entry
        self.birth_month_entry.props.adjustment = birth_month_adjustment
        self.birth_month_entry.set_value(int(self.entity.birth_month) if self.entity else 0)
        self.birth_month_entry.connect('changed', self.on_change_birth_date)
        self.birth_month_entry.connect('changed', self.on_change_any_data, 'birth_month')

        self.birth_day_entry = builder.birth_day_entry
        self.birth_day_entry.props.adjustment = birth_day_adjustment
        self.birth_day_entry.set_value(int(self.entity.birth_day) if self.entity else 0)
        self.birth_day_entry.connect('changed', self.on_change_birth_date)
        self.birth_day_entry.connect('changed', self.on_change_any_data, 'birth_day')

        self.age_value = builder.age_value

        # Top Right Controllers

        builder.family_name_entry.connect('changed', self.on_change_any_data, 'family_name')
        builder.first_name_entry.connect('changed', self.on_change_any_data, 'first_name')
        builder.father_name_entry.connect('changed', self.on_change_any_data, 'father_name')

        closing_adjustment = Gtk.Adjustment(upper=20, step_increment=1, page_increment=10)

        builder.closing_entry.props.adjustment = closing_adjustment
        builder.closing_entry.set_value(int(self.entity.closing) if self.entity else 0)
        builder.closing_entry.connect('changed', self.on_change_any_data, 'closing')
        
        for item_id, item_name in CIRCLES.items():
            builder.circle_entry.append(item_id=item_id, item_name=item_name)

        builder.circle_entry.props.selected = (self.entity.circle - 1) if self.entity else 0
        builder.circle_entry.connect('notify::selected-item', self.on_change_any_data_dropdown, 'circle')

        for sector in dbapi.session.scalars(select(db.Sector)):
            builder.sector_entry.append(item_id=sector.id, item_name=sector.name)

        builder.sector_entry.props.selected = (self.entity.sector_id - 1) if self.entity else 0
        builder.sector_entry.connect('notify::selected-item', self.on_change_any_data_dropdown, 'sector_id')
        builder.sector_edit_button.connect('clicked', self.on_sector_edit_clicked)

        for item_id, item_name in BOOK_CONTACT_TYPES.items():
            builder.book_contact_type_entry.append(item_id=item_id, item_name=item_name)

        builder.book_contact_type_entry.props.selected = (self.entity.book_contact_type - 1) if self.entity else 0
        builder.book_contact_type_entry.connect('notify::selected-item', self.on_change_any_data_dropdown, 'book_contact_type')

        for item_id, item_name in BOOK_DID.items():
            builder.book_did_entry.append(item_id=item_id, item_name=item_name)

        builder.book_did_entry.props.selected = (self.entity.book_did - 1) if self.entity else 0
        builder.book_did_entry.connect('notify::selected-item', self.on_change_any_data_dropdown, 'book_did')

        # Bottom Controllers

        if self.entity:
            builder.contacts_column_view.update_list()
            builder.communities_column_view.update_list()
            builder.meetings_column_view.update_list()
            builder.tasks_column_view.update_list()
            builder.humans_column_view.update_list()

        self.on_change_birth_date(None)

    def on_change_birth_date(self, spin_button):
        birth_date = date(
            self.birth_year_entry.get_value_as_int() or 1,
            self.birth_month_entry.get_value_as_int() or 1,
            self.birth_day_entry.get_value_as_int() or 1,
        )
        age_timedelta = date.today() - birth_date
        self.age_value.set_text(f'{age_timedelta.days // 365} лет')

    def on_sector_edit_clicked(self, button):
        window = EntityListWindow(Sector, transient_for=self, title='Sector List', modal=True)
        window.present()     


class ContactTypeWindow(EntityEditWindow, Gtk.ApplicationWindow):
    entity_name = 'contact_type'
    entity_class = db.ContactType

    def __init__(self, *args,  **kwargs):
        super().__init__(*args, **kwargs)
        builder = WindowBuilder(BASE_DIR / 'contact_type.xml', {'entity': self.entity})
        self.set_child(builder.grid)
        self.id_value = builder.id_value
        builder.name_entry.connect('changed', self.on_change_any_data, 'name')


class SectorWindow(EntityEditWindow, Gtk.ApplicationWindow):
    entity_name = 'sector'
    entity_class = db.Sector

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        builder = WindowBuilder(BASE_DIR / 'sector.xml', {'entity': self.entity})
        self.set_child(builder.grid)
        self.id_value = builder.id_value
        builder.name_entry.connect('changed', self.on_change_any_data, 'name')


class CommunityWindow(EntityEditWindow, Gtk.ApplicationWindow):
    entity_name = 'community'
    entity_class = db.Community

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        builder = WindowBuilder(BASE_DIR / 'community.xml', {'entity': self.entity}, parent_window=self)
        self.set_child(builder.grid)
        self.id_value = builder.id_value
        builder.name_entry.connect('changed', self.on_change_any_data, 'name')
        if self.entity:
            builder.humans_column_view.update_list()
            builder.contacts_column_view.update_list()
            builder.tasks_column_view.update_list()


class TaskWindow(EntityEditWindow, Gtk.ApplicationWindow):
    entity_name = 'task'
    entity_class = db.Task

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        builder = WindowBuilder(BASE_DIR / 'task.xml', {'entity': self.entity}, parent_window=self)
        self.set_child(builder.grid)
        self.id_value = builder.id_value
        builder.title_entry.connect('changed', self.on_change_any_data, 'title')

        for task_aim in dbapi.session.scalars(select(db.TaskAim)):
            builder.aim_entry.append(item_id=task_aim.id, item_name=task_aim.name)

        builder.aim_entry.props.selected = (self.entity.aim.id - 1) if self.entity else 0
        builder.aim_entry.connect('notify::selected-item', self.on_change_any_data_dropdown, 'aim_id')
        builder.aim_edit_button.connect('clicked', self.on_aim_edit_clicked)
        if self.entity:
            builder.humans_column_view.update_list()
            builder.communities_column_view.update_list()

    def on_aim_edit_clicked(self, button):
        window = EntityListWindow(TaskAim, transient_for=self, title='Task Aim List', modal=True)
        window.present()


class TaskAimWindow(EntityEditWindow, Gtk.ApplicationWindow):
    entity_name = 'task_aim'
    entity_class = db.TaskAim

    def __init__(self, *args,  **kwargs):
        super().__init__(*args, **kwargs)
        builder = WindowBuilder(BASE_DIR / 'task_aim.xml', {'entity': self.entity})
        self.set_child(builder.grid)
        self.id_value = builder.id_value
        builder.name_entry.connect('changed', self.on_change_any_data, 'name')


class MeetingWindow(EntityEditWindow, Gtk.ApplicationWindow):
    entity_name = 'meeting'
    entity_class = db.Meeting

    def __init__(self, *args,  **kwargs):
        super().__init__(*args, **kwargs)
        builder = WindowBuilder(BASE_DIR / 'meeting.xml', {'entity': self.entity}, parent_window=self)
        self.set_child(builder.grid)
        self.id_value = builder.id_value
        builder.title_entry.connect('changed', self.on_change_any_data, 'title')
        #builder.description_entry.connect('changed', self.on_change_any_data, 'description')
        if self.entity:
            builder.humans_column_view.update_list()


class ContactWindow(EntityEditWindow, Gtk.ApplicationWindow):
    entity_name = 'contact'
    entity_class = db.Contact

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.set_default_size(400, 600)
        builder = WindowBuilder(BASE_DIR / 'contact.xml', {'entity': self.entity}, parent_window=self)
        self.set_child(builder.grid)
        self.id_value = builder.id_value
        builder.value_entry.connect('changed', self.on_change_any_data, 'value')
        for contact_type in dbapi.session.scalars(select(db.ContactType)):
            builder.type_entry.append(item_id=contact_type.id, item_name=contact_type.name)

        builder.type_entry.props.selected = (self.entity.type_id - 1) if self.entity else 0
        builder.type_entry.connect('notify::selected-item', self.on_change_any_data_dropdown, 'type_id')
        builder.type_edit_button.connect('clicked', self.on_type_edit_clicked)
        for item_id, item_name in CONTACT_STATUSES.items():
            builder.status_entry.append(item_id=item_id, item_name=item_name)

        builder.status_entry.props.selected = (self.entity.status - 1) if self.entity else 0
        builder.status_entry.connect('notify::selected-item', self.on_change_any_data_dropdown, 'status')
        if self.entity:
            builder.humans_column_view.update_list()
            builder.communities_column_view.update_list()
    
    def on_type_edit_clicked(self, button):
        window = EntityListWindow(ContactType, transient_for=self, title='Contact Type List', modal=True)
        window.present()

 
class Human(GObject.Object):
    __gtype_name__  = 'Human'
    columns = (('ID', 'entity_id', FIELD_ID_SIZE), ('Фамилия', 'human_family_name', 150), ('Имя', 'human_first_name', 150))
    window = HumanWindow
    
    def __init__(self, entity_id, human_first_name, human_family_name):
        super().__init__()
        self._entity_id = entity_id
        self._human_first_name = human_first_name
        self._human_family_name = human_family_name

    @classmethod
    def from_db_object(cls, db_object):
        return cls(
            entity_id=db_object.id,
            human_first_name=db_object.first_name,
            human_family_name=db_object.family_name,
        )

    @GObject.Property(type=int)
    def entity_id(self):
        return self._entity_id

    @GObject.Property(type=str)
    def human_first_name(self):
        return self._human_first_name

    @GObject.Property(type=str)
    def human_family_name(self):
        return self._human_family_name


class Contact(GObject.Object):
    __gtype_name__  = 'Contact'
    columns = (('ID', 'entity_id', FIELD_ID_SIZE), ('Тип', 'contact_type', 80), ('Значение', 'contact_value', 150), ('Статус', 'contact_status', 150))
    window = ContactWindow

    def __init__(self, entity_id, contact_type, contact_value, contact_status):
        super().__init__()
        self._entity_id = entity_id
        self._contact_type = contact_type
        self._contact_value = contact_value
        self._contact_status = contact_status

    @classmethod
    def from_db_object(cls, db_object):
        return cls(
            entity_id=db_object.id,
            contact_type=db_object.type.name,
            contact_value=db_object.value,
            contact_status=CONTACT_STATUSES[db_object.status],
        )

    @GObject.Property(type=int)
    def entity_id(self):
        return self._entity_id

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
    columns = (('ID', 'entity_id', FIELD_ID_SIZE), ('Название', 'contact_type_name', None))
    window = ContactTypeWindow
    
    def __init__(self, entity_id, contact_type_name):
        super().__init__()
        self._entity_id = entity_id
        self._contact_type_name = contact_type_name

    @classmethod
    def from_db_object(cls, db_object):
        return cls(
            entity_id=db_object.id,
            contact_type_name=db_object.name,
        )

    @GObject.Property(type=int)
    def entity_id(self):
        return self._entity_id

    @GObject.Property(type=str)
    def contact_type_name(self):
        return self._contact_type_name


class Sector(GObject.Object):
    __gtype_name__  = 'Sector'
    columns = (('ID', 'entity_id', FIELD_ID_SIZE), ('Название', 'sector_name', None))
    window = SectorWindow

    def __init__(self, entity_id, sector_name):
        super().__init__()
        self._entity_id = entity_id
        self._sector_name = sector_name

    @classmethod
    def from_db_object(cls, db_object):
        return cls(
            entity_id=db_object.id,
            sector_name=db_object.name,
        )

    @GObject.Property(type=int)
    def entity_id(self):
        return self._entity_id

    @GObject.Property(type=str)
    def sector_name(self):
        return self._sector_name


class Community(GObject.Object):
    __gtype_name__  = 'Community'
    columns =  (('ID', 'entity_id', FIELD_ID_SIZE), ('Название', 'community_name', None))
    window = CommunityWindow

    def __init__(self, entity_id, community_name):
        super().__init__()
        self._entity_id = entity_id
        self._community_name = community_name

    @classmethod
    def from_db_object(cls, db_object):
        return cls(
            entity_id=db_object.id,
            community_name=db_object.name,
        )

    @GObject.Property(type=int)
    def entity_id(self):
        return self._entity_id

    @GObject.Property(type=str)
    def community_name(self):
        return self._community_name


class Task(GObject.Object):
    __gtype_name__  = 'Task'
    columns =  (('ID', 'entity_id', FIELD_ID_SIZE), ('Название', 'task_title', 400))
    window = TaskWindow
    
    @classmethod
    def from_db_object(cls, db_object):
        return cls(
            entity_id=db_object.id,
            task_title=db_object.title
        )

    def __init__(self, entity_id, task_title):
        super().__init__()
        self._entity_id = entity_id
        self._task_title = task_title

    @GObject.Property(type=int)
    def entity_id(self):
        return self._entity_id

    @GObject.Property(type=str)
    def task_title(self):
        return self._task_title


class TaskAim(GObject.Object):
    __gtype_name__  = 'TaskAim'
    columns = (('ID', 'entity_id', FIELD_ID_SIZE), ('Название', 'task_aim_name', None))
    window = TaskAimWindow
    
    def __init__(self, entity_id, task_aim_name):
        super().__init__()
        self._entity_id = entity_id
        self._task_aim_name = task_aim_name

    @classmethod
    def from_db_object(cls, db_object):
        return cls(
            entity_id=db_object.id,
            task_aim_name=db_object.name,
        )

    @GObject.Property(type=int)
    def entity_id(self):
        return self._entity_id

    @GObject.Property(type=str)
    def task_aim_name(self):
        return self._task_aim_name


class Meeting(GObject.Object):
    __gtype_name__  = 'Meeting'
    columns = (('ID', 'entity_id', FIELD_ID_SIZE), ('Название', 'meeting_title', 400))
    window = MeetingWindow

    def __init__(self, entity_id, meeting_title):
        super().__init__()
        self._entity_id = entity_id
        self._meeting_title = meeting_title

    @classmethod
    def from_db_object(cls, db_object):
        return cls(
            entity_id=db_object.id,
            meeting_title=db_object.title,
        )

    @GObject.Property(type=int)
    def entity_id(self):
        return self._entity_id

    @GObject.Property(type=str)
    def meeting_title(self):
        return self._meeting_title


class AppWindow(Gtk.ApplicationWindow):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.set_default_size(600, 400)
        self.props.show_menubar = True
        
        builder = WindowBuilder(BASE_DIR / 'app.xml', {})
        self.set_child(builder.box)

        action_show_map = Gio.SimpleAction.new('show_map', None)
        action_show_map.connect('activate', self.on_show_map)
        self.add_action(action_show_map)

        builder.box.props.orientation = Gtk.Orientation.HORIZONTAL
        builder.left_box.props.orientation = Gtk.Orientation.VERTICAL
        builder.main_box.props.orientation = Gtk.Orientation.VERTICAL

        builder.button_show_human.connect('clicked', self.on_show_entities, Human, db.Human)
        builder.button_show_community.connect('clicked', self.on_show_entities, Community, db.Community)
        builder.button_show_task.connect('clicked', self.on_show_entities, Task, db.Task)
        builder.button_show_contact.connect('clicked', self.on_show_entities, Contact, db.Contact)
        builder.button_show_meeting.connect('clicked', self.on_show_entities, Meeting, db.Meeting)

        self.main_box = builder.main_box
        self.entities_column_view = None
        self.on_show_entities(None, Human, db.Human)

    def on_show_entities(self, action, entity_class, entity_db_class):
        if self.entities_column_view:
            self.main_box.remove(self.entities_column_view.box)

        self.entities_column_view = EntityColumnView(
            self,
            entity_class,
            lambda widget, _: self.on_entity_added(widget, _, entity_db_class),
        )
        self.update_entity_list(entity_db_class)
        self.main_box.append(self.entities_column_view.box)

    def on_show_map(self, action, value):
        window = CircleMapWindow(dbapi.session, transient_for=self, title='Circle Map', modal=True)
        window.present()

    def on_show_aims(self, action, value):
        pass

    def on_show_adding_entity(self, action, value=None):
        self.entities_column_view.open_item_window()

    def on_show_settings(self, action, value):
        pass

    def on_entity_added(self, widget, _, entity_db_class):
        self.entities_column_view.clear()
        self.update_entity_list(entity_db_class)

    def update_entity_list(self, entity_db_class):
        for entity in dbapi.session.scalars(select(entity_db_class)):
            self.entities_column_view.append(entity)


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


with DBAdapter(DB_PATH) as dbapi:
    app = MyApplication()
    exit_status = app.run(sys.argv)

sys.exit(exit_status)
