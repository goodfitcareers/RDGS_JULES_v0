import uuid
import logging
from typing import List, Annotated, Optional # Added Optional for x_notion_api_token

from fastapi import APIRouter, Depends, HTTPException, Header, Body
from sqlmodel import Session

from backend.dependencies import get_db_session # Corrected import path
from backend.services.notion import NotionService, NotionWebhookPayload, NotionPageInfo, NotionServiceError

logger = logging.getLogger(__name__) # Placed logger definition at the top

router = APIRouter()

@router.post(
    "/webhook/{client_id}",
    response_model=List[NotionPageInfo],
    summary="Handle incoming Notion webhooks",
    tags=["Notion Integration"]
)
async def handle_notion_webhook(
    client_id: uuid.UUID,
    payload: NotionWebhookPayload = Body(...),
    # TODO: Replace X-Notion-API-Token with secure token retrieval via Replit's OAuth forwarding mechanism.
    # This header is a temporary measure for development.
    x_notion_api_token: Annotated[Optional[str], Header(description="User's Notion API Token (Temporary)")] = None, # Made Optional and added default None
    db: Session = Depends(get_db_session)
):
    """
    Receives webhook events from Notion, processes them using the NotionService,
    and triggers the ingestion pipeline for the specified client.
    """
    if not x_notion_api_token:
        # TODO: In a production setup with Replit's OAuth forwarding, this check might change
        # or the token might be guaranteed to be present.
        raise HTTPException(status_code=401, detail="Notion API token not provided in X-Notion-API-Token header.")

    logger.info(f"Received Notion webhook for client_id: {client_id}, payload type: {payload.type}")

    # Ensure client_id is a UUID object if it's coming from path parameters as string
    # FastAPI usually handles this conversion for path parameters defined with UUID type hint.

    notion_service = NotionService(notion_api_token=x_notion_api_token, client_id=client_id)

    try:
        processed_items = await notion_service.process_webhook_event(payload)
        if not processed_items and payload.item_ids: # Items were expected but none processed
             logger.warning(f"Notion webhook for client {client_id} resulted in no items being processed from {len(payload.item_ids)} payload item_ids.")
             # Depending on desired behavior, this might still be a 200 OK if the process itself was successful
             # or a different status if it implies an issue. For now, 200 OK with empty list.

        logger.info(f"Successfully processed Notion webhook for client {client_id}. {len(processed_items)} items prepared for ingestion.")
        return processed_items
    except NotionServiceError as e:
        logger.error(f"Notion service error for client {client_id} during webhook processing: {e}")
        # Map specific service errors to appropriate HTTP status codes if needed
        raise HTTPException(status_code=500, detail=f"Error processing Notion data: {str(e)}")
    except Exception as e:
        logger.error(f"Unexpected error handling Notion webhook for client {client_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="An unexpected error occurred.")
