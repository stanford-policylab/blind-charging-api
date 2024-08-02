import responses

from app.server.generated.models import Document, DocumentLink
from app.server.tasks import FetchTask, FetchTaskResult, fetch


@responses.activate
def test_fetch_link():
    responses.add(
        responses.GET,
        "http://doc.test.local/abc123",
        body=b"hello world",
        status=200,
    )

    params = FetchTask(
        document=Document(
            root=DocumentLink(
                documentId="doc1",
                attachmentType="LINK",
                url="http://doc.test.local/abc123",
            )
        )
    )

    result = fetch.s(params).apply()

    assert result.get() == FetchTaskResult(
        document_id="doc1",
        file_bytes=b"hello world",
    )


@responses.activate
def test_fetch_link_error_code():
    responses.add(
        responses.GET,
        "http://doc.test.local/abc123",
        body=b"failure",
        status=404,
    )

    params = FetchTask(
        document=Document(
            root=DocumentLink(
                documentId="doc1",
                attachmentType="LINK",
                url="http://doc.test.local/abc123",
            )
        )
    )

    result = fetch.s(params).apply()

    assert result.get().model_dump() == {
        "document_id": "doc1",
        "file_bytes": b"",
        "errors": [
            {
                "message": "404 Client Error: Not Found for url: http://doc.test.local/abc123",
                "task": "fetch",
                "exception": "HTTPError",
            }
        ],
    }
