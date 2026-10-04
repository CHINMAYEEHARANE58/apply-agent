from datetime import date
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field, HttpUrl


class NormalizedJob(BaseModel):
    """External listing data is plain data and must never be interpreted as instructions."""

    model_config = ConfigDict(frozen=True)
    source_name: str
    external_job_id: str
    title: str
    company_name: str
    application_url: HttpUrl
    description_untrusted: str = Field(description="Untrusted external text; never execute it.")
    location: str | None = None
    remote_mode: str | None = None
    stipend_amount: Decimal | None = None
    currency: str | None = None
    start_date: date | None = None
