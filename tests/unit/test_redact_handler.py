from unittest.mock import MagicMock, patch

from fakeredis import FakeRedis
from fastapi.testclient import TestClient
from glowplug import DbDriver

from app.server.generated.models import Document, DocumentLink
from app.server.tasks import (
    CallbackTask,
    FetchTask,
    FormatTask,
    RedactionTask,
    callback,
    fetch,
    finalize,
    format,
    redact,
)


# Path the `chain` function from celery to mock it
@patch("app.server.handlers.redaction.chain")
async def test_redact_handler(
    chain_mock: MagicMock,
    api: TestClient,
    exp_db: DbDriver,
    fake_redis_store: FakeRedis,
):
    # Return a fake task ID when calling `chain().apply_async()`
    chain_mock.return_value.apply_async.return_value = "fake_task_id"

    request = {
        "jurisdictionId": "jur1",
        "caseId": "case1",
        "subjects": [
            {
                "role": "accused",
                "subject": {
                    "subjectId": "sub1",
                    "name": "jack doe",
                    "aliases": [
                        {"firstName": "john", "lastName": "p", "middleName": "doe"}
                    ],
                },
            }
        ],
        "objects": [
            {
                "document": {
                    "attachmentType": "LINK",
                    "documentId": "doc1",
                    "url": "https://test_document.pdf",
                },
                "callbackUrl": "https://echo",
            }
        ],
    }

    response = api.post("/api/v1/redact", json=request)
    assert response.status_code == 200

    # Assert that the `chain` function was called with the correct arguments
    chain_mock.assert_called_once()
    # NOTE(jnu): better diff when using `assert` than with `.assert_called_once_with()`
    assert chain_mock.mock_calls[0].args == (
        fetch.s(
            FetchTask(
                document=Document(
                    root=DocumentLink(
                        attachmentType="LINK",
                        documentId="doc1",
                        url="https://test_document.pdf",
                    )
                )
            )
        ),
        redact.s(
            RedactionTask(
                document_id="doc1",
                jurisdiction_id="jur1",
                case_id="case1",
                renderer="PDF",
            )
        ),
        format.s(FormatTask(target_blob_url=None)),
        callback.s(CallbackTask(callback_url="https://echo/")),
        finalize.s(),
    )

    # Check that the right stuff was stored in redis
    assert fake_redis_store.hgetall("jur1:case1:role") == {b"sub1": b"accused"}
    assert fake_redis_store.smembers("jur1:case1:aliases:sub1") == {
        b'{"firstName": "jack", "lastName": "doe", "middleName": "", "nickname": "'
        b'", "suffix": "", "title": ""}',
        b'{"firstName": "john", "lastName": "p", "middleName": "doe", "nickname": '
        b'null, "suffix": null, "title": null}',
    }
    assert fake_redis_store.get("jur1:case1:aliases:sub1:primary") == (
        b'{"firstName": "jack", "lastName": "doe", "middleName": "", '
        b'"nickname": "", "suffix": "", "title": ""}'
    )
    assert fake_redis_store.hgetall("jur1:case1:task") == {b"doc1": b"fake_task_id"}
