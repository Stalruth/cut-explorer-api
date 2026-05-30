#!/usr/bin/env python
import json
import math
import re

from flask import Flask, render_template

from markupsafe import Markup

from sqlalchemy import select
from sqlalchemy.orm import joinedload, Session

from models import get_engine, Team, TeamPokemon

app = Flask(__name__)

engine = get_engine()

with open('icondata.json', 'r') as infile:
    icon_data = json.load(infile)


@app.errorhandler(404)
def error_404(err):
    return {'error': 'File not found.'}, 404


@app.route('/')
def paste_index():
    return render_template('index.html')


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

    print(pokemon.species, species_id, num, left, top)

    return Markup(f'<span title="{pokemon.species}" style="background-position: {left}px {top}px" class="set-icon"></span>')


@app.route('/<paste>')
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

