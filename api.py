#!/usr/bin/env python
from datetime import datetime
import json
import math
import re

from flask import abort, Flask, make_response, render_template, request
from markupsafe import Markup

from sqlalchemy import func, nullslast, select
from sqlalchemy.exc import NoResultFound
from sqlalchemy.orm import joinedload, Session

import megas
from models import get_engine, Format, SeasonFormat, Tournament, Team, TeamPokemon, PokemonTeratypes, PokemonMoves, PokemonNatures

app = Flask(__name__)

engine = get_engine()

with open('icondata.json', 'r') as infile:
    icon_data = json.load(infile)


@app.template_filter('setIcon')
def set_icon(pokemon):
    toID = re.compile('[^a-z0-9]')
    species_id = toID.sub('', pokemon.species.lower())

    if species_id in icon_data['pokemon']:
        icon_info = icon_data['pokemon'][species_id]
    else:
        icon_info = {'n': 0}

    num = icon_info['n']

    if num < 0 or num > 1025:
        num = 0
    if 'i' in icon_info:
        num = icon_info['i']

    top = -math.floor(num / 12) * 30
    left = -(num % 12) * 40

    return Markup(f'<span title="{pokemon.species}" style="background-position: {left}px {top}px" class="set-icon"></span>')


@app.errorhandler(404)
def error_404(err):
    return {'error': 'File not found.'}, 404


@app.route('/')
@app.route('/pastes/')
def paste_index():
    return render_template('index.html')


@app.route('/pastes/<paste>')
def paste_page(paste):
    with Session(engine) as session:
        paste_query = (select(Team)
                       .where(Team.id == paste)
                       .options(joinedload(Team.pokemon)
                                .joinedload(TeamPokemon.moves))
                       .options(joinedload(Team.pokemon)
                                .joinedload(TeamPokemon.teratype))
                       .options(joinedload(Team.pokemon)
                                .joinedload(TeamPokemon.nature))
                       .options(joinedload(Team.tour))
                       )
        result = session.execute(paste_query).unique().one().Team
        return render_template('paste.html', team=result)


@app.route('/pastes/<paste>.json')
def paste(paste):
    resp = make_response()
    resp.headers['Access-Control-Allow-Origin'] = '*'
    with Session(engine) as session:
        paste_query = (select(Team)
                       .where(Team.id == paste)
                       .options(joinedload(Team.pokemon)
                                .joinedload(TeamPokemon.moves))
                       .options(joinedload(Team.pokemon)
                                .joinedload(TeamPokemon.teratype))
                       .options(joinedload(Team.tour)))
        try:
            result = session.execute(paste_query).unique().one().Team
            output = {
                    'name': result.name,
                    'tour': result.tour.name,
                    'swiss': {
                        'wins': result.wins,
                        'losses': result.losses,
                    },
                    'place': result.place,
                    'top': result.top,
                    'team': []
            }
            if result.ties is not None:
                output['swiss']['ties'] = result.ties

            for pokemon in result.pokemon:
                pokemon_out = {
                        'species': pokemon.species,
                        'ability': pokemon.ability,
                        'moves': [m.move for m in pokemon.moves]
                }
                if pokemon.item is not None:
                    pokemon_out['item'] = pokemon.item
                if pokemon.teratype:
                    pokemon_out['teraType'] = pokemon.teratype.teratype
                output['team'].append(pokemon_out)
            return output
        except:
            abort(404)


@app.route('/tournaments/years.json', methods=(['GET']))
def years():
    resp = make_response()
    resp.headers['Access-Control-Allow-Origin'] = '*'
    result = []
    with Session(engine) as session:
        query = select(SeasonFormat.season).group_by('season').order_by('season')
        rows = session.execute(query)
        for row in rows:
            result.append(row.season)
    return result


# TODO: look at this again, we have the relationships set up
@app.route('/tournaments/<int:year>/tournaments.json')
def season(year):
    months = {1: 'Jan', 2: 'Feb', 3: 'Mar', 4: 'Apr', 5: 'May', 6: 'Jun',
              7: 'Jul', 8: 'Aug', 9: 'Sep', 10: 'Oct', 11: 'Nov', 12: 'Dec'}
    resp = make_response()
    resp.headers['Access-Control-Allow-Origin'] = '*'
    result = {
            'season': f'{year}',
            'formats': []
    }
    with Session(engine) as session:
        formats_query = select(SeasonFormat, Format).join(SeasonFormat.format).where(SeasonFormat.season == year).order_by(SeasonFormat.start_date)
        rows = session.execute(formats_query)
        for row in rows:
            tournaments = []
            for tour in row.SeasonFormat.tournaments:
                tournaments.append({
                    'id': tour.slug,
                    'name': tour.name
                })
            result['formats'].append({
                'name': row.Format.name,
                'start': {
                    'day': row.SeasonFormat.start_date.day,
                    'month': months[row.SeasonFormat.start_date.month],
                    'year': row.SeasonFormat.start_date.year
                },
                'end': {
                    'day': row.SeasonFormat.end_date.day,
                    'month': months[row.SeasonFormat.end_date.month],
                    'year': row.SeasonFormat.end_date.year
                },
                'tournaments': tournaments
            })
    return result


@app.route('/tournaments/current-year.json')
def current_season():
    with Session(engine) as session:
        query = select(func.max(SeasonFormat.season))
        result = session.execute(query).one()[0]
        return season(result)


def convert_set(pokemon, tour_format):
    pokemon_out = {
            'species': pokemon.species,
            'ability': pokemon.ability,
            'moves': [m.move for m in pokemon.moves]
    }

    if pokemon.item is not None:
        pokemon_out['item'] = pokemon.item
    else:
        pokemon_out['item'] = ''

    if tour_format.terastal == True:
        pokemon_out['teraType'] = pokemon.teratype.teratype

    if tour_format.open_natures == True:
        pokemon_out['nature'] = pokemon.nature.nature

    # Zacian
    if pokemon.species == 'Zacian' and pokemon.item == 'Rusted Sword':
        pokemon_out['species'] = 'Zacian-Crowned'
        pokemon_out['moves'] = ['Behemoth Blade' if m.move == 'Iron Head' else m.move for m in pokemon.moves]

    # Zamazenta
    if pokemon.species == 'Zamazenta' and pokemon.item == 'Rusted Shield':
        pokemon_out['species'] = 'Zamazenta-Crowned'
        pokemon_out['moves'] = ['Behemoth Bash' if m.move == 'Iron Head' else m.move for m in pokemon.moves]

    # Terapagos
    if pokemon.species == 'Terapagos':
        pokemon_out['species'] = 'Terapagos-Terastal'
        pokemon_out['abiilty'] = 'Tera Shell'

    # Megas
    if tour_format.mega_evolution:
        if pokemon.item in megas.stones:
            mega = megas.stones[pokemon.item]
            if mega['species'] == pokemon.species:
                pokemon_out['species'] = mega['mega']
        # TODO: test when mray becomes legal
        #else:
        #    for move_row in pokemon.moves:
        #        move = move_row.move
        #        if move in megas.moves and pokemon.species == megas.moves[move]['species']:
        #            pokemon_out['species'] = mega['mega']

    return pokemon_out


@app.route('/tournaments/<int:year>/<slug>.json')
def tournament(year, slug):
    resp = make_response()
    resp.headers['Access-Control-Allow-Origin'] = '*'
    result = {
            'teams': []
    }
    with Session(engine) as session:
        tour_query = (select(Tournament)
                      .where(Tournament.season == year)
                      .where(Tournament.slug == slug)
                      .options(joinedload(Tournament.season_format)
                               .joinedload(SeasonFormat.format))
                      )
        tour = session.execute(tour_query).one().Tournament
        if request.if_modified_since is not None and request.if_modified_since < tour.last_modified:
            return '', 304

        resp.last_modified = tour.last_modified
        result['name'] = tour.name if tour.name.startswith(f'{tour.season}') else f'{tour.season} {tour.name}'

        # format
        tour_format = tour.season_format.format
        result['fields'] = ['species', 'ability', 'item', 'moves']

        if tour_format.terastal:
            result['fields'].append('teraType')

        if tour_format.open_natures:
            result['fields'].append('nature')

        # stages
        stages = []
        if tour.cut is not None:
            stages.append({
                'count': tour.cut
            })
        if tour.day2 is not None:
            stages.append({
                'name': 'Day 2',
                'count': tour.day2
            })
        if tour.kicker != tour.day2 and tour.kicker != tour.cut:
            stage = {
                'count': tour.kicker
            }
            if tour.day2 is None or tour.kicker < tour.day2:
                stage['name'] = 'All Points',
            stages.append(stage)

        result['stages'] = sorted(stages, key=lambda stage: stage['count'])[::-1]
        result['stages'][0].pop('count', None)

        teams_query = (select(Team)
                       .where(Team.tour_id == tour.id)
                       .options(joinedload(Team.pokemon)
                                .joinedload(TeamPokemon.moves))
                       .order_by(Team.place)
                       )

        if tour_format.terastal:
            teams_query = (teams_query
                           .options(joinedload(Team.pokemon)
                                    .joinedload(TeamPokemon.teratype))
                           )

        if tour_format.open_natures:
            teams_query = (teams_query
                           .options(joinedload(Team.pokemon)
                                    .joinedload(TeamPokemon.nature))
                           )

        rows = session.execute(teams_query).unique()
        for row in rows:
            row_result = {
                    'name': row.Team.name,
                    'id': row.Team.id,
                    'swiss': {
                        'wins': row.Team.wins,
                        'losses': row.Team.losses,
                        'place': row.Team.place
                    },
            }
            if row.Team.top:
                row_result['top'] = row.Team.top
            if row.Team.ties:
                row_result['swiss']['ties'] = row.Team.ties
            row_result['team'] = [convert_set(pokemon, tour_format) for pokemon in row.Team.pokemon]

            result['teams'].append(row_result)
    return result

