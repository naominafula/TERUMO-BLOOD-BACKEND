from pydantic import BaseModel, ConfigDict, Field, EmailStr
from typing import Optional, Literal
from datetime import date, datetime


BloodGroup = Literal[
    "A+", "A-", "B+", "B-",
    "AB+", "AB-", "O+", "O-"
]
ScreeningStatus = Literal["pending", "passed", "rejected"]
BloodComponent = Literal["whole_blood", "red_cells", "plasma", "platelets"]
RequestPriority = Literal["low", "medium", "high", "urgent"]
RequestStatus = Literal["pending", "approved", "rejected", "fulfilled"]
DistributionStatus = Literal["dispatched", "received", "rejected"]
UserRole = Literal["admin", "staff", "viewer"]


class DonorCreate(BaseModel):
    full_name: str = Field(min_length=2, max_length=120)
    email: Optional[EmailStr] = None
    phone: str = Field(min_length=7, max_length=30)
    blood_group: BloodGroup
    location: Optional[str] = Field(default=None, max_length=150)


class DonorResponse(BaseModel):
    id: int
    full_name: str
    email: Optional[str] = None
    phone: str
    blood_group: str
    location: Optional[str] = None
    is_active: bool
    created_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


class InventoryCreate(BaseModel):
    blood_group: BloodGroup
    component: BloodComponent = "whole_blood"
    batch_number: str = Field(min_length=1, max_length=50)
    units: int = Field(ge=0, le=100000)
    expiry_date: Optional[date] = None


class InventoryResponse(BaseModel):
    id: int
    blood_group: str
    component: str
    batch_number: str
    units: int
    expiry_date: Optional[date] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


class DonationCreate(BaseModel):
    donor_id: int
    blood_group: BloodGroup
    quantity_ml: int = Field(gt=0, le=1000)
    screening_status: ScreeningStatus = "pending"
    screening_notes: Optional[str] = Field(default=None, max_length=500)


class DonationResponse(BaseModel):
    id: int
    donor_id: int
    blood_group: str
    quantity_ml: int
    donation_date: Optional[datetime] = None
    screening_status: str
    screening_notes: Optional[str] = None
    created_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


class DonationScreeningUpdate(BaseModel):
    screening_status: ScreeningStatus
    screening_notes: Optional[str] = Field(default=None, max_length=500)


class HospitalCreate(BaseModel):
    name: str = Field(min_length=2, max_length=150)
    code: str = Field(min_length=2, max_length=30)
    location: str = Field(min_length=2, max_length=200)
    contact_phone: Optional[str] = Field(default=None, max_length=30)
    email: Optional[EmailStr] = None
    is_active: bool = True


class HospitalResponse(BaseModel):
    id: int
    name: str
    code: str
    location: str
    contact_phone: Optional[str] = None
    email: Optional[str] = None
    is_active: bool
    created_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


class BloodRequestCreate(BaseModel):
    hospital_id: int
    blood_group: BloodGroup
    component: BloodComponent = "whole_blood"
    units_needed: int = Field(gt=0, le=10000)
    priority: RequestPriority = "medium"
    notes: Optional[str] = Field(default=None, max_length=500)


class BloodRequestResponse(BaseModel):
    id: int
    hospital_id: int
    blood_group: str
    component: str
    units_needed: int
    priority: str
    status: str
    notes: Optional[str] = None
    request_date: Optional[datetime] = None
    created_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


class BloodRequestUpdate(BaseModel):
    status: RequestStatus
    notes: Optional[str] = Field(default=None, max_length=500)


class DistributionCreate(BaseModel):
    request_id: int
    inventory_id: int
    hospital_id: int
    units_dispatched: int = Field(gt=0, le=10000)
    recipient_reference: Optional[str] = Field(default=None, max_length=100)
    notes: Optional[str] = Field(default=None, max_length=500)


class DistributionResponse(BaseModel):
    id: int
    request_id: int
    inventory_id: int
    hospital_id: int
    units_dispatched: int
    dispatch_date: Optional[datetime] = None
    status: str
    recipient_reference: Optional[str] = None
    notes: Optional[str] = None
    created_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


class DistributionUpdate(BaseModel):
    status: DistributionStatus
    notes: Optional[str] = Field(default=None, max_length=500)


class InventorySummary(BaseModel):
    blood_group: str
    total_units: int
    component_breakdown: dict[str, int]


class ExpiryAlert(BaseModel):
    id: int
    blood_group: str
    component: str
    batch_number: str
    units: int
    expiry_date: Optional[date]
    days_remaining: Optional[int]


class AlertSummary(BaseModel):
    low_stock: list[InventorySummary]
    expiring_soon: list[ExpiryAlert]


class UserCreate(BaseModel):
    username: str = Field(min_length=2, max_length=80)
    email: EmailStr
    password: str = Field(min_length=6, max_length=255)
    role: UserRole = "staff"


class UserResponse(BaseModel):
    id: int
    username: str
    email: str
    role: str
    is_active: bool
    created_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


class LoginRequest(BaseModel):
    username: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
