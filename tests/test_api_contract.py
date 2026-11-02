"""Validate request schemas without requiring running infrastructure."""
import pytest
from pydantic import ValidationError
from app.main import JobRequest

def test_valid_job():
    job = JobRequest(task="uppercase", payload="hello")
    assert job.task == "uppercase"

def test_invalid_task():
    with pytest.raises(ValidationError):
        JobRequest(task="shell", payload="hello")
