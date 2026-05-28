#!/usr/bin/env python
from flask import Flask, render_template

from sqlalchemy import select
from sqlalchemy.orm import joinedload, Session

from models import get_engine, Team, TeamPokemon

app = Flask(__name__)

engine = get_engine()


@app.errorhandler(404)
def error_404(err):
    return {'error': 'File not found.'}, 404


@app.route('/')
def paste_index():
    return render_template('index.html')


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

