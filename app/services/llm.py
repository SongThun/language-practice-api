import json

import anthropic

from app.config import settings

# Module-level cached client
_client: anthropic.AsyncAnthropic | None = None


def _get_client() -> anthropic.AsyncAnthropic:
    global _client
    if _client is None:
        _client = anthropic.AsyncAnthropic(api_key=settings.ANTHROPIC_API_KEY)
    return _client


def _strip_code_fence(text: str) -> str:
    """Strip markdown code fences from LLM response text."""
    if "```json" in text:
        text = text.split("```json")[1].split("```")[0]
    elif "```" in text:
        text = text.split("```")[1].split("```")[0]
    return text.strip()


def _format_word_entries(words: list[dict[str, str]]) -> str:
    entries = "\n".join(
        f"<word><term>{w['word']}</term><definition>{w['definition']}</definition></word>"
        for w in words
    )
    return f"<vocabulary>\n{entries}\n</vocabulary>"


async def suggest_definition(word: str, context_sentence: str, language: str) -> str:
    client = _get_client()

    prompt = (
        f"Provide a concise definition or English translation for the {language} "
        f'word/phrase "{word}".'
    )
    if context_sentence:
        prompt += f'\n\nContext: "{context_sentence}"'
    prompt += (
        "\n\nRespond with ONLY the definition, nothing else. "
        "Keep it brief (one short sentence or a few words)."
    )

    message = await client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=256,
        messages=[{"role": "user", "content": prompt}],
    )

    return message.content[0].text.strip()


async def generate_example_sentences(
    words: list[dict[str, str]],
    language: str,
) -> dict[str, str]:
    client = _get_client()

    vocab_xml = _format_word_entries(words)

    message = await client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=1024,
        messages=[
            {
                "role": "user",
                "content": (
                    f"Generate one natural example sentence for each of the following "
                    f"{language} words/phrases. The sentences should demonstrate proper usage "
                    f"and be appropriate for a language learner.\n\n"
                    f"{vocab_xml}\n\n"
                    f"Respond in JSON format only, as a mapping from the word to its example sentence. "
                    f'Example: {{"word1": "sentence1", "word2": "sentence2"}}'
                ),
            }
        ],
    )

    response_text = _strip_code_fence(message.content[0].text)
    examples = json.loads(response_text)

    # Map back to word IDs
    word_to_id = {w["word"]: w["id"] for w in words}
    result = {}
    for word_text, sentence in examples.items():
        word_id = word_to_id.get(word_text)
        if word_id:
            result[word_id] = sentence

    return result


async def evaluate_writing(
    user_writing: str,
    words: list[dict[str, str]],
    language: str,
) -> dict:
    client = _get_client()

    vocab_xml = _format_word_entries(words)

    message = await client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=2048,
        messages=[
            {
                "role": "user",
                "content": (
                    f"You are a {language} language tutor. A student was asked to write "
                    f"sentences or a short text incorporating the following vocabulary words:\n\n"
                    f"{vocab_xml}\n\n"
                    f"The student wrote:\n"
                    f"<user_writing>\n{user_writing}\n</user_writing>\n\n"
                    f"Evaluate the writing. Respond in JSON format only with this structure:\n"
                    f"{{\n"
                    f'  "overall_feedback": "General feedback about the writing quality",\n'
                    f'  "grammar_notes": "Specific grammar issues and corrections",\n'
                    f'  "word_evaluations": [\n'
                    f"    {{\n"
                    f'      "word": "the vocabulary word",\n'
                    f'      "is_correct": true/false,\n'
                    f'      "feedback": "How the word was used and any corrections"\n'
                    f"    }}\n"
                    f"  ]\n"
                    f"}}\n\n"
                    f"Evaluate EVERY word in the list. is_correct should be true if the word "
                    f"was used correctly in context, false if it was misused or missing."
                ),
            }
        ],
    )

    response_text = _strip_code_fence(message.content[0].text)
    evaluation = json.loads(response_text)

    # Map word names back to IDs
    word_to_id = {w["word"]: w["id"] for w in words}
    for word_eval in evaluation.get("word_evaluations", []):
        word_name = word_eval.get("word", "")
        word_eval["word_id"] = word_to_id.get(word_name)

    return evaluation
