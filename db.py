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

BOOK_CONTACT_TYPE_UNKNOWN = 1
BOOK_CONTACT_TYPE_CONNECTOR = 2
BOOK_CONTACT_TYPE_CAPACITOR = 3
BOOK_CONTACT_TYPE_BRIDGE = 4
BOOK_CONTACT_TYPES = {
    BOOK_CONTACT_TYPE_UNKNOWN: 'Не указано',
    BOOK_CONTACT_TYPE_CONNECTOR: 'Коннектор',
    BOOK_CONTACT_TYPE_CAPACITOR: 'Конденсатор',
    BOOK_CONTACT_TYPE_BRIDGE: 'Мост',
}

BOOK_DID_UNKNOWN = 1
BOOK_DID_DANGEROUS = 2
BOOK_DID_INTERESTING = 3
BOOK_DID_DIFFICULT = 4
BOOK_DID = {
    BOOK_DID_UNKNOWN: 'Не указано',
    BOOK_DID_DANGEROUS: 'Опасен',
    BOOK_DID_INTERESTING: 'Интересен',
    BOOK_DID_DIFFICULT: 'Сложен',
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
    book_contact_type: Mapped[int] = mapped_column(nullable=False, default=BOOK_CONTACT_TYPE_UNKNOWN)
    book_did: Mapped[int] = mapped_column(nullable=False, default=BOOK_DID_UNKNOWN)

    sector_id: Mapped[int] = mapped_column(ForeignKey('sector.id'), nullable=False, default=1)
    sector: Mapped['Sector'] = relationship(back_populates='humans')


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


class Community(Base):
    __tablename__ = 'community'

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)


class Task(Base):
    __tablename__ = 'task'

    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(String(100), nullable=False)


class LinkContactHuman(Base):
    __tablename__ = 'link_contact_human'

    id: Mapped[int] = mapped_column(primary_key=True)
    contact_id: Mapped[int] = mapped_column(ForeignKey('contact.id'), nullable=False)
    human_id: Mapped[int] = mapped_column(ForeignKey('human.id'), nullable=False)
    contact: Mapped['Contact'] = relationship()
    human: Mapped['Human'] = relationship()


class LinkContactCommunity(Base):
    __tablename__ = 'link_contact_community'

    id: Mapped[int] = mapped_column(primary_key=True)
    contact_id: Mapped[int] = mapped_column(ForeignKey('contact.id'), nullable=False)
    community_id: Mapped[int] = mapped_column(ForeignKey('community.id'), nullable=False)


class LinkTaskHuman(Base):
    __tablename__ = 'link_task_human'

    id: Mapped[int] = mapped_column(primary_key=True)
    task_id: Mapped[int] = mapped_column(ForeignKey('task.id'), nullable=False)
    human_id: Mapped[int] = mapped_column(ForeignKey('human.id'), nullable=False)


class LinkTaskCommunity(Base):
    __tablename__ = 'link_task_community'

    id: Mapped[int] = mapped_column(primary_key=True)
    task_id: Mapped[int] = mapped_column(ForeignKey('task.id'), nullable=False)
    community_id: Mapped[int] = mapped_column(ForeignKey('community.id'), nullable=False)


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

    def get_contacts(self):
        return self.session.scalars(select(Contact))

    def get_communities(self):
        return self.session.scalars(select(Community))

    def get_tasks(self):
        return self.session.scalars(select(Task))

