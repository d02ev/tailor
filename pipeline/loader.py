import httpx
from config import settings


def _get(url: str) -> dict | list:
    """Shared authenticated GET helper for all resume API endpoints."""
    with httpx.Client(timeout=15.0) as client:
        response = client.get(
            url,
            headers={
                "X-Api-Key": f"{settings.api_key}",
                "Accept": "application/json",
            },
        )
        response.raise_for_status()
        return response.json()


def fetch_resume() -> dict:
    """
    Fetch the resume from the source API and unwrap the response envelope.

    API response shape:
        { "statusCode": 200, "data": { ...resume... }, ... }

    Returns the inner "data" dict only.
    """
    resume_api_url = f"{settings.api_base_url}/resume"
    body = _get(resume_api_url)
    if "data" not in body:
        raise KeyError(
            f"Expected 'data' key in resume API response. Got: {list(body.keys())}"
        )
    return _validate_resume(body["data"])


def _validate_resume(data) -> dict:
    """
    Fail early with a clear message if the API returns something the pipeline
    can't optimise, rather than surfacing an AttributeError deep in Pass 1.
    """
    if not isinstance(data, dict):
        raise TypeError(
            f"Expected resume 'data' to be an object, got {type(data).__name__}"
        )
    rewriteable = {"experience", "projects", "techStack"}
    if not rewriteable & data.keys():
        raise ValueError(
            "Resume 'data' has none of the expected rewriteable sections "
            f"({', '.join(sorted(rewriteable))}). Got keys: {list(data.keys())}"
        )
    return data


def fetch_projects() -> list[dict]:
    """
    Fetch the full projects list from the projects endpoint and unwrap the envelope.

    API response shape:
        { "statusCode": 200, "data": [ {...project...}, ... ], ... }

    Returns the inner "data" list only.
    """
    project_api_url = f"{settings.api_base_url}/project"
    body = _get(project_api_url)
    if "data" not in body:
        raise KeyError(
            f"Expected 'data' key in projects API response. Got: {list(body.keys())}"
        )
    data = body["data"]
    if not isinstance(data, list):
        raise TypeError(
            f"Expected projects 'data' to be a list, got {type(data).__name__}"
        )
    return data