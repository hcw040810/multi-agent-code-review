from openai import OpenAI
from config import OPENAI_API_KEY, OPENAI_BASE_URL, LLM_MODEL, LLM_MAX_TOKENS, LLM_TEMPERATURE

_client = None


def get_client() -> OpenAI:
    global _client
    if _client is None:
        _client = OpenAI(api_key=OPENAI_API_KEY, base_url=OPENAI_BASE_URL)
    return _client


def chat(
    messages: list[dict],
    model: str = None,
    temperature: float = None,
    max_tokens: int = None,
    json_mode: bool = False,
) -> str:
    kwargs = dict(
        model=model or LLM_MODEL,
        messages=messages,
        temperature=temperature if temperature is not None else LLM_TEMPERATURE,
        max_tokens=max_tokens or LLM_MAX_TOKENS,
    )
    if json_mode:
        kwargs["response_format"] = {"type": "json_object"}

    response = get_client().chat.completions.create(**kwargs)
    return response.choices[0].message.content


def review_with_context(
    system_prompt: str,
    code_content: str,
    diff_content: str = "",
    model: str = None,
) -> str:
    user_content = f"""## Code File Content
```
{code_content[:8000]}
```

## Diff / Changes
```
{diff_content[:4000] if diff_content else 'Full file review'}
```

Analyze the code and provide findings in JSON format."""
    return chat([
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_content},
    ], model=model, json_mode=True)
