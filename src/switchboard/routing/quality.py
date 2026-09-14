def is_low_quality(response: dict, min_length: int = 20) -> bool:
    choices = response.get("choices") or [{}]
    choice = choices[0]
    if choice.get("finish_reason") != "stop":
        return True
    content = (choice.get("message") or {}).get("content") or ""
    return len(content.strip()) < min_length