"""Pure demo job tasks."""
def execute(task: str, payload: str):
    if task == "uppercase":
        return payload.upper()
    if task == "reverse":
        return payload[::-1]
    if task == "word_count":
        return str(len(payload.split()))
    raise ValueError("Unknown task")
