import uuid
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.practice import PracticeResult, PracticeSession
from app.models.word import Word
from app.models.word_stats import WordStats
from app.services import llm


async def evaluate_session_writing(
    db: AsyncSession,
    session_id: uuid.UUID,
    user_id: uuid.UUID,
    user_writing: str,
) -> dict:
    """Evaluate a user's writing for a practice session.

    1. Fetches the session and associated words.
    2. Calls the LLM to evaluate.
    3. Updates practice results and word stats (Leitner box).
    4. Returns the evaluation response.
    """
    # Fetch the session
    result = await db.execute(
        select(PracticeSession).where(
            PracticeSession.id == session_id,
            PracticeSession.user_id == user_id,
        )
    )
    session = result.scalar_one_or_none()
    if session is None:
        raise ValueError("Practice session not found")

    if session.completed_at is not None:
        raise ValueError("Practice session already completed")

    # Fetch the practice results to get the word IDs
    results_query = await db.execute(
        select(PracticeResult).where(PracticeResult.session_id == session_id)
    )
    practice_results = list(results_query.scalars().all())

    # Fetch the actual word objects
    word_ids = [pr.word_id for pr in practice_results]
    words_query = await db.execute(
        select(Word).where(Word.id.in_(word_ids))
    )
    words = {w.id: w for w in words_query.scalars().all()}

    # Build word data for the LLM
    word_data = [
        {"id": str(w.id), "word": w.word, "definition": w.definition}
        for w in words.values()
    ]

    # Call LLM for evaluation
    evaluation = await llm.evaluate_writing(
        user_writing=user_writing,
        words=word_data,
        language=session.language,
    )

    # Update session
    session.user_writing = user_writing
    session.feedback = evaluation.get("overall_feedback", "")
    session.completed_at = datetime.now(timezone.utc)

    # Update practice results and word stats based on evaluation
    word_name_to_eval = {
        we["word"]: we for we in evaluation.get("word_evaluations", [])
    }

    # Batch-fetch all WordStats for the relevant words (avoid N+1 queries)
    stats_result = await db.execute(
        select(WordStats).where(WordStats.word_id.in_(word_ids))
    )
    stats_by_word_id = {s.word_id: s for s in stats_result.scalars().all()}

    for pr in practice_results:
        word = words.get(pr.word_id)
        if word is None:
            continue

        word_eval = word_name_to_eval.get(word.word, {})
        is_correct = word_eval.get("is_correct", False)
        feedback = word_eval.get("feedback", "")

        pr.is_correct = is_correct
        pr.feedback = feedback

        # Update word stats (Leitner box progression)
        _update_word_stats(db, pr.word_id, is_correct, stats_by_word_id)

    await db.flush()

    # Build response
    word_evaluations = []
    for pr in practice_results:
        word = words.get(pr.word_id)
        word_evaluations.append({
            "word_id": pr.word_id,
            "word": word.word if word else "",
            "is_correct": pr.is_correct or False,
            "feedback": pr.feedback or "",
        })

    return {
        "session_id": session_id,
        "overall_feedback": evaluation.get("overall_feedback", ""),
        "grammar_notes": evaluation.get("grammar_notes", ""),
        "word_evaluations": word_evaluations,
    }


def _update_word_stats(
    db: AsyncSession,
    word_id: uuid.UUID,
    is_correct: bool,
    stats_by_word_id: dict[uuid.UUID, WordStats],
) -> None:
    """Update word stats based on practice result using the Leitner system.

    Correct: move to next box (max 5).
    Incorrect: back to box 1.

    Uses a pre-fetched dict of WordStats to avoid N+1 queries.
    """
    stats = stats_by_word_id.get(word_id)
    now = datetime.now(timezone.utc)

    if stats is None:
        stats = WordStats(
            word_id=word_id,
            box=2 if is_correct else 1,
            last_practiced=now,
            success_count=1 if is_correct else 0,
            fail_count=0 if is_correct else 1,
        )
        db.add(stats)
        stats_by_word_id[word_id] = stats
    else:
        stats.last_practiced = now
        if is_correct:
            stats.box = min(stats.box + 1, 5)
            stats.success_count += 1
        else:
            stats.box = 1
            stats.fail_count += 1
