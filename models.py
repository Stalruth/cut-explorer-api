from datetime import date
import uuid
import os

from sqlalchemy import create_engine, ForeignKey, Text, Integer
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

from typing import Optional, List


def get_engine():
    password = 'admin123'
    with open(os.environ['DB_PASS'], 'r') as infile:
        password = infile.read().strip()
    print(password)
    return create_engine(
            f'postgresql+psycopg://{os.environ["DB_USER"]}:{password}@localhost/{os.environ["DB_NAME"]}'
    )


class Base(DeclarativeBase):
    pass


class Format(Base):
    __tablename__='format'
    id = mapped_column(Text, primary_key=True)
    name: Mapped[str]
    gscup: Mapped[bool]
    megaevolution: Mapped[bool]
    terastal: Mapped[bool]
    season_formats: Mapped[List['SeasonFormat']] = relationship(back_populates='format')


class SeasonFormat(Base):
    __tablename__='season_formats'
    id = mapped_column(Integer, primary_key=True)
    season: Mapped[int]
    format_id: Mapped[str] = mapped_column(ForeignKey('format.id'))
    start_date: Mapped[date]
    end_date: Mapped[date]
    format: Mapped[Format] = relationship(back_populates='season_formats')
    tournaments: Mapped[List['Tournament']] = relationship(back_populates='season_format')


class Tournament(Base):
    __tablename__='tournament'
    id = mapped_column(Integer, primary_key=True)
    season: Mapped[int]
    season_format_id: Mapped[int] = mapped_column('season_format', ForeignKey('season_formats.id'))
    slug: Mapped[str]
    name: Mapped[str]
    kicker: Mapped[int]
    day2: Mapped[Optional[int]]
    cut: Mapped[Optional[int]]
    season_format: Mapped[SeasonFormat] = relationship(back_populates='tournaments')
    teams: Mapped[List["Team"]] = relationship(back_populates='tour', cascade='all, delete')


class Team(Base):
    __tablename__='team'
    id = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tour_id: Mapped[int] = mapped_column(ForeignKey('tournament.id'))
    name: Mapped[str]
    wins: Mapped[int]
    losses: Mapped[int]
    ties: Mapped[int]
    place: Mapped[int]
    top: Mapped[Optional[int]]
    paste: Mapped[Optional[str]]
    tour: Mapped[Tournament] = relationship(back_populates='teams')
    pokemon: Mapped[List['TeamPokemon']] = relationship(back_populates='team', cascade='all, delete', order_by='TeamPokemon.id')


class TeamPokemon(Base):
    __tablename__='team_pokemon'
    id = mapped_column(Integer, primary_key=True)
    team_id: Mapped[UUID] = mapped_column(ForeignKey('team.id'))
    species: Mapped[str]
    item: Mapped[Optional[str]]
    ability: Mapped[str]
    teratype: Mapped[Optional['PokemonTeratypes']] = relationship(back_populates='pokemon', cascade='all, delete')
    team: Mapped[Team] = relationship(back_populates='pokemon')
    moves: Mapped[List['PokemonMoves']] = relationship(back_populates='pokemon', cascade='all, delete', order_by='PokemonMoves.id')


class PokemonTeratypes(Base):
    __tablename__='pokemon_teratypes'
    pokemon_id = mapped_column(ForeignKey('team_pokemon.id'), primary_key=True)
    teratype: Mapped[str]
    pokemon: Mapped[TeamPokemon] = relationship(back_populates='teratype')


class PokemonMoves(Base):
    __tablename__='pokemon_moves'
    id = mapped_column(Integer, primary_key=True)
    pokemon_id: Mapped[int] = mapped_column(ForeignKey('team_pokemon.id'))
    move: Mapped[str]
    pokemon: Mapped[TeamPokemon] = relationship(back_populates='moves')

