import random
import uuid
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.tag import Tag
from app.models.word import Word


async def select_words_for_practice(
    db: AsyncSession,
    user_id: uuid.UUID,
    language: str,
    count: int = 5,
    tag_ids: list[uuid.UUID] | None = None,
) -> list[Word]:
    """Select words for a practice session using the Modified Leitner system.

    Selection probability is proportional to:
        (1 / box) * time_since_last_practiced

    Words in lower boxes (more difficult) and words not practiced recently
    have higher probability of being selected.

    Args:
        db: Async database session.
        user_id: The user's UUID.
        language: Filter words by this language.
        count: Number of words to select.
        tag_ids: Optional list of tag IDs to filter by.

    Returns:
        List of selected Word objects.
    """
    query = (
        select(Word)
        .options(selectinload(Word.stats), selectinload(Word.tags))
        .where(Word.user_id == user_id, Word.language == language)
    )

    if tag_ids:
        query = query.join(Word.tags).where(Tag.id.in_(tag_ids))

    result = await db.execute(query)
    all_words = list(result.scalars().unique().all())

    if not all_words:
        return []

    if len(all_words) <= count:
        return all_words

    # Calculate selection weights using Modified Leitner formula
    now = datetime.now(timezone.utc)
    weights: list[float] = []

    for word in all_words:
        stats = word.stats
        if stats is None:
            # No stats yet -- treat as box 1, never practiced (high priority)
            box = 1
            hours_since = 168.0  # Default to 1 week
        else:
            box = stats.box
            if stats.last_practiced is not None:
                last = stats.last_practiced
                if last.tzinfo is None:
                    last = last.replace(tzinfo=timezone.utc)
                delta = now - last
                hours_since = max(delta.total_seconds() / 3600.0, 1.0)
            else:
                hours_since = 168.0  # 1 week default

        # Modified Leitner: weight = (1 / box) * time_since_last_practiced
        weight = (1.0 / box) * hours_since
        weights.append(weight)

    # Weighted random selection without replacement
    selected: list[Word] = []
    candidates = list(zip(all_words, weights))
    total_weight = sum(w for _, w in candidates)

    for _ in range(min(count, len(candidates))):
        if total_weight == 0:
            break

        r = random.uniform(0, total_weight)
        cumulative = 0.0
        chosen_idx = 0

        for idx, (_, w) in enumerate(candidates):
            cumulative += w
            if cumulative >= r:
                chosen_idx = idx
                break

        chosen_word, chosen_w = candidates.pop(chosen_idx)
        total_weight -= chosen_w
        selected.append(chosen_word)

    return selected
