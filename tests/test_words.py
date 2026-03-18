import pytest

from tests.conftest import TEST_USER_ID


@pytest.mark.asyncio
async def test_create_word(client):
    response = await client.post(
        "/api/words",
        json={
            "word": "bonjour",
            "definition": "hello",
            "language": "French",
        },
    )
    assert response.status_code == 201
    data = response.json()
    assert data["word"] == "bonjour"
    assert data["definition"] == "hello"
    assert data["language"] == "French"
    assert data["user_id"] == str(TEST_USER_ID)
    assert data["stats"] is not None
    assert data["stats"]["box"] == 1


@pytest.mark.asyncio
async def test_create_word_with_context(client):
    response = await client.post(
        "/api/words",
        json={
            "word": "merci",
            "definition": "thank you",
            "language": "French",
            "context_sentence": "Merci beaucoup pour votre aide.",
        },
    )
    assert response.status_code == 201
    data = response.json()
    assert data["context_sentence"] == "Merci beaucoup pour votre aide."


@pytest.mark.asyncio
async def test_create_word_validation_error(client):
    response = await client.post(
        "/api/words",
        json={
            "word": "",
            "definition": "hello",
            "language": "French",
        },
    )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_list_words_empty(client):
    response = await client.get("/api/words")
    assert response.status_code == 200
    data = response.json()
    assert data["items"] == []
    assert data["total"] == 0


@pytest.mark.asyncio
async def test_list_words_with_data(client):
    # Create two words
    await client.post(
        "/api/words",
        json={"word": "hola", "definition": "hello", "language": "Spanish"},
    )
    await client.post(
        "/api/words",
        json={"word": "adios", "definition": "goodbye", "language": "Spanish"},
    )

    response = await client.get("/api/words")
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 2
    assert len(data["items"]) == 2


@pytest.mark.asyncio
async def test_list_words_filter_by_language(client):
    await client.post(
        "/api/words",
        json={"word": "hola", "definition": "hello", "language": "Spanish"},
    )
    await client.post(
        "/api/words",
        json={"word": "bonjour", "definition": "hello", "language": "French"},
    )

    response = await client.get("/api/words", params={"language": "Spanish"})
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 1
    assert data["items"][0]["language"] == "Spanish"


@pytest.mark.asyncio
async def test_list_words_search(client):
    await client.post(
        "/api/words",
        json={"word": "hola", "definition": "hello", "language": "Spanish"},
    )
    await client.post(
        "/api/words",
        json={"word": "adios", "definition": "goodbye", "language": "Spanish"},
    )

    response = await client.get("/api/words", params={"search": "hello"})
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 1


@pytest.mark.asyncio
async def test_get_word(client):
    create_resp = await client.post(
        "/api/words",
        json={"word": "hola", "definition": "hello", "language": "Spanish"},
    )
    word_id = create_resp.json()["id"]

    response = await client.get(f"/api/words/{word_id}")
    assert response.status_code == 200
    assert response.json()["id"] == word_id


@pytest.mark.asyncio
async def test_get_word_not_found(client):
    response = await client.get("/api/words/00000000-0000-0000-0000-000000000000")
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_update_word(client):
    create_resp = await client.post(
        "/api/words",
        json={"word": "hola", "definition": "hello", "language": "Spanish"},
    )
    word_id = create_resp.json()["id"]

    response = await client.patch(
        f"/api/words/{word_id}",
        json={"definition": "hi / hello"},
    )
    assert response.status_code == 200
    assert response.json()["definition"] == "hi / hello"
    assert response.json()["word"] == "hola"  # unchanged


@pytest.mark.asyncio
async def test_delete_word(client):
    create_resp = await client.post(
        "/api/words",
        json={"word": "hola", "definition": "hello", "language": "Spanish"},
    )
    word_id = create_resp.json()["id"]

    response = await client.delete(f"/api/words/{word_id}")
    assert response.status_code == 204

    get_response = await client.get(f"/api/words/{word_id}")
    assert get_response.status_code == 404
