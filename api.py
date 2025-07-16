from pathlib import Path
from uuid import uuid4

from sqlalchemy import select, delete, create_engine, or_

from db import (
    Base,
    ContactType,
    HumanRelationType,
    Sector,
    TaskAim,
)

class Config:
    def __init__(self, base_dir):
        self._dbs_dir = base_dir / 'dbs'
        if not self._dbs_dir.exists():
            self._dbs_dir.mkdir()

        self._last_open_path = self._dbs_dir / 'last_open.txt'
        self._uuid = None
        self._db_dir = None
        self.path = None
        self.name = None
        self._db_name_path = None
        
        if not self._last_open_path.exists():
            self.make_new_db()

    def populate_paths(self):
        self._db_dir = self._dbs_dir / self._uuid
        self.path = self._db_dir / 'sqlite3.db'
        self._db_name_path = self._db_dir / 'name.txt'

    def make_new_db(self, name='Default'):
        """ Генерирует идентификатор новой базы и помечает её как последнюю открытую """
        self._uuid = uuid4().hex
        self.name = name
        with self._last_open_path.open('w') as last_open_file:
            last_open_file.write(self._uuid)

        self.populate_paths()
        self._db_dir.mkdir()
        with self._db_name_path.open('w') as db_name_file:
            db_name_file.write(name)

    def use_last_db(self):
        """Открывает последнюю открытую базу"""
        if not self._uuid:
            with self._last_open_path.open() as last_open_file:
                self._uuid = last_open_file.read()

            self.populate_paths()
            with self._db_name_path.open() as db_name_file:
                self.name = db_name_file.read()


def get_engine_and_create_all(db_apth: Path):
    db_path_with_protocol = f'sqlite:///{db_apth}'
    engine = create_engine(db_path_with_protocol, echo=True)
    #engine = create_engine('sqlite://', echo=True)
    Base.metadata.create_all(engine)
    return engine


def create_first_rows(session):
    FIRST_ID = 1
    FIRST_NAME = 'Не указано'
    models = [ContactType, Sector, TaskAim, HumanRelationType]
    for model in models:
        query = select(model).where(model.id == FIRST_ID)
        if not session.scalars(query).first():
            entity = model(id=FIRST_ID, name=FIRST_NAME)
            session.add(entity)

    session.commit()

