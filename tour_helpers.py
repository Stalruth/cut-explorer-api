import json

import requests

from formes import formes


def get_pokedata(tour_id):
    if len(tour_id) < 10:
        url = f'https://pokedata.ovh/standingsVGC/{tour_id}/masters/{tour_id}_Masters.json'
        response = requests.get(url)
        return json.loads(response.text)
    with open(tour_id) as infile:
        return json.load(infile)


def get_active_kicker(players):
    if players >= 2046:
        return 1024
    if players >= 1024:
        return 512
    if players >= 512:
        return 256
    if players >= 256:
        return 128
    if players >= 128:
        return 64
    if players >= 80:
        return 32
    if players >= 48:
        return 16
    return 8


def get_swiss_rounds(players):
    if players > 4096:
        return (9, 6)
    elif players > 2048:
        return (8, 6)
    elif players > 1024:
        return (8, 5)
    elif players > 512:
        return (8, 4)
    elif players > 256:
        return (8, 3)
    elif players > 128:
        return (8, 2)
    elif players > 64:
        return (7, 2)
    elif players > 32:
        return (7, 0)
    elif players > 16:
        return (6, 0)
    elif players > 8:
        return (4, 0)
    return (3, 0)

def get_cutoff(players):
    if players > 64:
        return 8
    elif players > 32:
        return 6
    elif players > 16:
        return 4
    elif players > 8:
        return 2
    return 0


def get_points(wins, losses, ties):
    return (wins * 3) + ties


def is_day2(player, points):
    return get_points(
            player['record']['wins'],
            player['record']['losses'],
            player['record']['ties']) >= points and player['placing'] != 9999


def remove_cut(player, swiss):
    record = player['record']
    total_rounds = record['wins'] + record['losses'] + record['ties']
    played_cut_rounds = total_rounds - swiss
    if played_cut_rounds < 0:
        return (record['wins'], record['losses'], record['ties'])
    cut_wins = 0
    cut_losses = 0
    for i in range(swiss + 1, total_rounds + 1):
        if player['rounds'][f'{i}']['result'] == 'W':
            cut_wins += 1
        elif player['rounds'][f'{i}']['result'] == 'L':
            cut_losses += 1
    return (record['wins'] - cut_wins, record['losses'] - cut_losses, record['ties'])


def populate_counts(pokedata):
    kicker = get_active_kicker(len(pokedata))
    day2 = None
    cut = None

    swiss_day1, swiss_day2 = get_swiss_rounds(len(pokedata))
    swiss = swiss_day1 + swiss_day2
    total_rounds = sum_played_rounds(pokedata[0])
    if swiss_day2 > 0 and total_rounds >= swiss_day1:
        day2_threshold = get_points(swiss_day1 - 3, 2, 1)
        day2 = len([p for p in pokedata if is_day2(p, day2_threshold)])

    if total_rounds >= swiss_day1 + swiss_day2:
        cutoff_i = get_cutoff(len(pokedata)) - 1
        cutoff_points = get_points(*remove_cut(pokedata[cutoff_i], swiss))
        if cutoff_i > 0:
            cut = min(16, len([p for p in pokedata if get_points(*remove_cut(p, swiss)) >= cutoff_points]))

    return (kicker, day2, cut)


def remove_country(name):
    return name.split('[')[0].strip()


def sum_played_rounds(player):
    rec = player['record']
    return rec['wins'] + rec['losses'] + rec['ties']


def remove_country(name):
    return name.split('[')[0].strip()

def pokemon_validator(pokemon_in):
    pokemon = {
            'species': formes.get(pokemon_in['name'], pokemon_in['name']),
            'item': pokemon_in['item'],
            'teraType': pokemon_in['teratype'],
            'ability': pokemon_in['ability'],
            'moves': [move for move in pokemon_in['badges']]
    }
    # Pokemon Specific Jank
    # TODO: test

    # Calyrex - Calyrex entered by mistake when Calyrex-Ice or Calyrex-Shadow is intended.
    if pokemon['species'] == 'Calyrex':
        ice_only = {
                'Blizzard', 'Icy Wind', 'Hail', 'Avalanche', 'Icicle Spear',
                'Snowscape', 'Superpower', 'Glacial Lance', 'Smart Strike',
                'Ice Beam', 'Outrage', 'Throat Chop', 'Roar', 'Icicle Crash',
                'High Horsepower', 'Megahorn', 'Torment', 'Swords Dance',
                'Close Combat', 'Trailblaze', 'Heavy Slam', 'Mist', 'Iron Defense'
        }
        shadow_only = {
                'Disable', 'Confuse Ray', 'Pain Split', 'Foul Play',
                'Astral Barrage', 'Dark Pulse', 'Nasty Plot', 'Haze', 'Hex',
                'Will-O-Wisp', 'Phantom Force', 'Shadow Ball', 'Psycho Cut',
                'Night Shade'
        }
        ice_moves = set(pokemon['moves']) & ice_only
        shadow_moves = set(pokemon['moves']) & shadow_only
        print(ice_moves, shadow_moves)
        if len(ice_moves) > 0 and len(shadow_moves) == 0:
            print('Calyrex 1 Ice')
            pokemon['species'] = 'Calyrex-Ice'
        if len(ice_moves) == 0 and len(shadow_moves) > 0:
            print('Calyrex 1 Shadow')
            pokemon['species'] = 'Calyrex-Shadow'

    # Calyrex - Chilling/Grim Neigh as Calyrex's Ability (Correct: As One).
    if pokemon['species'] == 'Calyrex-Ice' and pokemon['ability'] == 'Chilling Neigh':
        pokemon['ability'] = 'As One (Glastrier)'

    if pokemon['species'] == 'Calyrex-Shadow' and pokemon['ability'] == 'Grim Neigh':
        pokemon['ability'] = 'As One (Spectrier)'

    # Calyrex - RK9 has "As One", we need to specify "As One (Spectrier)" v "As One (Glastrier)"
    if pokemon['ability'] == 'As One':
        if pokemon['species'] == 'Calyrex-Shadow':
            pokemon['ability'] = 'As One (Spectrier)'
        if pokemon['species'] == 'Calyrex-Ice':
            pokemon['ability'] = 'As One (Glastrier)'

    # Ogerpon - Embody Aspect listed; correct using Species+Tera+Item.
    # Leave for manual cleanup if necessary.
    if pokemon['ability'] == 'Embody Aspect':
        if (pokemon['species'] == 'Ogerpon' and
                pokemon['teraType'] == 'Grass'):
            pokemon['ability'] = 'Defiant'
        if (pokemon['species'] == 'Ogerpon-Wellspring' and
                pokemon['teraType'] == 'Water' and
                pokemon['item'] is not None and
                pokemon['item'] == 'Wellspring Mask'):
            pokemon['ability'] = 'Water Absorb'
        if (pokemon['species'] == 'Ogerpon-Hearthflame' and
                pokemon['teraType'] == 'Fire' and
                pokemon['item'] is not None and
                pokemon['item'] == 'Hearthflame Mask'):
            pokemon['ability'] = 'Mold Breaker'
        if (pokemon['species'] == 'Ogerpon-Cornerstone' and
                pokemon['teraType'] == 'Rock' and
                pokemon['item'] is not None and
                pokemon['item'] == 'Cornerstone Mask'):
            pokemon['ability'] = 'Sturdy'

    # Zacian - Behemoth Blade should always be Iron Head
    if 'Behemoth Blade' in pokemon['moves']:
        pokemon['moves'] = ['Iron Head' if move == 'Behemoth Blade' else move for move in pokemon['moves']]

    # Zamazenta - Behemoth Bash should always be Iron Head
    if 'Behemoth Bash' in pokemon['moves']:
        pokemon['moves'] = ['Iron Head' if move == 'Behemoth Bash' else move for move in pokemon['moves']]

    return pokemon

