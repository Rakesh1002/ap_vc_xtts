from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Depends
from typing import Dict, Set
import json
from app.core.security import get_current_user
from app.models.audio import ProcessingStatus

router = APIRouter()

class ConnectionManager:
    def __init__(self):
        self.active_connections: Dict[int, Set[WebSocket]] = {}

    async def connect(self, websocket: WebSocket, user_id: int):
        await websocket.accept()
        if user_id not in self.active_connections:
            self.active_connections[user_id] = set()
        self.active_connections[user_id].add(websocket)

    def disconnect(self, websocket: WebSocket, user_id: int):
        if user_id in self.active_connections:
            self.active_connections[user_id].remove(websocket)
            if not self.active_connections[user_id]:
                del self.active_connections[user_id]

    async def send_job_update(self, user_id: int, job_id: int, status: str, details: dict = None):
        if user_id in self.active_connections:
            message = {
                "job_id": job_id,
                "status": status,
                "details": details or {}
            }
            for connection in self.active_connections[user_id]:
                await connection.send_text(json.dumps(message))

manager = ConnectionManager()

@router.websocket("/ws/{token}")
async def websocket_endpoint(websocket: WebSocket, token: str):
    try:
        user = await get_current_user(token)
        await manager.connect(websocket, user.id)
        try:
            while True:
                await websocket.receive_text()
        except WebSocketDisconnect:
            manager.disconnect(websocket, user.id)
    except Exception as e:
        await websocket.close(code=1008)  # Policy violation 