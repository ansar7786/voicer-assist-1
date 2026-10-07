from typing import List, Optional
from pydantic import BaseModel, Field

class ProfileSchema(BaseModel):
    language: Optional[str] = "en"
    education_level: Optional[str] = None
    current_or_past_work: Optional[str] = None
    skills: List[str] = Field(default_factory=list)
    assets: List[str] = Field(default_factory=list)
    interests: List[str] = Field(default_factory=list)
    mobility: Optional[str] = None
    max_training_months: Optional[int] = None
    time_available: Optional[str] = None
    work_preference: Optional[str] = None
    urgency_of_income: Optional[str] = None
    location_block: Optional[str] = None
    confidence_flags: dict = Field(default_factory=dict)

class ConstraintSchema(BaseModel):
    max_training_months: Optional[int] = None
    mobility: Optional[str] = None
    work_preference: Optional[str] = None
    time_available: Optional[str] = None

class FactorSchema(BaseModel):
    factor: str
    label: str  # High / Medium / Low / Unknown
    reason: str

class PathwaySchema(BaseModel):
    name: str
    route: str
    qualification: str
    nsqf_level: int
    duration: int
    skill_gap: dict
    nearest_centre: Optional[dict] = None
    opportunity_status: str
    factors: List[FactorSchema] = Field(default_factory=list)
