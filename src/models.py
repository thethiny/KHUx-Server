from datetime import datetime
from typing import Optional

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    LargeBinary,
    String,
    create_engine,
)
from sqlalchemy.orm import (
    DeclarativeBase,
    Mapped,
    mapped_column,
    relationship,
    sessionmaker,
)


class Base(DeclarativeBase):
    pass


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    uuid: Mapped[str] = mapped_column(String, unique=True, index=True)
    native_user_id: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    user_name: Mapped[str] = mapped_column(String, default="Player")
    gender: Mapped[int] = mapped_column(Integer, default=0)
    comment: Mapped[str] = mapped_column(String, default="")
    platform_id: Mapped[int] = mapped_column(Integer, default=2)
    device_type: Mapped[int] = mapped_column(Integer, default=2)
    level: Mapped[int] = mapped_column(Integer, default=1)
    exp: Mapped[int] = mapped_column(Integer, default=0)
    money: Mapped[int] = mapped_column(Integer, default=0)
    lux: Mapped[int] = mapped_column(Integer, default=0)
    total_lux: Mapped[int] = mapped_column(Integer, default=0)
    free_stone: Mapped[int] = mapped_column(Integer, default=300)
    pay_stone: Mapped[int] = mapped_column(Integer, default=0)
    ap: Mapped[int] = mapped_column(Integer, default=16)
    max_ap: Mapped[int] = mapped_column(Integer, default=16)
    hp: Mapped[int] = mapped_column(Integer, default=3000)
    max_hp: Mapped[int] = mapped_column(Integer, default=3000)
    base_hp: Mapped[int] = mapped_column(Integer, default=3000)
    attack: Mapped[int] = mapped_column(Integer, default=0)
    defense: Mapped[int] = mapped_column(Integer, default=0)
    max_deck_cost: Mapped[int] = mapped_column(Integer, default=74)
    max_medal: Mapped[int] = mapped_column(Integer, default=100)
    lux_rank: Mapped[int] = mapped_column(Integer, default=0)
    lux_get_ratio: Mapped[int] = mapped_column(Integer, default=100)
    mvp_count: Mapped[int] = mapped_column(Integer, default=0)
    last_clear_stage_id: Mapped[int] = mapped_column(Integer, default=0)
    equip_coordinate_no: Mapped[int] = mapped_column(Integer, default=0)
    title_left_id: Mapped[int] = mapped_column(Integer, default=0)
    title_right_id: Mapped[int] = mapped_column(Integer, default=0)
    title_plate_id: Mapped[int] = mapped_column(Integer, default=0)
    continue_login_count: Mapped[int] = mapped_column(Integer, default=0)
    union_id: Mapped[int] = mapped_column(Integer, default=0)
    hair_parts_id: Mapped[int] = mapped_column(Integer, default=40001)
    hair_color_parts_id: Mapped[int] = mapped_column(Integer, default=0)
    face_parts_id: Mapped[int] = mapped_column(Integer, default=20001)
    body_parts_id: Mapped[int] = mapped_column(Integer, default=30001)
    skin_parts_id: Mapped[int] = mapped_column(Integer, default=0)
    accessories_parts_ids: Mapped[str] = mapped_column(String, default="")
    is_guilt: Mapped[bool] = mapped_column(Boolean, default=False)
    tutorial_done: Mapped[bool] = mapped_column(Boolean, default=False)
    tutorial_stage_reached: Mapped[bool] = mapped_column(Boolean, default=False)
    tutorial_progression: Mapped[int] = mapped_column(Integer, default=0)
    tutorial_phase: Mapped[int] = mapped_column(Integer, default=50)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    last_login_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    sessions: Mapped[list["Session"]] = relationship(back_populates="user")
    medals: Mapped[list["UserMedal"]] = relationship(back_populates="user")
    keyblades: Mapped[list["UserKeyblade"]] = relationship(back_populates="user")
    materials: Mapped[list["UserMaterial"]] = relationship(back_populates="user")


class Session(Base):
    __tablename__ = "sessions"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    session_id: Mapped[str] = mapped_column(String, unique=True)
    security_key: Mapped[bytes] = mapped_column(LargeBinary(32))
    native_token: Mapped[str] = mapped_column(String)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    last_active_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    user: Mapped["User"] = relationship(back_populates="sessions")


class UserMedal(Base):
    __tablename__ = "user_medals"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    medal_id: Mapped[int] = mapped_column(Integer)
    level: Mapped[int] = mapped_column(Integer, default=1)
    exp: Mapped[int] = mapped_column(Integer, default=0)
    attack_upper: Mapped[int] = mapped_column(Integer, default=0)
    defense_upper: Mapped[int] = mapped_column(Integer, default=0)
    burst_upper: Mapped[int] = mapped_column(Integer, default=0)
    lock: Mapped[bool] = mapped_column(Boolean, default=False)
    upper_cost: Mapped[int] = mapped_column(Integer, default=0)
    guilt_factor: Mapped[int] = mapped_column(Integer, default=0)
    skill_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    user: Mapped["User"] = relationship(back_populates="medals")


class UserKeyblade(Base):
    __tablename__ = "user_keyblades"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    keyblade_id: Mapped[int] = mapped_column(Integer)
    is_favorite: Mapped[bool] = mapped_column(Boolean, default=False)

    user: Mapped["User"] = relationship(back_populates="keyblades")


class UserMaterial(Base):
    __tablename__ = "user_materials"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    material_id: Mapped[int] = mapped_column(Integer)
    number: Mapped[int] = mapped_column(Integer, default=0)

    user: Mapped["User"] = relationship(back_populates="materials")


def get_engine(db_path: str = "khux.db"):
    return create_engine(f"sqlite:///{db_path}", echo=False)


def create_tables(engine):
    from sqlalchemy import inspect, text
    inspector = inspect(engine)
    if inspector.has_table("_meta"):
        with engine.connect() as conn:
            row = conn.execute(text("SELECT created_at FROM _meta LIMIT 1")).fetchone()
            if row:
                print(f"  DB created @ {row[0]}")
        _migrate(engine, inspector)
    else:
        Base.metadata.create_all(engine)
        with engine.connect() as conn:
            conn.execute(text("CREATE TABLE IF NOT EXISTS _meta (created_at TEXT)"))
            now = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
            conn.execute(text(f"INSERT INTO _meta VALUES ('{now}')"))
            conn.commit()
            print(f"  Creating DB @ {now}")


def _migrate(engine, inspector):
    from sqlalchemy import text
    existing = {col["name"] for col in inspector.get_columns("users")}
    new_cols = {
        "hair_parts_id": "INTEGER DEFAULT 40001",
        "hair_color_parts_id": "INTEGER DEFAULT 0",
        "face_parts_id": "INTEGER DEFAULT 20001",
        "body_parts_id": "INTEGER DEFAULT 30001",
        "skin_parts_id": "INTEGER DEFAULT 0",
        "accessories_parts_ids": "VARCHAR DEFAULT ''",
        "tutorial_phase": "INTEGER DEFAULT 50",
    }
    added = []
    with engine.connect() as conn:
        for col, typedef in new_cols.items():
            if col not in existing:
                conn.execute(text(f"ALTER TABLE users ADD COLUMN {col} {typedef}"))
                added.append(col)
        if added:
            conn.commit()
            print(f"  Migrated: added {', '.join(added)}")


def get_session(engine):
    return sessionmaker(bind=engine)
