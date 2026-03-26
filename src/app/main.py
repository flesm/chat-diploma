from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient

from src.app.application.services import ChatService
from src.app.config import Settings
from src.app.infra.gateways import AuthGateway, MentorGateway
from src.app.infra.realtime import RealtimeConnectionManager
from src.app.infra.repositories import ConversationRepository, MessageRepository
from src.app.presentation.routes import router as http_router
from src.app.presentation.websockets import router as websocket_router

settings = Settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    mongo = AsyncIOMotorClient(settings.mongo_url)
    db = mongo[settings.mongo_db]

    conversations = ConversationRepository(db)
    messages = MessageRepository(db)
    realtime_manager = RealtimeConnectionManager()
    auth_gateway = AuthGateway(settings.auth_api_url)
    mentor_gateway = MentorGateway(settings.core_api_url)
    chat_service = ChatService(
        conversations=conversations,
        messages=messages,
        mentor_gateway=mentor_gateway,
        realtime=realtime_manager,
    )

    await conversations.create_indexes()

    app.state.mongo = mongo
    app.state.db = db
    app.state.auth_gateway = auth_gateway
    app.state.chat_service = chat_service
    app.state.realtime_manager = realtime_manager

    yield

    mongo.close()


app = FastAPI(lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(http_router)
app.include_router(websocket_router)
