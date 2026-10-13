"""Submission execution boundaries. Only an injected authorized API may submit."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Literal

from app.applications.policy import (
    ApplicationPolicyService,
    SubmissionContext,
    SubmissionPolicyResult,
)
from app.job_sources.schemas import SourceCapability

ExecutorStatus = Literal["prepared", "awaiting_user", "manual_application_required", "submitted"]


@dataclass(frozen=True)
class ApplicationPackage:
    resume_reference: str | None
    cover_letter: str | None
    question_answers: dict[str, str]
    job_url: str
    recruiter_message: str | None = None


@dataclass(frozen=True)
class ExecutionResult:
    status: ExecutorStatus
    message: str
    idempotency_key: str
    external_application_id: str | None = None


class ApplicationExecutor(ABC):
    @abstractmethod
    def validate(
        self, context: SubmissionContext, source: SourceCapability
    ) -> SubmissionPolicyResult: ...
    @abstractmethod
    def prepare(self, package: ApplicationPackage, idempotency_key: str) -> ExecutionResult: ...
    @abstractmethod
    def submit(
        self, package: ApplicationPackage, context: SubmissionContext, source: SourceCapability
    ) -> ExecutionResult: ...
    @abstractmethod
    def get_status(self, idempotency_key: str) -> ExecutionResult | None: ...


@dataclass
class _BaseExecutor(ApplicationExecutor):
    policy: ApplicationPolicyService = field(default_factory=ApplicationPolicyService)
    _results: dict[str, ExecutionResult] = field(default_factory=dict)

    def validate(
        self, context: SubmissionContext, source: SourceCapability
    ) -> SubmissionPolicyResult:
        return self.policy.evaluate_submission(context, source)

    def get_status(self, idempotency_key: str) -> ExecutionResult | None:
        return self._results.get(idempotency_key)


class AuthorizedApiExecutor(_BaseExecutor):
    """Does not contain a client; production injects one only after authorization review."""

    def prepare(self, package: ApplicationPackage, idempotency_key: str) -> ExecutionResult:
        result = ExecutionResult("prepared", "Authorized API package prepared.", idempotency_key)
        self._results.setdefault(idempotency_key, result)
        return self._results[idempotency_key]

    def submit(
        self, package: ApplicationPackage, context: SubmissionContext, source: SourceCapability
    ) -> ExecutionResult:
        if existing := self._results.get(context.idempotency_key):
            return existing
        decision = self.validate(context, source)
        if not decision.allowed or decision.requires_user_confirmation:
            result = ExecutionResult("awaiting_user", decision.reason, context.idempotency_key)
            self._results[context.idempotency_key] = result
            return result
        # Intentionally no network call: a reviewed integration must provide it.
        result = ExecutionResult(
            "awaiting_user", "No authorized API integration is configured.", context.idempotency_key
        )
        self._results[context.idempotency_key] = result
        return result


class AssistedApplicationExecutor(_BaseExecutor):
    def prepare(self, package: ApplicationPackage, idempotency_key: str) -> ExecutionResult:
        result = ExecutionResult(
            "awaiting_user",
            "Open Application to complete this assisted application.",
            idempotency_key,
        )
        self._results.setdefault(idempotency_key, result)
        return self._results[idempotency_key]

    def submit(
        self, package: ApplicationPackage, context: SubmissionContext, source: SourceCapability
    ) -> ExecutionResult:
        return self.prepare(package, context.idempotency_key)


class ManualApplicationExecutor(AssistedApplicationExecutor):
    def prepare(self, package: ApplicationPackage, idempotency_key: str) -> ExecutionResult:
        result = ExecutionResult(
            "manual_application_required",
            "Application package is ready for manual completion.",
            idempotency_key,
        )
        self._results.setdefault(idempotency_key, result)
        return self._results[idempotency_key]
