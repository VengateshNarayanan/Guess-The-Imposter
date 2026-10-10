import os
import random
import string
import uuid

from flask import Flask, render_template, session, request
from flask_socketio import SocketIO, emit, join_room, leave_room
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'dev_secret_key_if_not_set')
socketio = SocketIO(app, cors_allowed_origins="*", async_mode='threading')

# State storage (In-memory for this version)
# rooms[room_code] = {
#     'code': str,
#     'state': 'waiting' | 'host_selected' | 'playing' | 'voting' | 'results',
#     'players': { player_id: {'name': str, 'connected': bool, 'sid': str} },
#     'host_id': str or None,
#     'different_player_id': str or None,
#     'common_word': str,
#     'different_word': str,
#     'votes': { voter_player_id: target_player_id },
#     'round': int
# }
rooms = {}
player_id_to_room = {}

def generate_room_code():
    while True:
        code = ''.join(random.choices(string.ascii_uppercase, k=6))
        if code not in rooms:
            return code

def get_player_id():
    return session.get('player_id')

def get_room(room_code):
    return rooms.get(room_code)

def broadcast_lobby_update(room_code):
    room = get_room(room_code)
    if not room:
        return
    
    players_data = []
    for pid, p in room['players'].items():
        players_data.append({
            'name': p['name'],
            'connected': p['connected'],
            'is_host': (pid == room['host_id'])
        })
    
    # Sort alphabetically by name
    players_data.sort(key=lambda x: x['name'].lower())
    
    socketio.emit('lobby_update', {
        'players': players_data,
        'count': len(room['players']),
        'state': room['state']
    }, room=room_code)

@app.route('/')
def index():
    if 'player_id' not in session:
        session['player_id'] = str(uuid.uuid4())
    return render_template('index.html')

@socketio.on('connect')
def handle_connect():
    pass

@socketio.on('disconnect')
def handle_disconnect():
    player_id = session.get('player_id')
    if not player_id:
        return
        
    room_code = player_id_to_room.get(player_id)
    if not room_code:
        return
        
    room = get_room(room_code)
    if room and player_id in room['players']:
        room['players'][player_id]['connected'] = False
        room['players'][player_id]['sid'] = None
        
        # If host disconnects before round starts, cancel host selection
        if room['state'] == 'host_selected' and room['host_id'] == player_id:
            room['state'] = 'waiting'
            room['host_id'] = None
            socketio.emit('host_cancelled', {'reason': 'Host disconnected'}, room=room_code)
            
        broadcast_lobby_update(room_code)

@socketio.on('create_room')
def handle_create_room(data):
    player_id = session.get('player_id')
    if not player_id:
        return {'success': False, 'error': 'Session error'}
        
    name = data.get('name', '').strip()
    if not name or len(name) > 20:
        return {'success': False, 'error': 'Invalid name'}
        
    room_code = generate_room_code()
    rooms[room_code] = {
        'code': room_code,
        'state': 'waiting',
        'players': {},
        'host_id': None,
        'different_player_id': None,
        'common_word': '',
        'different_word': '',
        'votes': {},
        'round': 1
    }
    
    rooms[room_code]['players'][player_id] = {
        'name': name,
        'connected': True,
        'sid': request.sid
    }
    player_id_to_room[player_id] = room_code
    
    join_room(room_code)
    broadcast_lobby_update(room_code)
    return {'success': True, 'room_code': room_code}

@socketio.on('join_room')
def handle_join_room(data):
    player_id = session.get('player_id')
    if not player_id:
        return {'success': False, 'error': 'Session error'}
        
    name = data.get('name', '').strip()
    room_code = data.get('room_code', '').strip().upper()
    
    if not name or len(name) > 20:
        return {'success': False, 'error': 'Invalid name'}
        
    room = get_room(room_code)
    if not room:
        return {'success': False, 'error': 'Room not found'}
        
    if len(room['players']) >= 20 and player_id not in room['players']:
        return {'success': False, 'error': 'Room is full'}
        
    # Check for duplicate name
    if player_id not in room['players']:
        for p in room['players'].values():
            if p['name'].lower() == name.lower():
                return {'success': False, 'error': 'Name already taken in this room'}
    
    # Update player info
    if player_id in room['players']:
        room['players'][player_id]['connected'] = True
        room['players'][player_id]['sid'] = request.sid
        room['players'][player_id]['name'] = name
    else:
        room['players'][player_id] = {
            'name': name,
            'connected': True,
            'sid': request.sid
        }
    
    player_id_to_room[player_id] = room_code
    join_room(room_code)
    
    broadcast_lobby_update(room_code)
    
    # Send current state to reconnecting player
    return {
        'success': True,
        'room_code': room_code,
        'state': room['state'],
        'is_host': room['host_id'] == player_id
    }

@socketio.on('reconnect_state')
def handle_reconnect_state():
    player_id = session.get('player_id')
    room_code = player_id_to_room.get(player_id)
    if not room_code:
        return {'success': False}
    room = get_room(room_code)
    if not room or player_id not in room['players']:
        return {'success': False}
        
    # If round is playing, send word
    word = None
    if room['state'] in ['playing', 'voting']:
        if player_id == room['different_player_id']:
            word = room['different_word']
        else:
            word = room['common_word']
            
    return {
        'success': True,
        'room_code': room_code,
        'state': room['state'],
        'is_host': room['host_id'] == player_id,
        'word': word,
        'has_voted': player_id in room['votes']
    }

@socketio.on('select_host')
def handle_select_host():
    player_id = session.get('player_id')
    room_code = player_id_to_room.get(player_id)
    if not room_code:
        return
        
    room = get_room(room_code)
    if not room:
        return
        
    if room['state'] != 'waiting':
        return
        
    connected_players = [pid for pid, p in room['players'].items() if p['connected']]
    if len(connected_players) < 3:
        return
        
    host_id = random.choice(connected_players)
    room['host_id'] = host_id
    room['state'] = 'host_selected'
    
    socketio.emit('host_assigned', {'host_name': room['players'][host_id]['name']}, room=room_code)
    
    # Notify host privately
    host_sid = room['players'][host_id]['sid']
    if host_sid:
        socketio.emit('you_are_host', room=host_sid)
        
    broadcast_lobby_update(room_code)

@socketio.on('submit_words')
def handle_submit_words(data):
    player_id = session.get('player_id')
    room_code = player_id_to_room.get(player_id)
    room = get_room(room_code)
    
    if not room or room['host_id'] != player_id or room['state'] != 'host_selected':
        return {'success': False, 'error': 'Unauthorized'}
        
    common = data.get('common_word', '').strip()
    different = data.get('different_word', '').strip()
    
    if not common or not different:
        return {'success': False, 'error': 'Both words are required'}
        
    if common.lower() == different.lower():
        return {'success': False, 'error': 'Words must be different'}
        
    if len(common) > 30 or len(different) > 30:
        return {'success': False, 'error': 'Words are too long'}
        
    connected_non_hosts = [pid for pid, p in room['players'].items() if p['connected'] and pid != player_id]
    
    if len(connected_non_hosts) < 2:
        return {'success': False, 'error': 'Not enough players'}
        
    # Assign words
    room['common_word'] = common
    room['different_word'] = different
    room['different_player_id'] = random.choice(connected_non_hosts)
    room['state'] = 'playing'
    room['votes'] = {}
    
    # Broadcast game start
    socketio.emit('round_started', {'round': room['round']}, room=room_code)
    
    # Send secret words privately
    for pid, p in room['players'].items():
        if not p['connected'] or not p['sid']:
            continue
        word = room['different_word'] if pid == room['different_player_id'] else room['common_word']
        socketio.emit('receive_word', {'word': word}, room=p['sid'])
        
    return {'success': True}

@socketio.on('proceed_to_voting')
def handle_proceed_voting():
    player_id = session.get('player_id')
    room_code = player_id_to_room.get(player_id)
    room = get_room(room_code)
    
    if not room or room['host_id'] != player_id or room['state'] != 'playing':
        return
        
    room['state'] = 'voting'
    
    # Prepare list of eligible players for voting (names and ids)
    # We shouldn't expose IDs, so we generate a safe mapping or just use names.
    # Actually, using player names as voting targets is fine since names are unique per room.
    players_list = [p['name'] for pid, p in room['players'].items() if p['connected']]
    
    socketio.emit('voting_started', {'players': players_list}, room=room_code)

@socketio.on('submit_vote')
def handle_submit_vote(data):
    player_id = session.get('player_id')
    room_code = player_id_to_room.get(player_id)
    room = get_room(room_code)
    
    if not room or room['state'] != 'voting':
        return {'success': False, 'error': 'Not in voting state'}
        
    target_name = data.get('target_name')
    if not target_name:
        return {'success': False}
        
    my_name = room['players'][player_id]['name']
    if my_name == target_name:
        return {'success': False, 'error': 'Cannot vote for yourself'}
        
    if player_id in room['votes']:
        return {'success': False, 'error': 'Already voted'}
        
    target_id = None
    for pid, p in room['players'].items():
        if p['name'] == target_name:
            target_id = pid
            break
            
    if not target_id:
        return {'success': False, 'error': 'Target not found'}
        
    room['votes'][player_id] = target_id
    
    # Check if all connected eligible players voted
    connected_voters = [pid for pid, p in room['players'].items() if p['connected']]
    
    socketio.emit('vote_recorded_global', {'count': len(room['votes']), 'total': len(connected_voters)}, room=room_code)
    
    return {'success': True}

@socketio.on('finish_voting')
def handle_finish_voting():
    player_id = session.get('player_id')
    room_code = player_id_to_room.get(player_id)
    room = get_room(room_code)
    
    if not room or room['host_id'] != player_id or room['state'] != 'voting':
        return
        
    room['state'] = 'results'
    
    # Calculate votes
    vote_counts = {}
    for target in room['votes'].values():
        vote_counts[target] = vote_counts.get(target, 0) + 1
        
    # Format results
    results = []
    for target_id, count in vote_counts.items():
        results.append({'name': room['players'][target_id]['name'], 'votes': count})
        
    results.sort(key=lambda x: x['votes'], reverse=True)
    
    different_name = room['players'][room['different_player_id']]['name']
    
    socketio.emit('voting_results', {
        'results': results,
        'imposter_name': different_name,
        'common_word': room['common_word'],
        'different_word': room['different_word']
    }, room=room_code)

@socketio.on('play_again')
def handle_play_again():
    player_id = session.get('player_id')
    room_code = player_id_to_room.get(player_id)
    room = get_room(room_code)
    
    if not room or room['host_id'] != player_id or room['state'] != 'results':
        return
        
    room['state'] = 'waiting'
    room['host_id'] = None
    room['different_player_id'] = None
    room['common_word'] = ''
    room['different_word'] = ''
    room['votes'] = {}
    room['round'] += 1
    
    socketio.emit('new_round_started', room=room_code)
    broadcast_lobby_update(room_code)

if __name__ == '__main__':
    socketio.run(app, host='0.0.0.0', port=5000, debug=True)
