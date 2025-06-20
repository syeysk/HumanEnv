from gi.repository import Gtk, Gio, GObject
import gi

gi.require_version("Gtk", "4.0")


class DataObject(GObject.Object):
    __gtype_name__  = 'DataObject'

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


#def setup(widget, item):
#    """Setup the widget to show in the Gtk.Listview"""
#    label = Gtk.Label()
#    item.set_child(label)


#def bind(widget, item):
#    """bind data from the store object to the widget"""
#    label = item.get_child()
#    obj = item.get_item()

#    label.set_text(obj.text)


#def _on_selected_item_notify(dropdown, _):
#        item = dropdown.get_selected_item()
#        print(item.text)

def on_activate(app):
    win = Gtk.ApplicationWindow(
        application=app,
        title="Gtk4 is Awesome !!!",
        default_height=400,
        default_width=400,
    )
    sw = Gtk.ScrolledWindow()
    box = Gtk.Box() 
    #drop_down = Gtk.DropDown.new()
    #factory = Gtk.SignalListItemFactory()
    button = Gtk.Button.new_with_label("Add new drink: Honey")
    #factory.connect("setup", setup)
    #factory.connect("bind", bind)

    #drop_down.set_factory(factory)

    #selection = Gtk.SingleSelection()

    #store = Gio.ListStore.new(DataObject)

    #selection.set_model(store)

    #drop_down.set_model(selection)

    #drop_down.connect("notify::selected-item", _on_selected_item_notify)
    #button.connect("clicked", lambda _: store.append(DataObject("honey")))

    EXAMPLE_COFFEES_LIST = [
    "Espresso",
    "Americano",
    "Latte",
    "Cappuccino",
    "Mocha",
    "Macchiato",
    "Flat White",
    "Affogato",
    "Cold Brew",
    "Nitro Coffee",
    "Turkish Coffee",
    "Irish Coffee",
    "Ristretto",
    "Doppio",
    "Café au Lait",
    "Vienna Coffee",
    "Café con Leche",
    "Iced Coffee",
    "Breve",
    "Coffee Milk",
]
    
    for name in EXAMPLE_COFFEES_LIST:
        store.append(DataObject(name))

    sw.set_child(box)
    box.append(drop_down)
    box.append(button)
    win.set_child(sw)
    win.present()


class UniDropDown:
    def __init__(self, items):
        drop_down = Gtk.DropDown.new()
        factory = Gtk.SignalListItemFactory()
        factory.connect('setup', self.on_setup)
        factory.connect('bind', self.on_bind)
        drop_down.set_factory(factory)
        selection = Gtk.SingleSelection()
        store = Gio.ListStore.new(DataObject)
        selection.set_model(store)
        drop_down.set_model(selection)
        drop_down.connect("notify::selected-item", self.on_selected_item)

    def on_setup(self, widget, item):
        """Setup the widget to show in the Gtk.Listview"""
        label = Gtk.Label()
        item.set_child(label)

    def on_bind(self, widget, item):
        """bind data from the store object to the widget"""
        label = item.get_child()
        obj = item.get_item()
        label.set_text(obj.name)

    def on_selected_item(self, dropdown, _):
        item = dropdown.get_selected_item()
        print(item.name)

    def append(self, item_id, item_name):
        store.append(DataObject(item_id, item_name))
