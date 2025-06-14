from typing import List, Optional
from sqlalchemy import ForeignKey, String, select, insert, create_engine, update
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column, relationship

CIRCLE_DEVELOP = 1
CIRCLE_EFFECTIVITY = 2
CIRCLE_SUPPORT = 3
CIRCLES = {
    CIRCLE_DEVELOP: 'Развития',
    CIRCLE_EFFECTIVITY: 'Продуктивности', 
    CIRCLE_SUPPORT: 'Поддержки',
}

SEX_UNKNOWN = 1
SEX_MALE = 2
SEX_FEMALE = 3
SEXES = {
    SEX_UNKNOWN:  'Неизвестно',
    SEX_MALE: 'Мужчина',
    SEX_FEMALE:  'Женщина',
}

CONTACT_STATUS_ACTIVE = 1
CONTACT_STATUS_INACTIVE = 2
CONTACT_STATUS_DELETED = 3
CONTACT_STATUSES = {
    CONTACT_STATUS_ACTIVE: 'Активен',
    CONTACT_STATUS_INACTIVE: 'Неактивен',
    CONTACT_STATUS_DELETED: 'Удалён аккаунт',
}


class Base(DeclarativeBase):
    pass


class Sector(Base):
    __tablename__ = 'sector'

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)

    humans: Mapped[List['Human']] = relationship(back_populates='sector', cascade='all, delete-orphan')


class Human(Base):
    __tablename__ = 'human'

    id: Mapped[int] = mapped_column(primary_key=True)
    family_name: Mapped[str] = mapped_column(String(100), nullable=False, default='')
    first_name: Mapped[str] = mapped_column(String(100), nullable=False, default='')
    father_name: Mapped[str] = mapped_column(String(100), nullable=False, default='')
    birth_year: Mapped[int] = mapped_column(nullable=False, default=0)
    birth_month: Mapped[int] = mapped_column(nullable=False, default=0)
    birth_day: Mapped[int] = mapped_column(nullable=False, default=0)
    circle: Mapped[int] = mapped_column(nullable=False, default=CIRCLE_DEVELOP)
    sex: Mapped[int] = mapped_column(nullable=False, default=SEX_UNKNOWN)
    closing: Mapped[int] = mapped_column(nullable=False, default=0)

    sector_id: Mapped[int] = mapped_column(ForeignKey('sector.id'), nullable=False, default=1)
    sector: Mapped['Sector'] = relationship(back_populates='humans')

    contacts: Mapped[List['Contact']] = relationship(back_populates='human', cascade='all, delete-orphan')


class ContactType(Base):
    __tablename__ = 'contact_type'

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)


class Contact(Base):
    __tablename__ = 'contact'

    id: Mapped[int] = mapped_column(primary_key=True)
    value: Mapped[str] = mapped_column(String(100), nullable=False, default='')
    type_id: Mapped[int] = mapped_column(ForeignKey('contact_type.id'), nullable=False, default=1)
    type: Mapped['ContactType'] = relationship()
    status: Mapped[int] = mapped_column(nullable=False, default=CONTACT_STATUS_ACTIVE)
    human_id: Mapped[int] = mapped_column(ForeignKey('human.id'))
    human: Mapped['Human'] = relationship(back_populates='contacts')


class Community(Base):
    __tablename__ = 'community'

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)


class Task(Base):
    __tablename__ = 'task'

    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(String(100), nullable=False)


class DBAdapter:
    def __init__(self, dbpath):
        db_path_with_protocol = f'sqlite:///{dbpath}'
        self.engine = create_engine(db_path_with_protocol, echo=True)
        #self.engine = create_engine('sqlite://', echo=True)
        Base.metadata.create_all(self.engine)

    def __enter__(self):
        self.session_obj = Session(self.engine)
        self.session = self.session_obj.__enter__()

        '''
        contact_types = (
            (1, 'Не указано'),
            (2, 'Телефон'),
            (3, 'ВКонтакте'),
            (4, 'Telegram'),
        )
        for contact_type_id, contact_type_name in contact_types:
            contact_type = ContactType(id=contact_type_id, name=contact_type_name)
            self.session.add(contact_type)

        sectors = (
            (1, 'Не указано'),
            (2, 'Университет'),
            (3, 'Работа'),
            (4, 'Клуб'),
        )
        for sector_id, sector_name in sectors:
            sector = Sector(id=sector_id, name=sector_name)
            self.session.add(sector)

        self.session.commit()
        '''
        return self

    def __exit__(self, type, value, traceback):
         self.session.__exit__(type, value, traceback)

    def get_humans(self):
        return self.session.scalars(select(Human))

    def get_contact_types(self):
        return self.session.scalars(select(ContactType))

    def get_sectors(self):
        return self.session.scalars(select(Sector))

    def add_contact(self, human_id, **kwargs):
        contact = Contact(human_id=human_id, **kwargs)
        self.session.add(contact)
        self.session.commit()
        return contact

    def get_contacts(self):
        return self.session.scalars(select(Contact))

    def get_communities(self):
        return self.session.scalars(select(Community))

    def get_tasks(self):
        return self.session.scalars(select(Task))

