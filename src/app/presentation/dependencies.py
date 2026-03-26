from fastapi import Depends, HTTPException, Request, WebSocket, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from src.app.application.dtos import CurrentUser
from src.app.application.services import ChatService
from src.app.infra.gateways import AuthGateway

security = HTTPBearer(auto_error=True)


def get_auth_gateway(request: Request) -> AuthGateway:
    return request.app.state.auth_gateway


def get_chat_service(request: Request) -> ChatService:
    return request.app.state.chat_service


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    auth_gateway: AuthGateway = Depends(get_auth_gateway),
) -> CurrentUser:
    return await auth_gateway.fetch_current_user(credentials.credentials)


async def get_current_websocket_user(
    websocket: WebSocket,
) -> CurrentUser:
    auth_gateway = websocket.app.state.auth_gateway
    token = websocket.query_params.get("token", "")
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token is required",
        )
    return await auth_gateway.fetch_current_user(token)
