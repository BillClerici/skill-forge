"""
GraphQL API Gateway - Unified endpoint for SkillForge RPG
Aggregates data from microservices using Strawberry GraphQL
"""
import os
import uuid
from contextlib import asynccontextmanager
from typing import List, Optional
from datetime import datetime

import httpx
import strawberry
from fastapi import FastAPI
from strawberry.fastapi import GraphQLRouter
from strawberry.types import Info


# ============================================
# GraphQL Types
# ============================================

@strawberry.type
class Account:
    account_id: strawberry.ID
    account_type: str
    subscription_tier: Optional[str]
    subscription_status: str
    max_members: int
    current_member_count: int
    created_at: datetime
    updated_at: datetime


@strawberry.input
class CreateAccountInput:
    account_type: str
    subscription_tier: Optional[str] = None
    max_members: int = 1


@strawberry.input
class UpdateAccountInput:
    subscription_tier: Optional[str] = None
    subscription_status: Optional[str] = None


# ============================================
# Service Clients
# ============================================

ACCOUNT_SERVICE_URL = os.getenv("ACCOUNT_SERVICE_URL", "http://account-service:8000")


async def get_http_client() -> httpx.AsyncClient:
    """Get HTTP client for service communication"""
    return httpx.AsyncClient(timeout=10.0)


# ============================================
# GraphQL Resolvers
# ============================================

@strawberry.type
class Query:
    @strawberry.field
    async def hello(self) -> str:
        """Test query"""
        return "Hello from SkillForge GraphQL API!"

    @strawberry.field
    async def account(self, account_id: strawberry.ID) -> Optional[Account]:
        """Get account by ID"""
        async with httpx.AsyncClient() as client:
            try:
                response = await client.get(f"{ACCOUNT_SERVICE_URL}/accounts/{account_id}")
                if response.status_code == 200:
                    data = response.json()
                    return Account(
                        account_id=data["account_id"],
                        account_type=data["account_type"],
                        subscription_tier=data.get("subscription_tier"),
                        subscription_status=data["subscription_status"],
                        max_members=data["max_members"],
                        current_member_count=data["current_member_count"],
                        created_at=datetime.fromisoformat(data["created_at"]),
                        updated_at=datetime.fromisoformat(data["updated_at"])
                    )
                return None
            except Exception as e:
                print(f"Error fetching account: {e}")
                return None

    @strawberry.field
    async def accounts(self, skip: int = 0, limit: int = 100) -> List[Account]:
        """List all accounts"""
        async with httpx.AsyncClient() as client:
            try:
                response = await client.get(
                    f"{ACCOUNT_SERVICE_URL}/accounts",
                    params={"skip": skip, "limit": limit}
                )
                if response.status_code == 200:
                    data = response.json()
                    return [
                        Account(
                            account_id=item["account_id"],
                            account_type=item["account_type"],
                            subscription_tier=item.get("subscription_tier"),
                            subscription_status=item["subscription_status"],
                            max_members=item["max_members"],
                            current_member_count=item["current_member_count"],
                            created_at=datetime.fromisoformat(item["created_at"]),
                            updated_at=datetime.fromisoformat(item["updated_at"])
                        )
                        for item in data
                    ]
                return []
            except Exception as e:
                print(f"Error fetching accounts: {e}")
                return []


@strawberry.type
class Mutation:
    @strawberry.mutation
    async def create_account(self, input: CreateAccountInput) -> Account:
        """Create a new account"""
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{ACCOUNT_SERVICE_URL}/accounts",
                json={
                    "account_type": input.account_type,
                    "subscription_tier": input.subscription_tier,
                    "max_members": input.max_members
                }
            )
            response.raise_for_status()
            data = response.json()
            return Account(
                account_id=data["account_id"],
                account_type=data["account_type"],
                subscription_tier=data.get("subscription_tier"),
                subscription_status=data["subscription_status"],
                max_members=data["max_members"],
                current_member_count=data["current_member_count"],
                created_at=datetime.fromisoformat(data["created_at"]),
                updated_at=datetime.fromisoformat(data["updated_at"])
            )

    @strawberry.mutation
    async def update_account(
        self,
        account_id: strawberry.ID,
        input: UpdateAccountInput
    ) -> Optional[Account]:
        """Update an existing account"""
        async with httpx.AsyncClient() as client:
            update_data = {}
            if input.subscription_tier is not None:
                update_data["subscription_tier"] = input.subscription_tier
            if input.subscription_status is not None:
                update_data["subscription_status"] = input.subscription_status

            response = await client.patch(
                f"{ACCOUNT_SERVICE_URL}/accounts/{account_id}",
                json=update_data
            )
            if response.status_code == 200:
                data = response.json()
                return Account(
                    account_id=data["account_id"],
                    account_type=data["account_type"],
                    subscription_tier=data.get("subscription_tier"),
                    subscription_status=data["subscription_status"],
                    max_members=data["max_members"],
                    current_member_count=data["current_member_count"],
                    created_at=datetime.fromisoformat(data["created_at"]),
                    updated_at=datetime.fromisoformat(data["updated_at"])
                )
            return None

    @strawberry.mutation
    async def delete_account(self, account_id: strawberry.ID) -> bool:
        """Delete an account"""
        async with httpx.AsyncClient() as client:
            response = await client.delete(f"{ACCOUNT_SERVICE_URL}/accounts/{account_id}")
            return response.status_code == 204


# ============================================
# GraphQL Schema
# ============================================

schema = strawberry.Schema(query=Query, mutation=Mutation)


# ============================================
# FastAPI Application
# ============================================

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    print("🚀 GraphQL API Gateway starting up...")
    yield
    # Shutdown
    print("🛑 GraphQL API Gateway shutting down...")


app = FastAPI(
    title="SkillForge GraphQL API Gateway",
    description="Unified GraphQL endpoint aggregating all SkillForge services",
    version="1.0.0",
    lifespan=lifespan
)


@app.get("/")
async def root():
    return {
        "service": "GraphQL API Gateway",
        "status": "running",
        "version": "1.0.0",
        "graphql_endpoint": "/graphql"
    }


@app.get("/health")
async def health_check():
    return {"status": "healthy", "service": "api-gateway"}


# GraphQL endpoint
graphql_app = GraphQLRouter(schema)
app.include_router(graphql_app, prefix="/graphql")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
