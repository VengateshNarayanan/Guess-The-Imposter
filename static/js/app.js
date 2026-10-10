const socket = io();

// State
let myName = '';
let currentRoomCode = '';
let isHost = false;
let myWord = '';
let selectedVoteTarget = null;
let currentRound = 1;

// Elements
const screens = {
    home: document.getElementById('home-screen'),
    lobby: document.getElementById('lobby-screen'),
    hostWord: document.getElementById('host-word-screen'),
    waiting: document.getElementById('waiting-screen'),
    reveal: document.getElementById('word-reveal-screen'),
    voting: document.getElementById('voting-screen'),
    results: document.getElementById('results-screen')
};

// UI Helpers
function showScreen(screenId) {
    Object.values(screens).forEach(s => s.classList.remove('active'));
    screens[screenId].classList.add('active');
}

function showToast(message) {
    const container = document.getElementById('toast-container');
    const toast = document.createElement('div');
    toast.className = 'toast';
    toast.textContent = message;
    container.appendChild(toast);
    setTimeout(() => {
        toast.style.opacity = '0';
        setTimeout(() => toast.remove(), 300);
    }, 3000);
}

// Socket Events
socket.on('connect', () => {
    // Check if we can reconnect
    socket.emit('reconnect_state');
});

socket.on('reconnect_state', (data) => {
    if (data.success) {
        currentRoomCode = data.room_code;
        isHost = data.is_host;
        
        if (data.state === 'waiting' || data.state === 'host_selected') {
            showScreen('lobby');
        } else if (data.state === 'playing') {
            myWord = data.word;
            document.getElementById('my-secret-word').textContent = myWord;
            showScreen('reveal');
            document.getElementById('host-discussion-controls').classList.toggle('hidden', !isHost);
        } else if (data.state === 'voting') {
            if (data.has_voted) {
                document.getElementById('voting-status').textContent = 'Your vote is recorded.';
                document.getElementById('btn-submit-vote').classList.add('hidden');
            }
            showScreen('voting');
            document.getElementById('host-voting-controls').classList.toggle('hidden', !isHost);
        }
    }
});

socket.on('lobby_update', (data) => {
    document.getElementById('display-room-code').textContent = currentRoomCode;
    document.getElementById('player-count').textContent = data.count;
    
    const list = document.getElementById('player-list');
    list.innerHTML = '';
    
    let connectedCount = 0;
    let amIHostInLobby = false;

    data.players.forEach(p => {
        if (p.connected) connectedCount++;
        if (p.name === myName && p.is_host) amIHostInLobby = true;
        
        const li = document.createElement('li');
        
        const nameSpan = document.createElement('span');
        nameSpan.className = 'player-name';
        nameSpan.textContent = p.name;
        if (p.is_host) {
            const hostBadge = document.createElement('span');
            hostBadge.className = 'host-badge';
            hostBadge.textContent = 'HOST';
            nameSpan.appendChild(hostBadge);
        }
        
        const statusSpan = document.createElement('span');
        statusSpan.className = 'player-status';
        statusSpan.innerHTML = `<span class="status-dot ${p.connected ? '' : 'offline'}"></span> ${p.connected ? 'Online' : 'Offline'}`;
        
        li.appendChild(nameSpan);
        li.appendChild(statusSpan);
        list.appendChild(li);
    });

    // Update Host Select Button
    const btnHost = document.getElementById('btn-select-host');
    const statusMsg = document.getElementById('lobby-status-msg');
    
    if (data.state === 'waiting') {
        if (connectedCount >= 3) {
            btnHost.disabled = false;
            statusMsg.textContent = 'Ready to select host.';
        } else {
            btnHost.disabled = true;
            statusMsg.textContent = `Waiting for at least 3 players (${connectedCount}/3)...`;
        }
    } else if (data.state === 'host_selected') {
        btnHost.disabled = true;
        statusMsg.textContent = 'Host selected. Waiting for words...';
    }
});

socket.on('host_assigned', (data) => {
    showToast(`${data.host_name} was randomly selected as the host!`);
    if (!isHost) { // if I am not the host, go to waiting
        showScreen('waiting');
        document.getElementById('waiting-message').textContent = 'Waiting for host to enter words...';
    }
});

socket.on('you_are_host', () => {
    isHost = true;
    showScreen('hostWord');
});

socket.on('host_cancelled', (data) => {
    showToast(data.reason);
    isHost = false;
    showScreen('lobby');
});

socket.on('round_started', (data) => {
    currentRound = data.round;
    document.getElementById('display-round-num').textContent = currentRound;
    
    document.getElementById('hidden-word-view').classList.remove('hidden');
    document.getElementById('revealed-word-view').classList.add('hidden');
    
    document.getElementById('host-discussion-controls').classList.toggle('hidden', !isHost);
    
    showScreen('reveal');
});

socket.on('receive_word', (data) => {
    myWord = data.word;
    document.getElementById('my-secret-word').textContent = myWord;
});

socket.on('voting_started', (data) => {
    selectedVoteTarget = null;
    document.getElementById('btn-submit-vote').disabled = true;
    document.getElementById('btn-submit-vote').classList.remove('hidden');
    document.getElementById('voting-status').textContent = '';
    
    const list = document.getElementById('voting-player-list');
    list.innerHTML = '';
    
    data.players.forEach(pname => {
        if (pname === myName) return; // Can't vote self
        
        const li = document.createElement('li');
        li.textContent = pname;
        li.dataset.name = pname;
        
        li.addEventListener('click', () => {
            if (document.getElementById('voting-status').textContent.includes('recorded')) return;
            
            Array.from(list.children).forEach(c => c.classList.remove('selected'));
            li.classList.add('selected');
            selectedVoteTarget = pname;
            document.getElementById('btn-submit-vote').disabled = false;
        });
        
        list.appendChild(li);
    });
    
    document.getElementById('host-voting-controls').classList.toggle('hidden', !isHost);
    showScreen('voting');
});

socket.on('vote_recorded_global', (data) => {
    if (isHost) {
        document.getElementById('voting-status').textContent = `${data.count}/${data.total} votes cast.`;
    }
});

socket.on('voting_results', (data) => {
    document.getElementById('result-imposter-name').textContent = data.imposter_name;
    document.getElementById('result-common-word').textContent = data.common_word;
    document.getElementById('result-different-word').textContent = data.different_word;
    
    const list = document.getElementById('results-vote-list');
    list.innerHTML = '';
    data.results.forEach(res => {
        const li = document.createElement('li');
        li.innerHTML = `<span>${res.name}</span> <strong>${res.votes} votes</strong>`;
        list.appendChild(li);
    });
    
    document.getElementById('host-results-controls').classList.toggle('hidden', !isHost);
    showScreen('results');
});

socket.on('new_round_started', () => {
    isHost = false;
    myWord = '';
    document.getElementById('common-word').value = '';
    document.getElementById('different-word').value = '';
    showScreen('lobby');
});

// Event Listeners
document.getElementById('btn-create-room').addEventListener('click', () => {
    myName = document.getElementById('player-name').value.trim();
    if (!myName) {
        showToast('Please enter a display name');
        return;
    }
    socket.emit('create_room', { name: myName }, (res) => {
        if (res.success) {
            currentRoomCode = res.room_code;
            showScreen('lobby');
        } else {
            showToast(res.error);
        }
    });
});

document.getElementById('btn-join-room').addEventListener('click', () => {
    myName = document.getElementById('player-name').value.trim();
    const code = document.getElementById('room-code-input').value.trim().toUpperCase();
    if (!myName || !code) {
        showToast('Please enter name and room code');
        return;
    }
    socket.emit('join_room', { name: myName, room_code: code }, (res) => {
        if (res.success) {
            currentRoomCode = res.room_code;
            isHost = res.is_host;
            if (res.state === 'waiting' || res.state === 'host_selected') {
                showScreen('lobby');
            } else {
                showScreen('waiting');
                document.getElementById('waiting-message').textContent = 'Game in progress...';
            }
        } else {
            showToast(res.error);
        }
    });
});

document.getElementById('btn-copy-code').addEventListener('click', () => {
    navigator.clipboard.writeText(currentRoomCode).then(() => {
        showToast('Room code copied!');
    });
});

document.getElementById('btn-share-code').addEventListener('click', () => {
    const url = window.location.origin;
    const text = `Join my IMPOSTER game! Room code: ${currentRoomCode}`;
    if (navigator.share) {
        navigator.share({ title: 'IMPOSTER', text: text, url: url }).catch(console.error);
    } else {
        navigator.clipboard.writeText(`${text} ${url}`).then(() => {
            showToast('Share link copied!');
        });
    }
});

document.getElementById('btn-select-host').addEventListener('click', () => {
    socket.emit('select_host');
});

document.getElementById('btn-submit-words').addEventListener('click', () => {
    const common = document.getElementById('common-word').value.trim();
    const diff = document.getElementById('different-word').value.trim();
    
    if (!common || !diff) {
        showToast('Please enter both words');
        return;
    }
    
    socket.emit('submit_words', { common_word: common, different_word: diff }, (res) => {
        if (!res.success) {
            showToast(res.error);
        }
    });
});

document.getElementById('btn-reveal-word').addEventListener('click', () => {
    document.getElementById('hidden-word-view').classList.add('hidden');
    document.getElementById('revealed-word-view').classList.remove('hidden');
});

document.getElementById('btn-hide-word').addEventListener('click', () => {
    document.getElementById('hidden-word-view').classList.remove('hidden');
    document.getElementById('revealed-word-view').classList.add('hidden');
});

document.getElementById('btn-proceed-voting').addEventListener('click', () => {
    socket.emit('proceed_to_voting');
});

document.getElementById('btn-submit-vote').addEventListener('click', () => {
    if (!selectedVoteTarget) return;
    
    socket.emit('submit_vote', { target_name: selectedVoteTarget }, (res) => {
        if (res.success) {
            document.getElementById('voting-status').textContent = 'Your vote has been recorded.';
            document.getElementById('btn-submit-vote').classList.add('hidden');
        } else {
            showToast(res.error || 'Failed to submit vote');
        }
    });
});

document.getElementById('btn-finish-voting').addEventListener('click', () => {
    socket.emit('finish_voting');
});

document.getElementById('btn-play-again').addEventListener('click', () => {
    socket.emit('play_again');
});
