from contextlib import asynccontextmanager
from datetime import date, timedelta, datetime
from typing import Annotated

from fastapi import FastAPI, Depends, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from sqlalchemy import func
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from passlib.context import CryptContext
from jose import JWTError, jwt

from database import Base, engine, get_db
from models import Donor, BloodInventory, Donation, Hospital, BloodRequest, BloodDistribution, User
from schemas import (
    DonorCreate,
    DonorResponse,
    InventoryCreate,
    InventoryResponse,
    DonationCreate,
    DonationResponse,
    DonationScreeningUpdate,
    HospitalCreate,
    HospitalResponse,
    BloodRequestCreate,
    BloodRequestResponse,
    BloodRequestUpdate,
    DistributionCreate,
    DistributionResponse,
    DistributionUpdate,
    InventorySummary,
    ExpiryAlert,
    AlertSummary,
    UserCreate,
    UserResponse,
    LoginRequest,
    TokenResponse,
)


SECRET_KEY = "change-me-in-production"
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login")


@asynccontextmanager
async def lifespan(app: FastAPI):
    Base.metadata.create_all(bind=engine)
    yield


app = FastAPI(
    title="BloodLink API",
    description="Blood bank management backend",
    version="1.0.0",
    lifespan=lifespan,
)

Base.metadata.create_all(bind=engine)


# Allow requests from your React development server.
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)


def hash_password(password: str) -> str:
    if password is None:
        raise ValueError("Password is required")
    normalized = password.strip()
    if len(normalized.encode("utf-8")) > 72:
        normalized = normalized.encode("utf-8")[:72].decode("utf-8", errors="ignore")
    return pwd_context.hash(normalized)


def create_access_token(username: str, role: str):
    expires_at = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    payload = {"sub": username, "role": role, "exp": expires_at}
    token = jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)
    return token


def get_current_user(db: Session = Depends(get_db), token: str = Depends(oauth2_scheme)) -> User:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username = payload.get("sub")
        if username is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception

    user = db.query(User).filter(User.username == username).first()
    if user is None:
        raise credentials_exception
    return user


def require_roles(*allowed_roles):
    def dependency(current_user: User = Depends(get_current_user)):
        if current_user.role not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You do not have permission to access this resource.",
            )
        return current_user
    return dependency


@app.get("/")
def home():
    return {
        "message": "Welcome to BloodLink API",
        "status": "running",
    }


@app.get("/health")
def health_check():
    return {"status": "healthy"}


@app.post("/api/auth/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
def register_user(user_data: UserCreate, db: Session = Depends(get_db)):
    user = User(
        username=user_data.username,
        email=user_data.email,
        password_hash=hash_password(user_data.password),
        role=user_data.role,
    )
    db.add(user)
    try:
        db.commit()
        db.refresh(user)
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="Username or email already exists")
    return user


@app.post("/api/auth/login", response_model=TokenResponse)
def login_user(payload: LoginRequest, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.username == payload.username).first()
    if not user or not verify_password(payload.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Invalid username or password")

    token = create_access_token(username=user.username, role=user.role)
    return TokenResponse(access_token=token)


@app.post(
    "/api/donors",
    response_model=DonorResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_donor(
    donor_data: DonorCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("admin", "staff")),
):
    donor = Donor(**donor_data.model_dump())

    db.add(donor)

    try:
        db.commit()
        db.refresh(donor)
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=409,
            detail="A donor with this email already exists.",
        )

    return donor


@app.get("/api/donors", response_model=list[DonorResponse])
def get_donors(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("admin", "staff", "viewer")),
):
    return db.query(Donor).order_by(Donor.id.desc()).all()


@app.get("/api/donors/{donor_id}", response_model=DonorResponse)
def get_donor(
    donor_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("admin", "staff", "viewer")),
):
    donor = db.query(Donor).filter(Donor.id == donor_id).first()

    if donor is None:
        raise HTTPException(status_code=404, detail="Donor not found")

    return donor


@app.post(
    "/api/donations",
    response_model=DonationResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_donation(
    donation_data: DonationCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("admin", "staff")),
):
    donor = db.query(Donor).filter(Donor.id == donation_data.donor_id).first()
    if donor is None:
        raise HTTPException(status_code=404, detail="Donor not found")

    donation = Donation(
        donor_id=donation_data.donor_id,
        blood_group=donation_data.blood_group,
        quantity_ml=donation_data.quantity_ml,
        screening_status=donation_data.screening_status,
        screening_notes=donation_data.screening_notes,
    )

    db.add(donation)
    db.commit()
    db.refresh(donation)

    return donation


@app.get("/api/donations", response_model=list[DonationResponse])
def get_donations(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("admin", "staff", "viewer")),
):
    return db.query(Donation).order_by(Donation.donation_date.desc()).all()


@app.get("/api/donations/{donation_id}", response_model=DonationResponse)
def get_donation(
    donation_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("admin", "staff", "viewer")),
):
    donation = db.query(Donation).filter(Donation.id == donation_id).first()

    if donation is None:
        raise HTTPException(status_code=404, detail="Donation not found")

    return donation


@app.patch(
    "/api/donations/{donation_id}/screening",
    response_model=DonationResponse,
)
def update_donation_screening(
    donation_id: int,
    update_data: DonationScreeningUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("admin", "staff")),
):
    donation = db.query(Donation).filter(Donation.id == donation_id).first()
    if donation is None:
        raise HTTPException(status_code=404, detail="Donation not found")

    donation.screening_status = update_data.screening_status
    donation.screening_notes = update_data.screening_notes

    if update_data.screening_status == "passed":
        inventory = db.query(BloodInventory).filter(
            BloodInventory.blood_group == donation.blood_group,
            BloodInventory.component == "whole_blood",
            BloodInventory.batch_number == f"DON-{donation.id:04d}",
        ).first()

        if inventory is None:
            inventory = BloodInventory(
                blood_group=donation.blood_group,
                component="whole_blood",
                batch_number=f"DON-{donation.id:04d}",
                units=0,
            )
            db.add(inventory)

        inventory.units += donation.quantity_ml

    db.commit()
    db.refresh(donation)

    return donation


@app.post(
    "/api/inventory",
    response_model=InventoryResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_inventory(
    inventory_data: InventoryCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("admin", "staff")),
):
    existing = db.query(BloodInventory).filter(
        BloodInventory.blood_group == inventory_data.blood_group,
        BloodInventory.component == inventory_data.component,
        BloodInventory.batch_number == inventory_data.batch_number,
    ).first()

    if existing:
        raise HTTPException(
            status_code=409,
            detail="This blood batch already exists. Update it instead.",
        )

    inventory = BloodInventory(**inventory_data.model_dump())
    db.add(inventory)
    db.commit()
    db.refresh(inventory)

    return inventory


@app.get("/api/inventory", response_model=list[InventoryResponse])
def get_inventory(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("admin", "staff", "viewer")),
):
    return db.query(BloodInventory).order_by(
        BloodInventory.blood_group,
        BloodInventory.component,
        BloodInventory.batch_number,
    ).all()


@app.get("/api/inventory/{blood_group}", response_model=list[InventoryResponse])
def get_inventory_by_group(
    blood_group: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("admin", "staff", "viewer")),
):
    group = blood_group.upper()

    inventory = db.query(BloodInventory).filter(
        BloodInventory.blood_group == group
    ).order_by(BloodInventory.component, BloodInventory.batch_number).all()

    if not inventory:
        raise HTTPException(
            status_code=404,
            detail="No inventory found for this blood group",
        )

    return inventory


@app.patch(
    "/api/inventory/{blood_group}",
    response_model=InventoryResponse,
)
def update_inventory(
    blood_group: str,
    inventory_data: InventoryCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("admin", "staff")),
):
    group = blood_group.upper()

    if inventory_data.blood_group != group:
        raise HTTPException(
            status_code=400,
            detail="The blood group in the URL and body must match.",
        )

    inventory = db.query(BloodInventory).filter(
        BloodInventory.blood_group == group,
        BloodInventory.component == inventory_data.component,
        BloodInventory.batch_number == inventory_data.batch_number,
    ).first()

    if inventory is None:
        raise HTTPException(
            status_code=404,
            detail="Blood batch not found in inventory",
        )

    inventory.units = inventory_data.units
    inventory.expiry_date = inventory_data.expiry_date
    db.commit()
    db.refresh(inventory)

    return inventory


@app.post(
    "/api/hospitals",
    response_model=HospitalResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_hospital(
    hospital_data: HospitalCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("admin", "staff")),
):
    hospital = Hospital(**hospital_data.model_dump())
    db.add(hospital)

    try:
        db.commit()
        db.refresh(hospital)
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=409,
            detail="A hospital with this name or code already exists.",
        )

    return hospital


@app.get("/api/hospitals", response_model=list[HospitalResponse])
def get_hospitals(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("admin", "staff", "viewer")),
):
    return db.query(Hospital).order_by(Hospital.name).all()


@app.get("/api/hospitals/{hospital_id}", response_model=HospitalResponse)
def get_hospital(
    hospital_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("admin", "staff", "viewer")),
):
    hospital = db.query(Hospital).filter(Hospital.id == hospital_id).first()
    if hospital is None:
        raise HTTPException(status_code=404, detail="Hospital not found")
    return hospital


@app.patch("/api/hospitals/{hospital_id}/status", response_model=HospitalResponse)
def update_hospital_status(
    hospital_id: int,
    is_active: bool,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("admin", "staff")),
):
    hospital = db.query(Hospital).filter(Hospital.id == hospital_id).first()
    if hospital is None:
        raise HTTPException(status_code=404, detail="Hospital not found")

    hospital.is_active = is_active
    db.commit()
    db.refresh(hospital)
    return hospital


@app.post(
    "/api/blood-requests",
    response_model=BloodRequestResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_blood_request(
    request_data: BloodRequestCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("admin", "staff")),
):
    hospital = db.query(Hospital).filter(Hospital.id == request_data.hospital_id).first()
    if hospital is None:
        raise HTTPException(status_code=404, detail="Hospital not found")

    request = BloodRequest(**request_data.model_dump())
    db.add(request)
    db.commit()
    db.refresh(request)

    return request


@app.get("/api/blood-requests", response_model=list[BloodRequestResponse])
def get_blood_requests(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("admin", "staff", "viewer")),
):
    return db.query(BloodRequest).order_by(BloodRequest.request_date.desc()).all()


@app.get("/api/blood-requests/{request_id}", response_model=BloodRequestResponse)
def get_blood_request(
    request_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("admin", "staff", "viewer")),
):
    request = db.query(BloodRequest).filter(BloodRequest.id == request_id).first()
    if request is None:
        raise HTTPException(status_code=404, detail="Blood request not found")
    return request


@app.patch("/api/blood-requests/{request_id}", response_model=BloodRequestResponse)
def update_blood_request(
    request_id: int,
    update_data: BloodRequestUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("admin", "staff")),
):
    request = db.query(BloodRequest).filter(BloodRequest.id == request_id).first()
    if request is None:
        raise HTTPException(status_code=404, detail="Blood request not found")

    request.status = update_data.status
    request.notes = update_data.notes or request.notes
    db.commit()
    db.refresh(request)
    return request


@app.post(
    "/api/distributions",
    response_model=DistributionResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_distribution(
    distribution_data: DistributionCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("admin", "staff")),
):
    request = db.query(BloodRequest).filter(BloodRequest.id == distribution_data.request_id).first()
    if request is None:
        raise HTTPException(status_code=404, detail="Blood request not found")

    inventory = db.query(BloodInventory).filter(BloodInventory.id == distribution_data.inventory_id).first()
    if inventory is None:
        raise HTTPException(status_code=404, detail="Inventory batch not found")

    hospital = db.query(Hospital).filter(Hospital.id == distribution_data.hospital_id).first()
    if hospital is None:
        raise HTTPException(status_code=404, detail="Hospital not found")

    if distribution_data.units_dispatched > inventory.units:
        raise HTTPException(
            status_code=400,
            detail="Dispatch quantity exceeds available inventory units.",
        )

    inventory.units -= distribution_data.units_dispatched

    distribution = BloodDistribution(
        request_id=distribution_data.request_id,
        inventory_id=distribution_data.inventory_id,
        hospital_id=distribution_data.hospital_id,
        units_dispatched=distribution_data.units_dispatched,
        recipient_reference=distribution_data.recipient_reference,
        notes=distribution_data.notes,
    )
    db.add(distribution)
    db.commit()
    db.refresh(distribution)
    return distribution


@app.get("/api/distributions", response_model=list[DistributionResponse])
def get_distributions(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("admin", "staff", "viewer")),
):
    return db.query(BloodDistribution).order_by(BloodDistribution.dispatch_date.desc()).all()


@app.get("/api/distributions/{distribution_id}", response_model=DistributionResponse)
def get_distribution(
    distribution_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("admin", "staff", "viewer")),
):
    distribution = db.query(BloodDistribution).filter(BloodDistribution.id == distribution_id).first()
    if distribution is None:
        raise HTTPException(status_code=404, detail="Distribution record not found")
    return distribution


@app.patch("/api/distributions/{distribution_id}", response_model=DistributionResponse)
def update_distribution(
    distribution_id: int,
    update_data: DistributionUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("admin", "staff")),
):
    distribution = db.query(BloodDistribution).filter(BloodDistribution.id == distribution_id).first()
    if distribution is None:
        raise HTTPException(status_code=404, detail="Distribution record not found")

    distribution.status = update_data.status
    distribution.notes = update_data.notes or distribution.notes
    db.commit()
    db.refresh(distribution)
    return distribution


@app.get("/api/reports/summary", response_model=list[InventorySummary])
def get_inventory_summary(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("admin", "staff", "viewer")),
):
    rows = db.query(
        BloodInventory.blood_group,
        func.sum(BloodInventory.units).label("total_units"),
    ).group_by(BloodInventory.blood_group).all()

    result = []
    for blood_group, total_units in rows:
        breakdown = {
            item.component: item.units
            for item in db.query(BloodInventory)
            .filter(BloodInventory.blood_group == blood_group)
            .all()
        }
        result.append(
            InventorySummary(
                blood_group=blood_group,
                total_units=int(total_units or 0),
                component_breakdown={k: v for k, v in breakdown.items()},
            )
        )

    return result


@app.get("/api/reports/alerts", response_model=AlertSummary)
def get_alerts(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("admin", "staff", "viewer")),
):
    today = date.today()
    expiry_threshold = today + timedelta(days=30)

    low_stock = []
    for inventory in db.query(BloodInventory).all():
        if inventory.units <= 50:
            low_stock.append(
                InventorySummary(
                    blood_group=inventory.blood_group,
                    total_units=inventory.units,
                    component_breakdown={inventory.component: inventory.units},
                )
            )

    expiring_soon = []
    for inventory in db.query(BloodInventory).filter(BloodInventory.expiry_date.isnot(None)).all():
        if inventory.expiry_date and inventory.expiry_date <= expiry_threshold:
            days_remaining = (inventory.expiry_date - today).days
            expiring_soon.append(
                ExpiryAlert(
                    id=inventory.id,
                    blood_group=inventory.blood_group,
                    component=inventory.component,
                    batch_number=inventory.batch_number,
                    units=inventory.units,
                    expiry_date=inventory.expiry_date,
                    days_remaining=days_remaining,
                )
            )

    return AlertSummary(
        low_stock=low_stock,
        expiring_soon=expiring_soon,
    )
