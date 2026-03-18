import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.db.session import get_db
from app.dependencies import get_current_user
from app.models.tag import Tag
from app.models.word import Word
from app.models.word_stats import WordStats
from app.schemas.word import WordCreate, WordListResponse, WordResponse, WordUpdate

router = APIRouter()


@router.post("", response_model=WordResponse, status_code=status.HTTP_201_CREATED)
async def create_word(
    body: WordCreate,
    user_id: uuid.UUID = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Word:
    word = Word(
        user_id=user_id,
        word=body.word,
        definition=body.definition,
        language=body.language,
        context_sentence=body.context_sentence,
    )

    # Attach tags if provided
    if body.tag_ids:
        result = await db.execute(
            select(Tag).where(Tag.id.in_(body.tag_ids), Tag.user_id == user_id)
        )
        tags = result.scalars().all()
        if len(tags) != len(body.tag_ids):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="One or more tag IDs are invalid",
            )
        word.tags = list(tags)

    # Create default word stats (box 1)
    word.stats = WordStats(word_id=word.id)

    db.add(word)
    await db.flush()
    await db.refresh(word)
    return word


@router.get("", response_model=WordListResponse)
async def list_words(
    language: str | None = Query(None),
    tag_id: uuid.UUID | None = Query(None),
    search: str | None = Query(None),
    offset: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    user_id: uuid.UUID = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    # Build filter conditions once, apply to both queries
    filters = [Word.user_id == user_id]
    needs_tag_join = False

    if language:
        filters.append(Word.language == language)

    if tag_id:
        filters.append(Tag.id == tag_id)
        needs_tag_join = True

    if search:
        filters.append(
            Word.word.ilike(f"%{search}%") | Word.definition.ilike(f"%{search}%")
        )

    query = select(Word).where(*filters)
    count_query = select(func.count()).select_from(Word).where(*filters)

    if needs_tag_join:
        query = query.join(Word.tags)
        count_query = count_query.join(Word.tags)

    # Get total count
    total_result = await db.execute(count_query)
    total = total_result.scalar_one()

    # Get paginated results
    query = query.options(selectinload(Word.tags), selectinload(Word.stats))
    query = query.order_by(Word.created_at.desc()).offset(offset).limit(limit)
    result = await db.execute(query)
    words = result.scalars().all()

    return {"items": words, "total": total}


@router.get("/{word_id}", response_model=WordResponse)
async def get_word(
    word_id: uuid.UUID,
    user_id: uuid.UUID = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Word:
    result = await db.execute(
        select(Word)
        .options(selectinload(Word.tags), selectinload(Word.stats))
        .where(Word.id == word_id, Word.user_id == user_id)
    )
    word = result.scalar_one_or_none()
    if word is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Word not found")
    return word


@router.patch("/{word_id}", response_model=WordResponse)
async def update_word(
    word_id: uuid.UUID,
    body: WordUpdate,
    user_id: uuid.UUID = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Word:
    result = await db.execute(
        select(Word)
        .options(selectinload(Word.tags), selectinload(Word.stats))
        .where(Word.id == word_id, Word.user_id == user_id)
    )
    word = result.scalar_one_or_none()
    if word is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Word not found")

    update_data = body.model_dump(exclude_unset=True)

    # Handle tag updates separately
    tag_ids = update_data.pop("tag_ids", None)
    if tag_ids is not None:
        tag_result = await db.execute(
            select(Tag).where(Tag.id.in_(tag_ids), Tag.user_id == user_id)
        )
        tags = tag_result.scalars().all()
        if len(tags) != len(tag_ids):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="One or more tag IDs are invalid",
            )
        word.tags = list(tags)

    for field, value in update_data.items():
        setattr(word, field, value)

    await db.flush()
    await db.refresh(word)
    return word


@router.delete("/{word_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_word(
    word_id: uuid.UUID,
    user_id: uuid.UUID = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    result = await db.execute(
        select(Word).where(Word.id == word_id, Word.user_id == user_id)
    )
    word = result.scalar_one_or_none()
    if word is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Word not found")
    await db.delete(word)
