from ..generated.models import RedactionStatus


def get_redaction_status(*, jurisdiction_id: str, case_id: str) -> RedactionStatus:
    return RedactionStatus(
        jurisdictionId=jurisdiction_id,
        caseId=case_id,
        requests=[],
    )
