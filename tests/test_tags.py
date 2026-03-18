import pytest


@pytest.mark.asyncio
async def test_create_tag(client):
    response = await client.post("/api/tags", json={"name": "food"})
    assert response.status_code == 201
    data = response.json()
    assert data["name"] == "food"


@pytest.mark.asyncio
async def test_create_duplicate_tag(client):
    await client.post("/api/tags", json={"name": "travel"})
    response = await client.post("/api/tags", json={"name": "travel"})
    assert response.status_code == 409


@pytest.mark.asyncio
async def test_list_tags(client):
    await client.post("/api/tags", json={"name": "animals"})
    await client.post("/api/tags", json={"name": "colors"})

    response = await client.get("/api/tags")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 2
    # Sorted by name
    assert data[0]["name"] == "animals"
    assert data[1]["name"] == "colors"


@pytest.mark.asyncio
async def test_get_tag(client):
    create_resp = await client.post("/api/tags", json={"name": "sports"})
    tag_id = create_resp.json()["id"]

    response = await client.get(f"/api/tags/{tag_id}")
    assert response.status_code == 200
    assert response.json()["name"] == "sports"


@pytest.mark.asyncio
async def test_update_tag(client):
    create_resp = await client.post("/api/tags", json={"name": "old name"})
    tag_id = create_resp.json()["id"]

    response = await client.patch(f"/api/tags/{tag_id}", json={"name": "new name"})
    assert response.status_code == 200
    assert response.json()["name"] == "new name"


@pytest.mark.asyncio
async def test_delete_tag(client):
    create_resp = await client.post("/api/tags", json={"name": "temp"})
    tag_id = create_resp.json()["id"]

    response = await client.delete(f"/api/tags/{tag_id}")
    assert response.status_code == 204

    get_resp = await client.get(f"/api/tags/{tag_id}")
    assert get_resp.status_code == 404


@pytest.mark.asyncio
async def test_create_word_with_tags(client):
    # Create a tag first
    tag_resp = await client.post("/api/tags", json={"name": "greetings"})
    tag_id = tag_resp.json()["id"]

    # Create a word with the tag
    word_resp = await client.post(
        "/api/words",
        json={
            "word": "hola",
            "definition": "hello",
            "language": "Spanish",
            "tag_ids": [tag_id],
        },
    )
    assert word_resp.status_code == 201
    data = word_resp.json()
    assert len(data["tags"]) == 1
    assert data["tags"][0]["name"] == "greetings"
