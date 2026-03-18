from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.word import Word
from app.models.word_stats import WordStats
from app.services.word_selection import select_words_for_practice
from tests.conftest import TEST_USER_ID


@pytest.mark.asyncio
async def test_select_words_empty(db_session: AsyncSession):
    """No words exist -- should return empty list."""
    result = await select_words_for_practice(
        db=db_session,
        user_id=TEST_USER_ID,
        language="Spanish",
        count=5,
    )
    assert result == []


@pytest.mark.asyncio
async def test_select_words_fewer_than_count(db_session: AsyncSession):
    """Fewer words than requested -- return all of them."""
    for i in range(3):
        word = Word(
            user_id=TEST_USER_ID,
            word=f"word_{i}",
            definition=f"def_{i}",
            language="Spanish",
        )
        db_session.add(word)
    await db_session.flush()

    result = await select_words_for_practice(
        db=db_session,
        user_id=TEST_USER_ID,
        language="Spanish",
        count=5,
    )
    assert len(result) == 3


@pytest.mark.asyncio
async def test_select_words_respects_language(db_session: AsyncSession):
    """Only words matching the language should be selected."""
    spanish = Word(user_id=TEST_USER_ID, word="hola", definition="hello", language="Spanish")
    french = Word(user_id=TEST_USER_ID, word="bonjour", definition="hello", language="French")
    db_session.add_all([spanish, french])
    await db_session.flush()

    result = await select_words_for_practice(
        db=db_session,
        user_id=TEST_USER_ID,
        language="Spanish",
        count=5,
    )
    assert len(result) == 1
    assert result[0].word == "hola"


@pytest.mark.asyncio
async def test_select_words_prefers_lower_box(db_session: AsyncSession):
    """Words in lower boxes should be selected more frequently."""
    now = datetime.now(timezone.utc)

    # Create words with different box levels but same last_practiced
    words = []
    for i in range(10):
        word = Word(
            user_id=TEST_USER_ID,
            word=f"word_{i}",
            definition=f"def_{i}",
            language="Spanish",
        )
        db_session.add(word)
        await db_session.flush()

        box = 1 if i < 5 else 5
        stats = WordStats(
            word_id=word.id,
            box=box,
            last_practiced=now - timedelta(hours=24),
            success_count=0,
            fail_count=0,
        )
        db_session.add(stats)
        words.append((word, box))

    await db_session.flush()

    # Run selection many times and count how often box-1 words are selected
    box1_count = 0
    trials = 50
    for _ in range(trials):
        selected = await select_words_for_practice(
            db=db_session,
            user_id=TEST_USER_ID,
            language="Spanish",
            count=3,
        )
        for w in selected:
            if any(word.id == w.id and box == 1 for word, box in words):
                box1_count += 1

    # Box 1 words should be selected much more often than box 5 words
    # With weight ratio 5:1, box 1 words should dominate
    total_selections = trials * 3
    box1_ratio = box1_count / total_selections
    assert box1_ratio > 0.5, f"Box 1 words selected {box1_ratio:.0%} of the time, expected >50%"
