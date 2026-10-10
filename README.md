# IMPOSTER - Real-Time Multiplayer Party Game

A real-time multiplayer party game built with Python, Flask, and Socket.IO.

## Game Concept
The game supports 3-20 players. Most players receive one common word, while one randomly selected player receives a different word. The player with the different word must try to figure out what the common word is, while the other players try to figure out who has the different word.

## Local Development Setup (Windows)

1. **Create the virtual environment**:
   ```powershell
   py -m venv venv
   ```

2. **Activate the virtual environment**:
   ```powershell
   .\venv\Scripts\Activate.ps1
   ```

3. **Install dependencies**:
   ```powershell
   py -m pip install -r requirements.txt
   ```

4. **Set environment variables**:
   Create a `.env` file in the root directory and add a `SECRET_KEY`.
   ```powershell
   Copy-Item .env.example .env
   ```

5. **Start the server**:
   ```powershell
   py app.py
   ```

6. **Play locally**:
   Open your browser and navigate to `http://127.0.0.1:5000`

### Testing with Multiple Devices Locally
To play with multiple devices on the same local network:
1. Ensure your firewall allows inbound connections on port 5000.
2. Run the application bound to `0.0.0.0`:
   (The `app.py` script binds to `0.0.0.0` automatically)
3. Find your computer's local IP address using `ipconfig` (e.g., `192.168.1.100`).
4. On your mobile phone (connected to the same Wi-Fi), go to `http://192.168.1.100:5000`.

## Deployment to Render
1. Connect your GitHub repository to Render.
2. The `render.yaml` file in this repository provides the configuration.
3. Render will automatically use `gunicorn` with `eventlet` to run the application.

## Technologies Used
- Backend: Python, Flask, Flask-SocketIO, Eventlet
- Frontend: HTML5, CSS3, Vanilla JavaScript, Socket.IO Client
