#!/usr/bin/env python
import json
import math
import os
import re

import requests

from sqlalchemy import select
from sqlalchemy.orm import joinedload, Session

from models import get_engine, Format, SeasonFormat, Tournament, Team, TeamPokemon, PokemonTeratypes, PokemonMoves
from tour_helpers import get_pokedata, get_swiss_rounds, remove_country, remove_cut, pokemon_validator, populate_counts


def get_name_slug(season):
    # valid levels:
    #   - regional / Regional Championships
    #   - special / Special Event
    #   - international / International Championships
    #   - worlds / Pokémon World Championships
    # deprecated levels:
    #   - worlds-day1 / Pokémon World Championships (Day 1)
    level = 'regional'
    name_suffix = 'Regional Championships'
    level_input = input('What level was this event? [[R]egional/[s]pecial/[i]nternational/[w]orlds] ')
    if level_input.lower().startswith('s'):
        level = 'special'
        name_suffix = 'Special Event'
    elif level_input.lower().startswith('i'):
        level = 'international'
        name_suffix = 'International Championships'
    elif level_input.lower().startswith('w'):
        return (f'{season} Pokémon World Championships', 'worlds')

    city_name = input('Where was this event held? (City for Reg/Spe, Region for Int) ')
    return (f'{season} {city_name} {name_suffix}', f"{level}-{re.sub('\\s', '-', city_name.lower())}")


engine = get_engine()

with Session(engine) as session:
    # get format
    latest_season_query = select(SeasonFormat).order_by(SeasonFormat.start_date.desc()).limit(1).options(joinedload(SeasonFormat.format))
    result = session.execute(latest_season_query).one().SeasonFormat
    print(f'{result.format.name} ({result.start_date} - {result.end_date})')
    response = input('Is this the current format? [Y/n] ')
    if response.lower().startswith('n'):
        print('then add the new one asshole')
        os.exit(1)

    new_tour = Tournament()
    result = session.execute(latest_season_query).one().SeasonFormat
    tour_format = result.format
    new_tour.season_format = result
    new_tour.season = result.season

    (new_tour.name, new_tour.slug) = get_name_slug(new_tour.season)

    pokedata_id = input('Enter the pokedata ID: ')
    pokedata = get_pokedata(pokedata_id)

    (new_tour.kicker, new_tour.day2, new_tour.cut) = populate_counts(pokedata)
    swiss_day1, swiss_day2 = get_swiss_rounds(len(pokedata))
    swiss = swiss_day1 + swiss_day2

    session.add(new_tour)

    for player in pokedata:
        if player['placing'] > max(new_tour.kicker, new_tour.day2):
            break

        team = Team()
        team.tour = new_tour
        team.name = remove_country(player['name'])
        (team.wins, team.losses, team.ties) = remove_cut(player, swiss)
        team.place = player['placing']
        rounds = player['record']['wins'] + player['record']['losses'] + player['record']['ties']
        if ((new_tour.day2 is not None and team.place > new_tour.day2) or
            (new_tour.cut is not None and team.place > new_tour.cut) or
            (rounds > swiss and player['rounds'][f'{rounds}']['result'] == 'L') or
            (new_tour.cut is not None and rounds == swiss + math.ceil(math.log2(new_tour.cut)))):
                team.top = 2 ** math.ceil(math.log2(team.place))

        session.add(team)

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

            if tour_format.terastal:
                teratype = PokemonTeratypes()
                teratype.teratype = valid['teraType']
                teratype.pokemon = new_mon
                session.add(teratype)

    session.commit()
    print('Done!')

