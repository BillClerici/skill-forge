# 🎮 SkillForge Game Engine - User Guide

## ✅ What's Complete

### **Backend (All Done!)**
- ✅ **Phase 1**: Core game loop with LangGraph
- ✅ **Phase 2**: Advanced AI agents, persistence (MongoDB, Neo4j)
- ✅ **Phase 3**: Multiplayer, auto-save, quest tracking, dynamic events

### **Frontend (Ready to Use!)**
- ✅ Game Lobby UI
- ✅ Game Session UI with real-time chat
- ✅ Character selection
- ✅ WebSocket client for live gameplay

---

## 🚀 How to Access the UI

### **1. Start All Services**
```bash
docker-compose up -d
```

### **2. Open the Dashboard**
Navigate to: **http://localhost:8000/**

---

## 🎯 Step-by-Step: Play a Game

### **Option A: Quick Start (If you have a campaign)**

1. **Go to Game Lobby**
   http://localhost:8000/game/lobby/

2. **Select a Campaign**
   - Browse available campaigns
   - Click "⚔️ Play Solo" or "👥 Create Party"

3. **Choose Your Character**
   - Select from your characters
   - Click "Start Game"

4. **Play!**
   - Real-time chat with GM
   - Type actions naturally ("I talk to the innkeeper")
   - See your quest objectives and character stats

---

### **Option B: Create a Campaign First**

If you don't have any campaigns yet:

1. **Create a Campaign**
   http://localhost:8000/campaigns/wizard/

2. **Or Use Campaign Designer**
   http://localhost:8000/campaigns/designer/

3. **Create a Character** (if needed)
   - Go to http://localhost:8000/players/
   - Create/select a player
   - Create a character

4. **Then follow Option A**

---

## 🗺️ Complete UI Map

### **Main Pages**

| Page | URL | What It Does |
|------|-----|--------------|
| **Dashboard** | `/` | Overview of everything |
| **Game Lobby** | `/game/lobby/` | Browse & start games |
| **Campaigns** | `/campaigns/` | Manage campaigns |
| **Campaign Wizard** | `/campaigns/wizard/` | Create campaigns |
| **Characters** | `/players/` | Manage characters |
| **Worlds** | `/worlds/` | Browse/create worlds |

### **Game Pages**

| Page | URL | What It Does |
|------|-----|--------------|
| **Game Session** | `/game/session/{session_id}/` | Live gameplay |
| **Party Lobby** | `/game/party/{session_id}/` | Multiplayer waiting room |
| **Join Game** | `/game/join/?token={invite_token}` | Join with invite link |

---

## 🎮 Gameplay Features

### **Chat Interface**
- **GM Narration**: Vivid scene descriptions
- **NPC Dialogue**: In-character conversations
- **Assessment Feedback**: Bloom's Taxonomy evaluations
- **Player Actions**: Your inputs

### **Info Panels**
- **Quest Tab**: Current objectives, progress
- **Character Tab**: Stats, Bloom's level, inventory
- **Party Tab**: Team members, team chat

### **Actions**
- Type naturally: "I examine the door"
- Quick actions: Click suggested actions
- Real-time response from AI Game Master

---

## 🔧 Backend Services

### **Game Engine API**
- **Base URL**: http://localhost:9500
- **Health**: http://localhost:9500/health
- **Docs**: http://localhost:9500/docs (FastAPI auto-docs)

### **Key Endpoints**
```bash
POST /api/v1/session/start-solo
POST /api/v1/session/create-party
POST /api/v1/session/{session_id}/join
GET  /api/v1/session/{session_id}/state
POST /api/v1/session/{session_id}/pause
POST /api/v1/session/{session_id}/resume
```

### **WebSocket**
```
ws://localhost:9500/ws/session/{session_id}/player/{player_id}
```

---

## 🧪 Testing the System

### **1. Check Game Engine Health**
```bash
curl http://localhost:9500/health
```

**Expected Response:**
```json
{
  "status": "healthy",
  "redis": "connected",
  "rabbitmq": "connected",
  "mongodb": "connected",
  "neo4j": "connected"
}
```

### **2. Test Session Creation**
```bash
curl -X POST http://localhost:9500/api/v1/session/start-solo \
  -H "Content-Type: application/json" \
  -d '{
    "campaign_id": "YOUR_CAMPAIGN_ID",
    "player_id": "YOUR_PLAYER_ID",
    "character_id": "YOUR_CHARACTER_ID"
  }'
```

### **3. Check Django**
```bash
curl http://localhost:8000/
```

---

## 🎨 What the UI Looks Like

### **Game Lobby**
- **Grid of Campaigns**: Beautiful cards with images
- **Campaign Info**: Title, description, world, quest count
- **Two Buttons**: "Play Solo" or "Create Party"
- **Character Selector**: Modal popup to choose character

### **Game Session**
- **Left Panel (2/3)**: Chat window with GM & player messages
- **Right Panel (1/3)**: Quest info, character stats, party
- **Header**: Campaign name, current quest
- **Input Box**: Type your actions
- **Connection Status**: Green/red indicator

---

## 📊 What's Tracked

### **In MongoDB**
- Complete game sessions
- Chat history
- Assessments (Bloom's levels, dimensional scores)
- Player progression
- Save points

### **In Neo4j**
- Player-NPC relationships
- Knowledge graphs
- Quest progression
- Location visits

### **In Redis**
- Active session state (real-time)
- Distributed locks (for multiplayer)

---

## 🚧 What's NOT Built Yet

### **UI Components**
- ❌ Save/Load UI (auto-save works, manual save UI needed)
- ❌ Progress Dashboard (visualizations for Bloom's/dimensions)
- ❌ Team Chat UI (channels work, need prettier UI)
- ❌ Character sheet customization UI

### **Features**
- ❌ Speech-to-Text (STT)
- ❌ Text-to-Speech (TTS)
- ❌ Rich media embedding (images, videos in chat)
- ❌ Advanced parental controls

---

## 🐛 Troubleshooting

### **"Game engine not connected"**
1. Check if game-engine is running:
   ```bash
   docker ps | grep game-engine
   ```

2. Start it:
   ```bash
   docker-compose up -d game-engine
   ```

3. Check logs:
   ```bash
   docker logs skillforge-game-engine
   ```

### **"No campaigns available"**
1. Create a campaign:
   - Go to http://localhost:8000/campaigns/wizard/
   - Follow the wizard

2. Or check existing campaigns:
   ```bash
   curl http://localhost:8000/campaigns/
   ```

### **"Character not found"**
1. Create a character:
   - Go to http://localhost:8000/players/
   - Select a player
   - Click "Create Character"

---

## 💡 Pro Tips

### **For Best Experience**
1. **Use Chrome/Firefox**: Best WebSocket support
2. **Keep Session ID**: Bookmark your game session URL
3. **Pause/Resume**: You can pause anytime, auto-save keeps state
4. **Natural Language**: Type like you're talking: "I ask the guard about the castle"

### **For Multiplayer**
1. Host creates party
2. Share invite token with friends
3. They use: http://localhost:8000/game/join/?token=INVITE_TOKEN
4. Host starts when everyone's ready

### **For Development**
- **FastAPI Docs**: http://localhost:9500/docs (auto-generated)
- **GraphQL**: http://localhost:8000/graphql/
- **RabbitMQ Management**: http://localhost:15672 (skillforge / PASSWORD)
- **Neo4j Browser**: http://localhost:7474 (neo4j / PASSWORD)

---

## 📈 Next Steps

### **To Complete the System**

1. **Build & Start Game Engine**:
   ```bash
   docker-compose build game-engine
   docker-compose up -d game-engine
   ```

2. **Create Test Data**:
   - Create a player
   - Create a character
   - Create/generate a campaign

3. **Play!**:
   - Go to game lobby
   - Start a game
   - Experience AI-powered gameplay

### **For Production**
1. Add authentication/authorization
2. Implement save/load UI
3. Build progress dashboard
4. Add STT/TTS
5. Performance testing
6. Security hardening

---

## 🎮 Example Gameplay Flow

1. **Player**: Opens `/game/lobby/`
2. **Player**: Sees "Dragons of Valtoria" campaign
3. **Player**: Clicks "Play Solo"
4. **Player**: Selects "Aria the Elf"
5. **System**: Creates session, connects WebSocket
6. **GM**: "You stand at the entrance of the ancient fortress..."
7. **Player**: Types "I examine the door for traps"
8. **GM**: "Your keen eyes spot strange runes..."
9. **GM**: Assessment: "Excellent observation! +15 XP (Apply level)"
10. **Player**: Continues adventure...

---

## 🆘 Need Help?

- **Logs**: `docker logs skillforge-game-engine`
- **Health Check**: http://localhost:9500/health
- **API Docs**: http://localhost:9500/docs
- **Django Admin**: http://localhost:8000/admin/

---

**Enjoy your SkillForge adventure! 🎲✨**
