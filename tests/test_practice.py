import uuid

import pytest



@pytest.mark.asyncio
async def test_select_words_endpoint(client):
    """Create words then call the select-words endpoint."""
    # Create some words first
    for i in range(5):
        await client.post(
            "/api/words",
            json={
                "word": f"palabra_{i}",
                "definition": f"word_{i}",
                "language": "Spanish",
            },
        )

    response = await client.post(
        "/api/practice/select-words",
        json={"language": "Spanish", "count": 3},
    )
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 3
    assert all("word" in w and "definition" in w for w in data)


@pytest.mark.asyncio
async def test_select_words_no_words(client):
    response = await client.post(
        "/api/practice/select-words",
        json={"language": "Spanish", "count": 3},
    )
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_create_practice_session(client):
    # Create words
    word_ids = []
    for i in range(3):
        resp = await client.post(
            "/api/words",
            json={
                "word": f"mot_{i}",
                "definition": f"word_{i}",
                "language": "French",
            },
        )
        word_ids.append(resp.json()["id"])

    # Create session
    response = await client.post(
        "/api/practice/sessions",
        json={"language": "French", "word_ids": word_ids},
    )
    assert response.status_code == 201
    data = response.json()
    assert data["language"] == "French"
    assert data["word_count"] == 3
    assert data["user_writing"] is None
    assert data["completed_at"] is None
    assert len(data["results"]) == 3


@pytest.mark.asyncio
async def test_get_practice_session(client):
    # Create a word and session
    word_resp = await client.post(
        "/api/words",
        json={"word": "hallo", "definition": "hello", "language": "German"},
    )
    word_id = word_resp.json()["id"]

    session_resp = await client.post(
        "/api/practice/sessions",
        json={"language": "German", "word_ids": [word_id]},
    )
    session_id = session_resp.json()["id"]

    response = await client.get(f"/api/practice/sessions/{session_id}")
    assert response.status_code == 200
    assert response.json()["id"] == session_id


@pytest.mark.asyncio
async def test_get_practice_session_not_found(client):
    fake_id = "00000000-0000-0000-0000-000000000000"
    response = await client.get(f"/api/practice/sessions/{fake_id}")
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_create_session_invalid_word_ids(client):
    fake_id = str(uuid.uuid4())
    response = await client.post(
        "/api/practice/sessions",
        json={"language": "French", "word_ids": [fake_id]},
    )
    assert response.status_code == 400
