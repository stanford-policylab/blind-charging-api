# generated by fastapi-codegen:
#   filename:  ../../stanford-policylab/blind-charging-api/app/schema/openapi.yaml
#   timestamp: 2024-07-25T20:52:08+00:00

from __future__ import annotations

from enum import Enum
from typing import List, Optional, Union

from pydantic import AnyUrl, AwareDatetime, BaseModel, Field, RootModel
from typing_extensions import Literal


class Error(BaseModel):
    message: str


class AttachmentType(Enum):
    LINK = 'LINK'


class DocumentLink(BaseModel):
    attachmentType: Literal['LINK']
    documentId: str
    url: AnyUrl


class AttachmentType1(Enum):
    TEXT = 'TEXT'


class DocumentText(BaseModel):
    attachmentType: Literal['TEXT']
    documentId: str
    content: str


class AttachmentType2(Enum):
    BASE64 = 'BASE64'


class DocumentContent(BaseModel):
    attachmentType: Literal['BASE64']
    documentId: str
    content: str


class Document(RootModel[Union[DocumentLink, DocumentText, DocumentContent]]):
    root: Union[DocumentLink, DocumentText, DocumentContent] = Field(
        ..., discriminator='attachmentType'
    )


class Status(Enum):
    COMPLETE = 'COMPLETE'


class Status1(Enum):
    ERROR = 'ERROR'


class Status2(Enum):
    QUEUED = 'QUEUED'
    PROCESSING = 'PROCESSING'


class HumanName(BaseModel):
    title: Optional[str] = None
    firstName: str
    lastName: Optional[str] = None
    middleName: Optional[str] = None
    suffix: Optional[str] = None
    nickname: Optional[str] = None


class MaskedSubject(BaseModel):
    subjectId: str
    alias: str


class Person(BaseModel):
    subjectId: str
    name: Union[str, HumanName]
    aliases: Optional[List[Union[str, HumanName]]] = None


class Subject(BaseModel):
    role: str
    subject: Person


class RedactionTarget(BaseModel):
    document: Document
    callbackUrl: AnyUrl
    targetBlobUrl: Optional[AnyUrl] = None


class ReviewTimestamps(BaseModel):
    pageOpen: AwareDatetime
    decision: AwareDatetime


class FinalChargingDecision(Enum):
    CHARGE = 'CHARGE'
    DECLINE = 'DECLINE'


class FinalChargeOutcome(BaseModel):
    finalChargingDecision: FinalChargingDecision = Field(
        ..., description='The final charging decision.', examples=['CHARGE']
    )
    finalChargingDecisionExplanation: Optional[str] = Field(
        None, examples=['The accused was caught on camera with the stolen goods.']
    )


class OutcomeType(Enum):
    BLIND_DECISION = 'BLIND_DECISION'


class BlindChargingDecision(Enum):
    CHARGE_LIKELY = 'CHARGE_LIKELY'
    CHARGE_MAYBE = 'CHARGE_MAYBE'
    DECLINE_MAYBE = 'DECLINE_MAYBE'
    DECLINE_LIKELY = 'DECLINE_LIKELY'


class BlindDecisionOutcome(BaseModel):
    outcomeType: Literal['BLIND_DECISION'] = Field(..., examples=['BLIND_DECISION'])
    blindChargingDecision: BlindChargingDecision = Field(
        ...,
        description='The likely charging decision after blind review.',
        examples=['CHARGE_LIKELY'],
    )
    blindChargingDecisionExplanation: Optional[str] = Field(
        None, examples=['The accused was caught on camera with the stolen goods.']
    )
    additionalEvidence: Optional[str] = Field(
        None, examples=['The accused has a history of theft.']
    )


class OutcomeType1(Enum):
    DISQUALIFICATION = 'DISQUALIFICATION'


class DisqualifyingReason(Enum):
    ASSIGNED_TO_UNBLIND = 'ASSIGNED_TO_UNBLIND'
    CASE_TYPE_INELIGIBLE = 'CASE_TYPE_INELIGIBLE'
    PRIOR_KNOWLEDGE_BIAS = 'PRIOR_KNOWLEDGE_BIAS'
    NARRATIVE_INCOMPLETE = 'NARRATIVE_INCOMPLETE'
    REDACTION_MISSING = 'REDACTION_MISSING'
    REDACTION_ILLEGIBLE = 'REDACTION_ILLEGIBLE'
    OTHER = 'OTHER'


class DisqualifyOutcome(BaseModel):
    outcomeType: Literal['DISQUALIFICATION'] = Field(..., examples=['DISQUALIFICATION'])
    disqualifyingReason: DisqualifyingReason = Field(
        ..., examples=['CASE_TYPE_INELIGIBLE']
    )
    disqualifyingReasonExplanation: Optional[str] = Field(
        None,
        examples=['I have prior knowledge of the individuals involved in this case.'],
    )


class ReviewProtocol(Enum):
    BLIND_REVIEW = 'BLIND_REVIEW'
    FINAL_REVIEW = 'FINAL_REVIEW'


class Protocol(Enum):
    BLIND_REVIEW = 'BLIND_REVIEW'


class BlindReviewDecision(BaseModel):
    protocol: Literal['BLIND_REVIEW'] = Field(..., examples=['BLIND_REVIEW'])
    outcome: Union[BlindDecisionOutcome, DisqualifyOutcome] = Field(
        ..., discriminator='outcomeType'
    )


class Protocol1(Enum):
    FINAL_REVIEW = 'FINAL_REVIEW'


class FinalReviewDecision(BaseModel):
    protocol: Literal['FINAL_REVIEW'] = Field(..., examples=['FINAL_REVIEW'])
    outcome: FinalChargeOutcome


class ReviewDecision(RootModel[Union[BlindReviewDecision, FinalReviewDecision]]):
    root: Union[BlindReviewDecision, FinalReviewDecision] = Field(
        ..., discriminator='protocol'
    )


class Exposure(BaseModel):
    jurisdictionId: str
    caseId: str
    subjectId: str
    reviewingAttorneyMaskedId: str
    documentIds: List[str] = Field(..., min_length=1)
    protocol: ReviewProtocol


class Review(BaseModel):
    jurisdictionId: str
    caseId: str
    subjectId: str
    reviewingAttorneyMaskedId: str
    documentIds: List[str] = Field(..., min_length=1)
    decision: ReviewDecision
    timestamps: ReviewTimestamps


class APIStatus(BaseModel):
    detail: str


class BlindReviewInfo(BaseModel):
    jurisdictionId: str
    caseId: str
    blindReviewRequired: bool
    maskedSubjects: List[MaskedSubject]


class RedactionResultSuccess(BaseModel):
    jurisdictionId: str
    caseId: str
    inputDocumentId: str
    maskedSubjects: List[MaskedSubject]
    redactedDocument: Document
    status: Literal['COMPLETE']


class RedactionResultError(BaseModel):
    jurisdictionId: str
    caseId: str
    inputDocumentId: str
    maskedSubjects: List[MaskedSubject]
    error: str
    status: Literal['ERROR']


class RedactionResultPending(BaseModel):
    jurisdictionId: str
    caseId: str
    inputDocumentId: str
    maskedSubjects: List[MaskedSubject]
    status: Literal['QUEUED', 'PROCESSING']


class RedactionResultCompleted(
    RootModel[Union[RedactionResultSuccess, RedactionResultError]]
):
    root: Union[RedactionResultSuccess, RedactionResultError] = Field(
        ...,
        description='A completed redaction job. Similar to `RedactionResult`,\nbut where it is not possible to see a result in an incomplete (pending or queued) state.\n',
        discriminator='status',
    )


class RedactionResult(
    RootModel[
        Union[RedactionResultSuccess, RedactionResultError, RedactionResultPending]
    ]
):
    root: Union[
        RedactionResultSuccess, RedactionResultError, RedactionResultPending
    ] = Field(
        ..., description='Information about a redaction job.\n', discriminator='status'
    )


class RedactionStatus(BaseModel):
    jurisdictionId: str
    caseId: str
    requests: List[RedactionResult]


class RedactionRequest(BaseModel):
    jurisdictionId: str
    caseId: str
    subjects: List[Subject] = Field(..., min_length=1)
    objects: List[RedactionTarget] = Field(..., min_length=1)
