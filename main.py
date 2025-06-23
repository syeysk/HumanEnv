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
from sqlalchemy import select

gi.require_version("Gtk", "4.0")
from gi.repository import GLib, Gio, Gtk, GObject

BASE_DIR = Path(__file__).resolve().parent
MENU_MAIN_PATH = BASE_DIR / 'menu_main.xml'
#WIDGET_MAIN_PATH = BASE_DIR / 'widget_main.xml'
DEFAULT_DB_PATH = BASE_DIR / 'default.db'
FIELD_ID_SIZE = 30
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

    def __init__(self, parent_window, item_type, on_item_created=None, on_delete_clicked=None):
        # Buttons

        self.parent_window = parent_window
        self.on_item_created = on_item_created

        self.buttons_box = Gtk.Box(spacing=6)
        self.buttons_box.props.orientation = Gtk.Orientation.HORIZONTAL
        
        delete_button = Gtk.Button(label='Удалить')
        if on_delete_clicked:
            delete_button.connect('clicked', on_delete_clicked)

        add_button = Gtk.Button(label='Добавить')
        add_button.connect('clicked', self.on_add_item_clicked)

        select_button = Gtk.Button(label='Выбрать')

        self.buttons_box.append(delete_button)
        self.buttons_box.append(add_button)
        self.buttons_box.append(select_button)

        # Item's list
    
        self.item_type_class = item_type
        self.list_store = Gio.ListStore(item_type=item_type)
        selection = Gtk.SingleSelection(model=self.list_store)
        self.view = Gtk.ColumnView(model=selection)
        self.view.connect('activate', self.on_activate_item)
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

            self.view.append_column(column)

    def append(self, db_object):
         self.list_store.append(self.item_type_class.from_db_object(db_object))

    def clear(self):
        self.list_store.remove_all()

    def open_item_window(self, entity_id=None):
        window = self.item_type_class.window(
            transient_for=self.parent_window,
            title=self.item_type_class.__gtype_name__,
            modal=True,
            entity_id=entity_id,
        )
        window.connect('entity_added', self.on_item_created)
        window.present()

    def on_activate_item(self, column_view, position):
        item = self.list_store.get_item(position)
        self.open_item_window(item.entity_id)

    def on_add_item_clicked(self, _):
        self.open_item_window()


class EntityListWindow(Gtk.ApplicationWindow):
    entity_type_class = None
    entity_db_class = None

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        box = Gtk.Box()
        box.props.orientation = Gtk.Orientation.VERTICAL
        self.set_child(box)
        self.column_view = EntityColumnView(
            self,
            self.entity_type_class,
            self.on_entity_added,
        )
        box.append(self.column_view.buttons_box)
        box.append(self.column_view.view)
        self.update_entity_list()

    def on_entity_added(self, widget, _):
        self.column_view.clear()
        self.update_entity_list()

    def update_entity_list(self):
        for entity in dbapi.session.scalars(select(self.entity_db_class)):
            self.column_view.append(entity)


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
        id_label.props.xalign = 0
        self.id_value = Gtk.Label(label=self.entity.id if self.entity else '')

        sex_label = Gtk.Label(label='Пол')
        sex_label.props.xalign = 0
        sex_entry = Gtk.DropDown()
        sex_entry.props.model = UniDropDown(tupples=tuple(SEXES.items()))
        sex_entry.props.selected = (self.entity.sex - 1) if self.entity else 0
        sex_entry.connect('notify::selected-item', self.on_change_any_data_dropdown, 'sex')

        birth_year_adjustment = Gtk.Adjustment(upper=3000, step_increment=1, page_increment=10)
        birth_month_adjustment = Gtk.Adjustment(upper=12, step_increment=1, page_increment=10)
        birth_day_adjustment = Gtk.Adjustment(upper=31, step_increment=1, page_increment=10)

        birth_year_label = Gtk.Label(label='Год рождения')
        birth_year_label.props.xalign = 0
        self.birth_year_entry = Gtk.SpinButton()
        self.birth_year_entry.props.adjustment = birth_year_adjustment
        self.birth_year_entry.set_value(int(self.entity.birth_year) if self.entity else 0)
        self.birth_year_entry.connect('changed', self.on_change_birth_date)
        self.birth_year_entry.connect('changed', self.on_change_any_data, 'birth_year')

        birth_month_label = Gtk.Label(label='Месяц рождения')
        birth_month_label.props.xalign = 0
        self.birth_month_entry = Gtk.SpinButton()
        self.birth_month_entry.props.adjustment = birth_month_adjustment
        self.birth_month_entry.set_value(int(self.entity.birth_month) if self.entity else 0)
        self.birth_month_entry.connect('changed', self.on_change_birth_date)
        self.birth_month_entry.connect('changed', self.on_change_any_data, 'birth_month')

        birth_day_label = Gtk.Label(label='День рождения')
        birth_day_label.props.xalign = 0
        self.birth_day_entry = Gtk.SpinButton()
        self.birth_day_entry.props.adjustment = birth_day_adjustment
        self.birth_day_entry.set_value(int(self.entity.birth_day) if self.entity else 0)
        self.birth_day_entry.connect('changed', self.on_change_birth_date)
        self.birth_day_entry.connect('changed', self.on_change_any_data, 'birth_day')

        age_label = Gtk.Label(label='Возраст:')
        age_label.props.xalign = 0
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
        family_name_label.props.xalign = 0
        family_name_entry = Gtk.Entry(text=self.entity.family_name if self.entity else '')
        family_name_entry.connect('changed', self.on_change_any_data, 'family_name')
        first_name_label = Gtk.Label(label='Имя')
        first_name_label.props.xalign = 0
        first_name_entry = Gtk.Entry(text=self.entity.first_name if self.entity else '')
        first_name_entry.connect('changed', self.on_change_any_data, 'first_name')
        father_name_label = Gtk.Label(label='Отчество')
        father_name_label.props.xalign = 0
        father_name_entry = Gtk.Entry(text=self.entity.father_name if self.entity else '')
        father_name_entry.connect('changed', self.on_change_any_data, 'father_name')

        closing_adjustment = Gtk.Adjustment(upper=20, step_increment=1, page_increment=10)

        closing_label = Gtk.Label(label='Близость')
        closing_label.props.xalign = 0
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
        circle_label.props.xalign = 0
        
        circle_entry = Gtk.DropDown()
        circle_entry.props.model = UniDropDown(tupples=tuple(CIRCLES.items()))
        circle_entry.props.selected = (self.entity.circle - 1) if self.entity else 0
        circle_entry.connect('notify::selected-item', self.on_change_any_data_dropdown, 'circle')
        top_right_box.attach(circle_label, 0, len(top_right_map), 1, 1)
        top_right_box.attach(circle_entry, 1, len(top_right_map), 2, 1)

        sector_label = Gtk.Label(label='Сектор')
        sector_label.props.xalign = 0
        sector_entry = Gtk.DropDown()
        sector_strings = tuple((sector.id, sector.name) for sector in dbapi.session.scalars(select(db.Sector)))
        sector_entry.props.model = UniDropDown(tupples=sector_strings)
        sector_entry.props.selected = (self.entity.sector_id - 1) if self.entity else 0
        sector_entry.connect('notify::selected-item', self.on_change_any_data_dropdown, 'sector_id')
        sector_edit_button = Gtk.Button(label='Edit')
        sector_edit_button.connect('clicked', self.on_sector_edit_clicked)
        top_right_box.attach(sector_label, 0, len(top_right_map) + 1, 1, 1)
        top_right_box.attach(sector_entry, 1, len(top_right_map) + 1, 1, 1)
        top_right_box.attach(sector_edit_button, 2, len(top_right_map) + 1, 1, 1)

        book_contact_type_label = Gtk.Label(label='Тип контакта')
        book_contact_type_entry = Gtk.DropDown()
        book_contact_type_entry.props.model = UniDropDown(tupples=tuple(BOOK_CONTACT_TYPES.items()))
        book_contact_type_entry.props.selected = (self.entity.book_contact_type - 1) if self.entity else 0
        book_contact_type_entry.connect('notify::selected-item', self.on_change_any_data_dropdown, 'book_contact_type')
        top_right_box.attach(book_contact_type_label, 0, len(top_right_map) + 2, 1, 1)
        top_right_box.attach(book_contact_type_entry, 1, len(top_right_map) + 2, 2, 1)

        book_did_label = Gtk.Label(label='Анализ ОИС')
        book_did_entry = Gtk.DropDown()
        book_did_entry.props.model = UniDropDown(tupples=tuple(BOOK_DID.items()))
        book_did_entry.props.selected = (self.entity.book_did - 1) if self.entity else 0
        book_did_entry.connect('notify::selected-item', self.on_change_any_data_dropdown, 'book_did')
        top_right_box.attach(book_did_label, 0, len(top_right_map) + 3, 1, 1)
        top_right_box.attach(book_did_entry, 1, len(top_right_map) + 3, 2, 1)

        # Bottom Controllers

        self.contacts_column_view = EntityColumnView(
            self,
            Contact,
            self.on_contact_added,
        )
        bottom_box.append(self.contacts_column_view.buttons_box)
        bottom_box.append(self.contacts_column_view.view)

        if self.entity:
            self.update_contact_list()

        links_label = Gtk.Label(label='Links')
        bottom_box.append(links_label)
    
    def update_contact_list(self):
        for link_contact in dbapi.session.scalars(select(db.LinkContactHuman).where(db.LinkContactHuman.human_id==self.entity.id)):
            self.contacts_column_view.append(link_contact.contact)

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

    def on_sector_edit_clicked(self, button):
        window = SectorListWindow(transient_for=self, title='Sector List', modal=True)
        window.present()     


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
                gtkclass = EntityColumnView
            elif tag == 'UniDropDown':
                gtkclass = UniDropDown
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
                kwargs['on_item_created'] = getattr(self.parent_window, node.attrib.pop('on_item_added'))
            
            colspan = int(node.attrib.pop('colspan', '1'))

            gtkelem = gtkclass(**kwargs)
            for attr_name, attr_value in node.attrib.items():
                if attr_name == 'id':
                    setattr(self, attr_value, gtkelem)
                else:
                    if attr_name in {'selected'}:
                        attr_value = int(attr_value) if attr_value else 0

                    setattr(gtkelem.props, attr_name, attr_value)
        
            if self.parents:
                parent_gtk, parent_type, data = self.parents[-1]
                if parent_type == 'Grid':
                    if tag == 'EntityColumnView':
                        parent_gtk.attach(gtkelem.buttons_box, data['x'], data['y'], colspan, 1)
                        parent_gtk.attach(gtkelem.view, data['x'], data['y'] + 1, colspan, 5)
                        data['y'] += 5
                    else:
                        parent_gtk.attach(gtkelem, data['x'], data['y'], colspan, 1)

                    data['x'] += 1
        
            if tag == 'Grid':
                self.parents.append((gtkelem, tag, {'x': 0, 'y': -1}))

        for child in node:
            self._go(child)

        if tag == 'Grid':
            if self.parents:
                self.parents.pop(-1)


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

        self.contacts_column_view = builder.contacts_column_view
        if self.entity:
            self.update_contact_list()

    def on_contact_added(self, widget, contact_id):
        dbapi.session.add(db.LinkContactCommunity(community_id=self.entity.id, contact_id=contact_id))
        dbapi.session.commit()
        self.contacts_column_view.clear()
        self.update_contact_list()

    def update_contact_list(self):
        for link_contact in dbapi.session.scalars(select(db.LinkContactCommunity).where(db.LinkContactCommunity.community_id==self.entity.id)):
            self.contacts_column_view.append(link_contact.contact)


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

        builder.aim_entry.props.selected = self.entity.aim.id if self.entity else 0
        builder.aim_entry.connect('notify::selected-item', self.on_change_any_data_dropdown, 'aim_id')
        builder.aim_edit_button.connect('clicked', self.on_aim_edit_clicked)

        self.humans_column_view = builder.humans_column_view
        if self.entity:
            self.update_human_list()

    def on_human_added(self, widget, human_id):
        dbapi.session.add(db.LinkTaskHuman(task_id=self.entity.id, human_id=human_id))
        dbapi.session.commit()
        self.humans_column_view.clear()
        self.update_human_list()

    def update_human_list(self):
        for link_human in dbapi.session.scalars(select(db.LinkTaskHuman).where(db.LinkTaskHuman.task_id==self.entity.id)):
            self.humans_column_view.append(link_human.human)

    def on_aim_edit_clicked(self, button):
        window = TaskAimListWindow(transient_for=self, title='Task Aim List', modal=True)
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

        self.humans_column_view = builder.humans_column_view
        if self.entity:
            self.update_human_list()

    def on_human_added(self, widget, human_id):
        dbapi.session.add(db.LinkHumanMeeting(meeting_id=self.entity.id, human_id=human_id))
        dbapi.session.commit()
        self.humans_column_view.clear()
        self.update_human_list()

    def update_human_list(self):
        for link_human in dbapi.session.scalars(select(db.LinkHumanMeeting).where(db.LinkHumanMeeting.meeting_id==self.entity.id)):
            self.humans_column_view.append(link_human.human)


class ContactWindow(EntityEditWindow, Gtk.ApplicationWindow):
    entity_name = 'contact'
    entity_class = db.Contact

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.set_default_size(400, 600)

        grid = Gtk.Grid()
        self.set_child(grid)
        
        id_label = Gtk.Label(label='Идентификатор')
        self.id_value = Gtk.Label(label=self.entity.id if self.entity else '')

        value_label = Gtk.Label(label='Значение')
        value_entry = Gtk.Entry(text=self.entity.value if self.entity else '')
        value_entry.connect('changed', self.on_change_any_data, 'value')

        type_label = Gtk.Label(label='Тип')
        type_entry = Gtk.DropDown()
        type_strings = tuple((contact_type.id, contact_type.name) for contact_type in dbapi.session.scalars(select(db.ContactType)))
        type_entry.props.model = UniDropDown(tupples=type_strings)
        type_entry.props.selected = (self.entity.type_id - 1) if self.entity else 0
        type_entry.connect('notify::selected-item', self.on_change_any_data_dropdown, 'type_id')
        type_edit_button = Gtk.Button(label='Edit')
        type_edit_button.connect('clicked', self.on_type_edit_clicked)

        status_label = Gtk.Label(label='Статус')
        status_entry = Gtk.DropDown()
        status_entry.props.model = UniDropDown(tupples=tuple(CONTACT_STATUSES.items()))
        status_entry.props.selected = (self.entity.status - 1) if self.entity else 0
        status_entry.connect('notify::selected-item', self.on_change_any_data_dropdown, 'status')

        top_right_map = (
            (id_label, self.id_value, None),
            (value_label, value_entry, None),
            (type_label, type_entry, type_edit_button),
            (status_label, status_entry, None),
        )
        populate_grid(grid, top_right_map)
        
        self.humans_column_view = EntityColumnView(
            self,
            Human,
            self.on_human_added,
        )
        grid.attach(self.humans_column_view.buttons_box, 0, len(top_right_map), 3, 1)
        grid.attach(self.humans_column_view.view, 0, len(top_right_map) + 1, 3, 5)

        self.communities_column_view = EntityColumnView(
            self,
            Community,
            self.on_community_added,
        )
        grid.attach(self.communities_column_view.buttons_box, 0, len(top_right_map) + 7, 3, 1)
        grid.attach(self.communities_column_view.view, 0, len(top_right_map) + 10, 3, 5)
        if self.entity:
            self.update_human_list()
            self.update_community_list()
    
    def on_type_edit_clicked(self, button):
        window = ContactTypeListWindow(transient_for=self, title='Contact Type List', modal=True)
        window.present()

    def on_human_added(self, widget, human_id):
        dbapi.session.add(db.LinkContactHuman(human_id=human_id, contact_id=self.entity.id))
        dbapi.session.commit()
        self.humans_column_view.clear()
        self.update_human_list()

    def update_human_list(self):
        for link_contact in dbapi.session.scalars(select(db.LinkContactHuman).where(db.LinkContactHuman.contact_id==self.entity.id)):
            self.humans_column_view.append(link_contact.human)

    def on_community_added(self, widget, community_id):
        dbapi.session.add(db.LinkContactCommunity(community_id=community_id, contact_id=self.entity.id))
        dbapi.session.commit()
        self.communities_column_view.clear()
        self.update_community_list()

    def update_community_list(self):
        for link_contact in dbapi.session.scalars(select(db.LinkContactCommunity).where(db.LinkContactCommunity.contact_id==self.entity.id)):
            self.communities_column_view.append(link_contact.community)

 
class Human(GObject.Object):
    __gtype_name__  = 'Human'
    columns = (('ID', 'entity_id', FIELD_ID_SIZE), ('ФИО', 'human_name', None))
    window = HumanWindow
    
    def __init__(self, entity_id, human_name):
        super().__init__()
        self._entity_id = entity_id
        self._human_name = human_name

    @classmethod
    def from_db_object(cls, db_object):
        return cls(
            entity_id=db_object.id,
            human_name=db_object.first_name,
        )

    @GObject.Property(type=int)
    def entity_id(self):
        return self._entity_id

    @GObject.Property(type=str)
    def human_name(self):
        return self._human_name


class Contact(GObject.Object):
    __gtype_name__  = 'Contact'
    columns = (('ID', 'entity_id', FIELD_ID_SIZE), ('Тип', 'contact_type', None), ('Значение', 'contact_value', None), ('Статус', 'contact_status', 150))
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
    columns =  (('ID', 'entity_id', FIELD_ID_SIZE), ('Название', 'task_title', None))
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
    columns = (('ID', 'entity_id', FIELD_ID_SIZE), ('Название', 'meeting_name', None))
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

    @GObject.Property(type=int)
    def meeting_title(self):
        return self._meeting_title


class TaskAimListWindow(EntityListWindow):
    entity_type_class = TaskAim
    entity_db_class = db.TaskAim


class ContactTypeListWindow(EntityListWindow):
    entity_type_class = ContactType
    entity_db_class = db.ContactType


class SectorListWindow(EntityListWindow):
    entity_type_class = Sector
    entity_db_class = db.Sector


class AppWindow(Gtk.ApplicationWindow):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.set_default_size(600, 400)
        self.props.show_menubar = True

        #action_show_contacts = Gio.SimpleAction.new('show_contacts', None)
        #action_show_contacts.connect('activate', self.on_show_entities, Contact, db.Contact)
        #self.add_action(action_show_contacts)

        self.box = Gtk.Box(spacing=6)
        self.box.props.orientation = Gtk.Orientation.HORIZONTAL
        left_box = Gtk.Box(spacing=6)
        left_box.props.orientation = Gtk.Orientation.VERTICAL

        button_show_human = Gtk.Button(label='Human')
        button_show_human.connect('clicked', self.on_show_entities, Human, db.Human)
        left_box.append(button_show_human)

        button_show_community = Gtk.Button(label='Community')
        button_show_community.connect('clicked', self.on_show_entities, Community, db.Community)
        left_box.append(button_show_community)

        button_show_task = Gtk.Button(label='Task')
        button_show_task.connect('clicked', self.on_show_entities, Task, db.Task)
        left_box.append(button_show_task)

        button_show_contact = Gtk.Button(label='Contact')
        button_show_contact.connect('clicked', self.on_show_entities, Contact, db.Contact)
        left_box.append(button_show_contact)

        button_show_meeting = Gtk.Button(label='Meeting')
        button_show_meeting.connect('clicked', self.on_show_entities, Meeting, db.Meeting)
        left_box.append(button_show_meeting)

        self.box.append(left_box)
        self.set_child(self.box)

        self.main_box = None
        self.on_show_entities(None, Human, db.Human)

    def clear_and_init_empty_view(self):
        if self.main_box:
            self.box.remove(self.main_box)

        self.main_box = Gtk.Box(spacing=6)
        self.main_box.props.orientation = Gtk.Orientation.VERTICAL
        self.box.append(self.main_box)

    def on_show_entities(self, action, entity_class, entity_db_class):
        self.clear_and_init_empty_view()
        self.entities_column_view = EntityColumnView(
            self,
            entity_class,
            lambda widget, _: self.on_entity_added(widget, _, entity_db_class),
        )
        self.update_entity_list(entity_db_class)
        self.main_box.append(self.entities_column_view.buttons_box)
        self.main_box.append(self.entities_column_view.view)

    def on_show_map(self, action, value):
        pass

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


with DBAdapter(DEFAULT_DB_PATH) as dbapi:
    app = MyApplication()
    exit_status = app.run(sys.argv)

sys.exit(exit_status)
