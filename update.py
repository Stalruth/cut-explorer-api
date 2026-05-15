#!/usr/bin/env python
import json
import math
import os
import re

import requests

from sqlalchemy import select
from sqlalchemy.exc import NoResultFound, MultipleResultsFound
from sqlalchemy.orm import joinedload, Session

from models import get_engine, Format, SeasonFormat, Tournament, Team, TeamPokemon, PokemonTeratypes, PokemonMoves
from tour_helpers import get_pokedata, get_swiss_rounds, remove_country, remove_cut, pokemon_validator, populate_counts


engine = get_engine()

with Session(engine) as session:
    # get tour
    latest_tour_query = select(Tournament).order_by(Tournament.id.desc()).limit(5)
    results = session.execute(latest_tour_query)
    first_id = ''
    for tour_row in results:
        tour = tour_row.Tournament
        print(f'[{tour.id}] {tour.name}')
        if first_id == '':
            first_id = f'{tour.id}'

    tour_select = input('Enter a Tournament ID (blank for latest): ')
    if len(tour_select) == 0:
        tour_select = first_id
    tour_query = select(Tournament).where(Tournament.id == int(tour_select))
    tournament = session.execute(tour_query).one().Tournament

    pokedata_id = input('Enter the Pokedata ID: ')
    pokedata = get_pokedata(pokedata_id)

    (_, tournament.day2, tournament.cut) = populate_counts(pokedata)
    swiss_day1, swiss_day2 = get_swiss_rounds(len(pokedata))
    swiss = swiss_day1 + swiss_day2

    # Remove DQ'd players
    print('removing DQs')
    for player in [p for p in pokedata if p['placing'] == 9999]:
        player_query = (select(Team)
                        .where(Team.tour == tournament)
                        .where(Team.name == remove_country(player['name']))
                        .where(Team.wins >= player['record']['wins'])
                        .where(Team.losses >= player['record']['losses'])
                        .where(Team.ties >= player['record']['ties']))
        results = session.execute(player_query)
        try:
            team = results.one().Team
            session.delete(team)
        except MultipleResultsFound:
            print(f'uh oh: multiple {player["name"]} match DQ\'d player')
            print('please delete the tournament and re-add from scratch.')
            print('yes this kills all links. sorry.')
        except NoResultFound:
            pass

    for player in pokedata:
        print(player['name'], player['record']['wins'], player['record']['losses'], player['placing'])
        if player['placing'] > max(tournament.kicker, tournament.day2):
            break

        player_query = (select(Team)
                        .where(Team.tour == tournament)
                        .where(Team.name == remove_country(player['name']))
                        .where(Team.wins <= player['record']['wins'])
                        .where(Team.losses <= player['record']['losses'])
                        .where(Team.ties <= player['record']['ties'])
        )
        results = session.execute(player_query)
        try:
            team = results.one().Team
            print('adjusting player')
            (team.wins, team.losses, team.ties) = remove_cut(player, swiss)
            team.place = player['placing']
            rounds = player['record']['wins'] + player['record']['losses'] + player['record']['ties']
            if ((tournament.day2 is not None and team.place > tournament.day2) or
                (tournament.cut is not None and team.place > tournament.cut) or
                (rounds > swiss and player['rounds'][f'{rounds}']['result'] == 'L') or
                (tournament.cut is not None and rounds == swiss + math.ceil(math.log2(tournament.cut)))):
                    team.top = 2 ** math.ceil(math.log2(team.place))
        except MultipleResultsFound:
            print(f'uh oh: multiple {player["name"]} match points earning player')
            print('please delete the tournament and re-add from scratch.')
            print('yes this kills all links. sorry.')
        except NoResultFound:
            print('adding player')
            team = Team()
            team.tour = tournament
            team.name = remove_country(player['name'])
            (team.wins, team.losses, team.ties) = remove_cut(player, swiss)
            team.place = player['placing']
            rounds = team.wins + team.losses + team.ties
            if ((tournament.day2 is not None and team.place > tournament.day2) or
                (tournament.cut is not None and team.place > tournament.cut) or
                (rounds > swiss and player['rounds'][f'{rounds}']['result'] == 'L') or
                (rounds == swiss + math.ceil(math.log2(tournament.cut)))):
                    team.top = 2 ** math.ceil(math.log2(team.place))

            session.add(team)
            print('team added')

            for pokemon_set in player['decklist']:
                valid = pokemon_validator(pokemon_set)
                new_mon = TeamPokemon()
                new_mon.team = team
                new_mon.species = valid['species']
                new_mon.ability = valid['ability']
                new_mon.item = valid['item']
                session.add(new_mon)

                for move in valid['moves']:
                    move_entry = PokemonMoves()
                    move_entry.pokemon = new_mon
                    move_entry.move = move
                    session.add(move_entry)

                if tournament.season_format.format.terastal:
                    teratype = PokemonTeratypes()
                    teratype.teratype = valid['teraType']
                    teratype.pokemon = new_mon
                    session.add(teratype)

    session.commit()
    print('Done!')

