"""The active, bounded API request contract."""
from datetime import date
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class GenerateRequest(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")
    match_id: str | int | None = None
    team1: str | None = Field(None, min_length=1, max_length=80)
    team2: str | None = Field(None, min_length=1, max_length=80)
    format: str | None = Field(None, max_length=20)
    venue: str | None = Field(None, max_length=160)
    date: str | None = None
    use_ml: bool = True
    use_intelligence: bool = True
    scan_news: bool = False
    risk_aversion: float = Field(0.05, ge=0, le=0.2)
    mode: Literal["prediction", "retrospective"] = "prediction"
    allow_relaxation: bool = False

    @field_validator("match_id", mode="before")
    @classmethod
    def valid_id(cls, value):
        if value is None:
            return value
        if isinstance(value, bool) or not isinstance(value, (str, int)):
            raise ValueError("match_id must be a string or integer")
        if not str(value).strip() or len(str(value)) > 128:
            raise ValueError("match_id must contain 1-128 characters")
        return value

    @field_validator("date")
    @classmethod
    def valid_date(cls, value):
        if value is not None:
            if len(value) != 10:
                raise ValueError("date must be YYYY-MM-DD")
            date.fromisoformat(value)
        return value

    @field_validator("format")
    @classmethod
    def valid_format(cls, value):
        if value is not None:
            from model.team_generator import normalize_format
            return normalize_format(value)
        return value

    @model_validator(mode="after")
    def valid_teams(self):
        if self.match_id is None and not (self.team1 and self.team2):
            raise ValueError("Provide match_id or both team1 and team2")
        if self.team1 and self.team2 and self.team1.casefold() == self.team2.casefold():
            raise ValueError("Teams must differ")
        return self


class ExplainRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    explain_token: str = Field(min_length=32, max_length=32, pattern=r"^[a-f0-9]{32}$")


class SaveAnalysisRequest(ExplainRequest):
    title: str = Field(min_length=1, max_length=120)
