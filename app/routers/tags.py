import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.dependencies import get_current_user
from app.models.tag import Tag
from app.schemas.tag import TagCreate, TagResponse, TagUpdate

router = APIRouter()


async def _get_owned_tag(
    db: AsyncSession, tag_id: uuid.UUID, user_id: uuid.UUID
) -> Tag:
    """Fetch a tag by ID that belongs to the given user, or raise 404."""
    result = await db.execute(
        select(Tag).where(Tag.id == tag_id, Tag.user_id == user_id)
    )
    tag = result.scalar_one_or_none()
    if tag is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tag not found")
    return tag


async def _check_duplicate_tag_name(
    db: AsyncSession, user_id: uuid.UUID, name: str
) -> None:
    """Raise 409 if a tag with the given name already exists for the user."""
    existing = await db.execute(
        select(Tag).where(Tag.user_id == user_id, Tag.name == name)
    )
    if existing.scalar_one_or_none() is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Tag with this name already exists",
        )


@router.post("", response_model=TagResponse, status_code=status.HTTP_201_CREATED)
async def create_tag(
    body: TagCreate,
    user_id: uuid.UUID = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Tag:
    await _check_duplicate_tag_name(db, user_id, body.name)

    tag = Tag(user_id=user_id, name=body.name)
    db.add(tag)
    await db.flush()
    await db.refresh(tag)
    return tag


@router.get("", response_model=list[TagResponse])
async def list_tags(
    user_id: uuid.UUID = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[Tag]:
    result = await db.execute(
        select(Tag).where(Tag.user_id == user_id).order_by(Tag.name)
    )
    return list(result.scalars().all())


@router.get("/{tag_id}", response_model=TagResponse)
async def get_tag(
    tag_id: uuid.UUID,
    user_id: uuid.UUID = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Tag:
    return await _get_owned_tag(db, tag_id, user_id)


@router.patch("/{tag_id}", response_model=TagResponse)
async def update_tag(
    tag_id: uuid.UUID,
    body: TagUpdate,
    user_id: uuid.UUID = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Tag:
    tag = await _get_owned_tag(db, tag_id, user_id)

    if body.name != tag.name:
        await _check_duplicate_tag_name(db, user_id, body.name)

    tag.name = body.name
    await db.flush()
    await db.refresh(tag)
    return tag


@router.delete("/{tag_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_tag(
    tag_id: uuid.UUID,
    user_id: uuid.UUID = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    tag = await _get_owned_tag(db, tag_id, user_id)
    await db.delete(tag)
