"""
Pydantic schemas for SIH26097 Live Voice Livelihood Pathway Engine.
Strict privacy adherence: NO demographic, caste, community, religion, address, or ID fields.
"""
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field

class ProfileSchema(BaseModel):
    language: Optional[str] = "en"
    education_level: Optional[str] = None
    current_or_past_work: Optional[str] = None
    skills: List[str] = Field(default_factory=list)
    assets: List[str] = Field(default_factory=list)
    interests: List[str] = Field(default_factory=list)
    mobility: Optional[str] = None          # e.g., 'home_only', 'local_block', 'district', 'state'
    max_training_months: Optional[int] = None
    time_available: Optional[str] = None     # e.g., 'full_time', 'part_time', 'weekends'
    work_preference: Optional[str] = None    # e.g., 'self', 'wage', 'either'
    urgency_of_income: Optional[str] = None  # e.g., 'urgent', 'moderate', 'flexible'
    location_block: Optional[str] = None
    confidence_flags: Dict[str, Any] = Field(default_factory=dict)

class ConstraintSchema(BaseModel):
    max_training_months: Optional[int] = None
    mobility: Optional[str] = None
    work_preference: Optional[str] = None
    time_available: Optional[str] = None

class FactorSchema(BaseModel):
    factor: str
    label: str  # High / Medium / Low / Unknown
    reason: str

class CentreInfoSchema(BaseModel):
    name: str
    block: str
    seats: int
    next_batch_date: Optional[str] = None
    mode: Optional[str] = None

class PathwaySchema(BaseModel):
    id: str
    name: str
    trade: str
    route: str  # self / wage / both
    qualification: str
    nsqf_level: int
    duration_months: int
    delivery_mode: str = "either"
    equipment_obtainable: int = 1
    skill_gap: List[str] = Field(default_factory=list)
    nearest_centre: Optional[CentreInfoSchema] = None
    opportunity_status: str  # Exactly "No verified opportunity found" if none
    factors: List[FactorSchema] = Field(default_factory=list)

class ExcludedPathwaySchema(BaseModel):
    id: str
    name: str
    trade: str
    reason: str

class PathwaysResultSchema(BaseModel):
    pathways: List[PathwaySchema] = Field(default_factory=list)
    excluded: List[ExcludedPathwaySchema] = Field(default_factory=list)
    no_result_reasons: List[str] = Field(default_factory=list)

class DiffItemSchema(BaseModel):
    id: str
    name: str
    trade: str
    reason: str

class PathwayDiffSchema(BaseModel):
    added: List[DiffItemSchema] = Field(default_factory=list)
    removed: List[DiffItemSchema] = Field(default_factory=list)
    kept: List[DiffItemSchema] = Field(default_factory=list)

class RecomputeResultSchema(BaseModel):
    pathways: List[PathwaySchema] = Field(default_factory=list)
    excluded: List[ExcludedPathwaySchema] = Field(default_factory=list)
    diff: PathwayDiffSchema

class PathwaysRequest(BaseModel):
    profile: ProfileSchema
    constraints: Optional[ConstraintSchema] = None

class RecomputeRequest(BaseModel):
    profile: ProfileSchema
    previous_pathway_ids: List[str] = Field(default_factory=list)
    constraints: Optional[ConstraintSchema] = None
