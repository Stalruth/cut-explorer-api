#!/usr/bin/env python
import json
import math
import os
import re

import requests

from sqlalchemy import func, select
from sqlalchemy.orm import joinedload, Session

from models import get_engine, Format, SeasonFormat, Tournament, Team, TeamPokemon, PokemonTeratypes, PokemonMoves, PokemonNatures
# change pokedata to reportworm
# add get_reportworm and remove_cut_reportworm to tour_helpers
from tour_helpers import get_reportworm, get_swiss_rounds, remove_country, remove_cut_reportworm, pokemon_validator


# change location to arg cos we need that for reportworm
def get_name_slug(season, city_name):
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

    return (f'{city_name} {name_suffix}', f"{level}-{re.sub('\\s', '-', city_name.lower())}")


engine = get_engine()

with Session(engine) as session:
    # get format
    latest_season_query = select(SeasonFormat).order_by(SeasonFormat.start_date.desc()).limit(1).options(joinedload(SeasonFormat.format))
    result = session.execute(latest_season_query).one().SeasonFormat
    print(f'{result.format.name} ({result.start_date} - {result.end_date})')
    response = input('Is this the current format? [Y/n] ')
    if response.lower().startswith('n'):
        # TODO: this
        print('then add the new one asshole')
        os.exit(1)

    new_tour = Tournament()
    result = session.execute(latest_season_query).one().SeasonFormat
    tour_format = result.format
    new_tour.season_format = result
    new_tour.season = result.season
    new_tour.last_modified = func.now()

    city_name = input('Where was this event held? (City for Reg/Spe, Region for Int) ')
    (new_tour.name, new_tour.slug) = get_name_slug(new_tour.season, city_name)

    # TODO: spaces
    # TODO: ICs
    reportworm = get_reportworm(new_tour.season, city_name.lower())

    event = reportworm['event']
    (new_tour.kicker, new_tour.day2, new_tour.cut) = (event['points'], event['phase2Count'], event['cutCount'])
    swiss_day1, swiss_day2 = get_swiss_rounds(event['playerCount'])
    swiss = swiss_day1 + swiss_day2

    session.add(new_tour)
    print(new_tour.id, new_tour.season, new_tour.name, new_tour.kicker, new_tour.day2, new_tour.cut)

    for (pid, player) in reportworm['standings'].items():
        if player['place'] > max(new_tour.kicker, new_tour.day2):
            break

        team = Team()
        team.tour = new_tour
        team.name = player['name']
        rounds = player['record']['w'] + player['record']['l'] + player['record']['t']
        if rounds > swiss:
            (team.wins, team.losses, team.ties) = remove_cut_reportworm(player['record']['w'], player['record']['l'], player['record']['t'], player['rounds'][0]['res'], swiss)
        else:
            team.wins = player['record']['w']
            team.losses = player['record']['l']
            team.ties = player['record']['t']
        team.place = player['place']
        if ((new_tour.day2 is not None and team.place > new_tour.day2) or
            (new_tour.cut is not None and team.place > new_tour.cut) or
            # reportworm orders rounds last first
            (rounds > swiss and player['rounds'][0]['res'] == 'L') or
            (new_tour.cut is not None and rounds == swiss + math.ceil(math.log2(new_tour.cut)))):
                team.top = 2 ** math.ceil(math.log2(team.place))

        session.add(team)
        print(team.name, team.wins, team.losses, '=', player['record']['w'],  player['record']['l'], team.place, team.top)

        # decklist -> team
        for pokemon_set in player['team']:
            valid = pokemon_validator(pokemon_set)
            new_mon = TeamPokemon()
            new_mon.team = team
            new_mon.species = valid['species']
            new_mon.ability = valid['ability']
            new_mon.item = valid['item']
            session.add(new_mon)
            print(new_mon.species, new_mon.item, new_mon.ability, end='')

            for move in valid['moves']:
                move_entry = PokemonMoves()
                move_entry.pokemon = new_mon
                move_entry.move = move
                session.add(move_entry)
                print('', move_entry.move, end='')

            if tour_format.terastal:
                teratype = PokemonTeratypes()
                teratype.teratype = valid['teraType']
                teratype.pokemon = new_mon
                session.add(teratype)
                print('', teratype.teratype, end='')

            if tour_format.open_natures:
                nature = PokemonNatures()
                nature.nature = valid['nature']
                nature.pokemon = new_mon
                session.add(nature)
                print('', nature.nature, end='')

            print()

    confirm = input('Everything good? ')
    if confirm.lower().startswith('y'):
        session.commit()
        print('Done!')
    else:
        print('Discarded!')

