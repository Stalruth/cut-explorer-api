#!/usr/bin/env python
from flask import abort, Flask, make_response, render_template, request

from sqlalchemy import func, select
from sqlalchemy.exc import NoResultFound
from sqlalchemy.orm import joinedload, Session

from models import get_engine, Format, SeasonFormat, Tournament, Team, TeamPokemon, PokemonTeratypes, PokemonMoves

app = Flask(__name__)

engine = get_engine()


@app.errorhandler(404)
def error_404(err):
    return {'error': 'File not found.'}, 404


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


def convert_species(pokemon):
    if pokemon.species == 'Zacian' and pokemon.item == 'Rusted Sword':
        return 'Zacian-Crowned'
    if pokemon.species == 'Zamazenta' and pokemon.item == 'Rusted Shield':
        return 'Zamazenta-Crowned'
    if pokemon.species == 'Terapagos':
        return 'Terapagos-Terastal'
    return pokemon.species


def convert_ability(pokemon):
    if pokemon.species == 'Terapagos':
        return 'Tera Shell'
    return pokemon.ability


def convert_move(move, pokemon):
    if pokemon.species == 'Zacian' and pokemon.item == 'Rusted Sword' and move == 'Iron Head':
        return 'Behemoth Blade'
    if pokemon.species == 'Zamazenta' and pokemon.item == 'Rusted Shield' and move == 'Iron Head':
        return 'Behemoth Bash'
    return move


@app.route('/tournaments/<int:year>/<slug>.json')
def tournament(year, slug):
    resp = make_response()
    resp.headers['Access-Control-Allow-Origin'] = '*'
    result = {
            'teams': []
    }
    with Session(engine) as session:
        tour_query = select(Tournament).where(Tournament.season == year).where(Tournament.slug == slug)
        tour = session.execute(tour_query).one().Tournament
        result['name'] = tour.name if tour.name.startswith(f'{tour.season}') else f'{tour.season} {tour.name}'

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

        # teams
        teams_query = select(Team).where(Team.tour_id == tour.id).order_by(Team.place).options(joinedload(Team.pokemon).joinedload(TeamPokemon.moves)).options(joinedload(Team.pokemon).joinedload(TeamPokemon.teratype))
        print(teams_query)
        rows = session.execute(teams_query).unique()
        for row in rows:
            row_result = {
                    'name': row.Team.name,
                    'paste': row.Team.paste,
                    'id': row.Team.id,
                    'swiss': {
                        'wins': row.Team.wins,
                        'losses': row.Team.losses,
                        'place': row.Team.place
                    },
                    'team': []
            }
            if row.Team.top:
                row_result['top'] = row.Team.top
            if row.Team.ties:
                row_result['swiss']['ties'] = row.Team.ties
            for pokemon in row.Team.pokemon:
                mon = {
                    'species': convert_species(pokemon),
                    'ability': convert_ability(pokemon),
                    'moves': [convert_move(move_row.move, pokemon) for move_row in pokemon.moves]
                }
                if pokemon.item is not None:
                    mon['item'] = pokemon.item
                if pokemon.teratype is not None:
                    mon['teraType'] = pokemon.teratype.teratype
                row_result['team'].append(mon)
            result['teams'].append(row_result)
    return result

