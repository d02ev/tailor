import httpx
from config import settings


def publish_resume(
    final_resume: dict,
    template_id: str,
    resume_name: str,
    company_name: str | None = None,
) -> None:
    """
    POST the final optimised resume to the configured output API endpoint.

    Request body shape:
        {
            "resumeData":  { ...optimised resume dict... },
            "templateId":  "<template_id>",
            "resumeName":  "<resume_name>",
            "companyName": "<company_name>"   # present only in JD mode
        }

    Raises httpx.HTTPStatusError on non-2xx responses.
    """
    payload: dict = {
        "resumeData": final_resume,
        "templateId": template_id,
        "resumeName": resume_name,
    }

    if company_name:
        payload["companyName"] = company_name

    with httpx.Client(timeout=15.0) as client:
        response = client.post(
            f"{settings.api_base_url}/resume/generate",
            headers={
                "X-Api-Key": f"{settings.api_key}",
                "Content-Type":  "application/json",
            },
            json=payload,
        )
        response.raise_for_status()