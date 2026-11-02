import pytest
from app.tasks import execute

def test_tasks():
    assert execute("uppercase", "hello") == "HELLO"
    assert execute("reverse", "abc") == "cba"
    assert execute("word_count", "two words") == "2"

def test_unknown_task():
    with pytest.raises(ValueError):
        execute("unknown", "hello")
