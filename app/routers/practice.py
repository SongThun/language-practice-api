import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.dependencies import get_current_user
from app.models.practice import PracticeResult, PracticeSession
from app.models.word import Word
from app.schemas.practice import (
    EvaluationRequest,
    EvaluationResponse,
    ExampleGenerationRequest,
    PracticeSessionCreate,
    PracticeSessionResponse,
    SelectedWord,
    WordSelectionRequest,
)
from app.services import llm
from app.services.evaluation import evaluate_session_writing
from app.services.word_selection import select_words_for_practice

router = APIRouter()


@router.post("/select-words", response_model=list[SelectedWord])
async def select_words(
    body: WordSelectionRequest,
    user_id: uuid.UUID = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[dict]:
    """Select words for practice using the Leitner algorithm."""
    words = await select_words_for_practice(
        db=db,
        user_id=user_id,
        language=body.language,
        count=body.count,
        tag_ids=body.tag_ids if body.tag_ids else None,
    )

    if not words:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No words found for the given criteria",
        )

    return [
        {
            "id": w.id,
            "word": w.word,
            "definition": w.definition,
            "language": w.language,
            "example_sentence": None,
        }
        for w in words
    ]


@router.post("/generate-examples", response_model=list[SelectedWord])
async def generate_examples(
    body: ExampleGenerationRequest,
    user_id: uuid.UUID = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[dict]:
    """Generate example sentences for selected words using the LLM."""
    result = await db.execute(
        select(Word).where(Word.id.in_(body.word_ids), Word.user_id == user_id)
    )
    words = list(result.scalars().all())

    if not words:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No words found",
        )

    word_data = [
        {"id": str(w.id), "word": w.word, "definition": w.definition}
        for w in words
    ]

    language = words[0].language
    examples = await llm.generate_example_sentences(word_data, language)

    return [
        {
            "id": w.id,
            "word": w.word,
            "definition": w.definition,
            "language": w.language,
            "example_sentence": examples.get(str(w.id)),
        }
        for w in words
    ]


@router.post("/sessions", response_model=PracticeSessionResponse, status_code=status.HTTP_201_CREATED)
async def create_session(
    body: PracticeSessionCreate,
    user_id: uuid.UUID = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> PracticeSession:
    """Create a new practice session with selected words."""
    # Verify all words belong to the user
    result = await db.execute(
        select(Word).where(Word.id.in_(body.word_ids), Word.user_id == user_id)
    )
    words = list(result.scalars().all())

    if len(words) != len(body.word_ids):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="One or more word IDs are invalid",
        )

    session = PracticeSession(
        user_id=user_id,
        language=body.language,
        word_count=len(words),
    )
    db.add(session)
    await db.flush()

    # Create practice results for each word
    for word in words:
        practice_result = PracticeResult(
            session_id=session.id,
            word_id=word.id,
        )
        db.add(practice_result)

    await db.flush()
    await db.refresh(session)
    return session


@router.get("/sessions/{session_id}", response_model=PracticeSessionResponse)
async def get_session(
    session_id: uuid.UUID,
    user_id: uuid.UUID = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> PracticeSession:
    """Get a practice session by ID."""
    result = await db.execute(
        select(PracticeSession).where(
            PracticeSession.id == session_id,
            PracticeSession.user_id == user_id,
        )
    )
    session = result.scalar_one_or_none()
    if session is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Practice session not found",
        )
    return session


@router.post("/sessions/{session_id}/evaluate", response_model=EvaluationResponse)
async def evaluate_writing(
    session_id: uuid.UUID,
    body: EvaluationRequest,
    user_id: uuid.UUID = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Submit writing and get AI evaluation for a practice session."""
    try:
        result = await evaluate_session_writing(
            db=db,
            session_id=session_id,
            user_id=user_id,
            user_writing=body.user_writing,
        )
        return result
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        ) from e
