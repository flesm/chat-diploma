from typing import Any

import httpx
from fastapi import HTTPException, status

from src.app.application.dtos import CurrentUser


class AuthGateway:
    def __init__(self, auth_api_url: str):
        self._auth_api_url = auth_api_url

    async def fetch_current_user(self, token: str) -> CurrentUser:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(
                f"{self._auth_api_url}/auth/me",
                params={"token": token},
            )

        if response.status_code >= 400:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token",
            )

        payload = response.json()
        return CurrentUser(
            id=str(payload["id"]),
            email=payload["email"],
            first_name=payload["first_name"],
            last_name=payload["last_name"],
            role=payload.get("role"),
            token=token,
        )


class MentorGateway:
    def __init__(self, core_api_url: str):
        self._core_api_url = core_api_url

    async def verify_mentor_intern_links(self, token: str) -> list[dict[str, Any]]:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(
                f"{self._core_api_url}/mentor-intern-links",
                headers={"Authorization": f"Bearer {token}"},
            )

        if response.status_code >= 400:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Cannot load mentor interns",
            )

        data = response.json()
        return data if isinstance(data, list) else []

    async def verify_my_mentor(self, token: str) -> dict[str, Any]:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(
                f"{self._core_api_url}/mentor-intern-links/my-mentor",
                headers={"Authorization": f"Bearer {token}"},
            )

        if response.status_code >= 400:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Cannot load mentor link",
            )

        data = response.json()
        return data if isinstance(data, dict) else {}
