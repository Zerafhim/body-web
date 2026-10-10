from contextlib import asynccontextmanager
from datetime import date as DateValue, datetime, timezone
import hashlib
import hmac
import os
from pathlib import Path
import random
import re
import secrets
from typing import AsyncGenerator, Generator

from fastapi import Depends, FastAPI, HTTPException, Request, Response, status
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import Date, DateTime, Float, ForeignKey, Integer, String, create_engine, select
from sqlalchemy.engine import Engine
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column, sessionmaker
from starlette.middleware.sessions import SessionMiddleware


BASE_DIR = Path(__file__).resolve().parent
DATABASE_URL = os.getenv("DATABASE_URL", f"sqlite:///{BASE_DIR / 'body_data.db'}")
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql+psycopg://", 1)
elif DATABASE_URL.startswith("postgresql://"):
    DATABASE_URL = DATABASE_URL.replace("postgresql://", "postgresql+psycopg://", 1)

IS_DEPLOYED = bool(os.getenv("RENDER") or os.getenv("VERCEL"))
SESSION_SECRET = os.getenv("SESSION_SECRET")
if not SESSION_SECRET:
    if IS_DEPLOYED:
        raise RuntimeError("SESSION_SECRET must be configured in the deployment environment.")
    SESSION_SECRET = secrets.token_urlsafe(48)

engine_options: dict[str, object] = {"pool_pre_ping": True}
if DATABASE_URL.startswith("sqlite"):
    engine_options["connect_args"] = {"check_same_thread": False}
engine: Engine = create_engine(DATABASE_URL, **engine_options)
SessionFactory = sessionmaker(bind=engine, expire_on_commit=False)


class BMI:
    """Calculate and classify a body's BMI."""

    @staticmethod
    def calculate(weight: float, height: float) -> float:
        if weight < 0:
            raise ValueError("weight must be non-negative")
        if height <= 0:
            raise ValueError("height must be positive")
        return weight / (height**2)

    @staticmethod
    def category(value: float) -> str:
        if value < 18.5:
            return "Underweight"
        if value < 25:
            return "Normal weight"
        if value < 30:
            return "Overweight"
        return "Obesity"


bmi = BMI
Bmi = BMI


class Base(DeclarativeBase):
    pass


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    email: Mapped[str] = mapped_column(String(254), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(256))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )


class MeasurementRecord(Base):
    __tablename__ = "measurements"

    id: Mapped[str] = mapped_column(String(16), primary_key=True)
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True, index=True)
    date: Mapped[DateValue] = mapped_column(Date, nullable=False)
    name: Mapped[str] = mapped_column(String(100), nullable=False, default="Legacy User")
    gender: Mapped[str] = mapped_column(String(1), nullable=False, default="M")
    birth_year: Mapped[int] = mapped_column(Integer, nullable=False, default=2000)
    weight: Mapped[float] = mapped_column(Float, nullable=False)
    height: Mapped[float] = mapped_column(Float, nullable=False)
    note: Mapped[str] = mapped_column(String(120), nullable=False, default="")


class RegisterPayload(BaseModel):
    email: str = Field(max_length=254)
    password: str = Field(min_length=12, max_length=128)

    @field_validator("email")
    @classmethod
    def validate_email(cls, value: str) -> str:
        value = value.strip().lower()
        if not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", value):
            raise ValueError("Masukkan alamat email yang valid.")
        return value


class LoginPayload(BaseModel):
    email: str = Field(max_length=254)
    password: str = Field(min_length=1, max_length=128)

    @field_validator("email")
    @classmethod
    def normalize_email(cls, value: str) -> str:
        return value.strip().lower()


class MeasurementPayload(BaseModel):
    date: DateValue
    name: str = Field(min_length=6, max_length=100)
    gender: str
    birth_year: int = Field(ge=1900, le=2011)
    weight: int = Field(ge=0)
    height: int = Field(gt=0)
    note: str = Field(default="", max_length=120)

    @field_validator("name")
    @classmethod
    def validate_name(cls, value: str) -> str:
        value = value.strip()
        if (
            len(value) <= 5
            or not value.replace(" ", "").isalpha()
            or not value.istitle()
        ):
            raise ValueError(
                "Nama harus lebih dari 5 karakter, hanya berisi huruf, "
                "dan menggunakan format Title Case."
            )
        return value

    @field_validator("gender")
    @classmethod
    def validate_gender(cls, value: str) -> str:
        value = value.strip().upper()
        if value not in {"M", "L"}:
            raise ValueError("Gender harus M atau L.")
        return value


class Measurement(BaseModel):
    id: str
    date: DateValue
    name: str
    gender: str
    birth_year: int
    age: int
    weight: float
    height: float
    note: str
    bmi: float
    bmi_category: str


def initialize_database() -> None:
    Base.metadata.create_all(engine)
    if engine.dialect.name == "sqlite":
        with engine.begin() as connection:
            columns = {
                row[1] for row in connection.exec_driver_sql("PRAGMA table_info(measurements)")
            }
            migrations = {
                "name": "VARCHAR(100) NOT NULL DEFAULT 'Legacy User'",
                "gender": "VARCHAR(1) NOT NULL DEFAULT 'M'",
                "birth_year": "INTEGER NOT NULL DEFAULT 2000",
                "user_id": "INTEGER REFERENCES users(id)",
            }
            for column, definition in migrations.items():
                if column not in columns:
                    connection.exec_driver_sql(
                        f"ALTER TABLE measurements ADD COLUMN {column} {definition}"
                    )


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncGenerator[None, None]:
    initialize_database()
    yield


app = FastAPI(
    title="Raga API",
    description="Aplikasi catatan tubuh dengan akun pribadi.",
    lifespan=lifespan,
)
app.add_middleware(
    SessionMiddleware,
    secret_key=SESSION_SECRET,
    session_cookie="raga_session",
    max_age=60 * 60 * 24 * 7,
    same_site="lax",
    https_only=IS_DEPLOYED,
)


def get_db() -> Generator[Session, None, None]:
    with SessionFactory() as session:
        yield session


def get_current_user(
    request: Request, db: Session = Depends(get_db)
) -> User:
    user_id = request.session.get("user_id")
    if not isinstance(user_id, int):
        raise HTTPException(status_code=401, detail="Silakan masuk terlebih dahulu.")
    user = db.get(User, user_id)
    if user is None:
        request.session.clear()
        raise HTTPException(status_code=401, detail="Sesi tidak berlaku. Silakan masuk lagi.")
    return user


def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    digest = hashlib.scrypt(password.encode("utf-8"), salt=salt, n=2**14, r=8, p=1)
    return f"scrypt${salt.hex()}${digest.hex()}"


def verify_password(password: str, stored_hash: str) -> bool:
    try:
        algorithm, salt_hex, digest_hex = stored_hash.split("$", maxsplit=2)
        if algorithm != "scrypt":
            return False
        salt = bytes.fromhex(salt_hex)
        expected_digest = bytes.fromhex(digest_hex)
        actual_digest = hashlib.scrypt(
            password.encode("utf-8"), salt=salt, n=2**14, r=8, p=1
        )
        return hmac.compare_digest(actual_digest, expected_digest)
    except (ValueError, TypeError):
        return False


def serialize_measurement(record: MeasurementRecord) -> dict[str, object]:
    bmi_value = BMI.calculate(record.weight, record.height / 100)
    return {
        "id": record.id,
        "date": record.date,
        "name": record.name,
        "gender": record.gender,
        "birth_year": record.birth_year,
        "age": DateValue.today().year - record.birth_year,
        "weight": record.weight,
        "height": record.height,
        "note": record.note,
        "bmi": bmi_value,
        "bmi_category": BMI.category(bmi_value),
    }


def generate_measurement_id(db: Session) -> str:
    used_ids = set(db.scalars(select(MeasurementRecord.id)).all())
    available_ids = [
        f"BO{number}" for number in range(100, 1000) if f"BO{number}" not in used_ids
    ]
    if not available_ids:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Semua ID BO100 sampai BO999 sudah digunakan.",
        )
    return random.choice(available_ids)


@app.get("/", include_in_schema=False)
def home() -> FileResponse:
    return FileResponse(BASE_DIR / "web.html", media_type="text/html")


@app.get("/c.css", include_in_schema=False)
def stylesheet() -> FileResponse:
    return FileResponse(BASE_DIR / "c.css", media_type="text/css")


@app.get("/health", include_in_schema=False)
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/api/auth/register", status_code=status.HTTP_201_CREATED)
def register(
    payload: RegisterPayload,
    request: Request,
    db: Session = Depends(get_db),
) -> dict[str, str]:
    if db.scalar(select(User).where(User.email == payload.email)) is not None:
        raise HTTPException(status_code=409, detail="Email tersebut sudah terdaftar.")
    user = User(email=payload.email, password_hash=hash_password(payload.password))
    db.add(user)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="Email tersebut sudah terdaftar.")
    db.refresh(user)
    request.session.clear()
    request.session["user_id"] = user.id
    return {"email": user.email}


@app.post("/api/auth/login")
def login(
    payload: LoginPayload,
    request: Request,
    db: Session = Depends(get_db),
) -> dict[str, str]:
    user = db.scalar(select(User).where(User.email == payload.email))
    if user is None or not verify_password(payload.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Email atau kata sandi salah.")
    request.session.clear()
    request.session["user_id"] = user.id
    return {"email": user.email}


@app.get("/api/auth/me")
def current_account(user: User = Depends(get_current_user)) -> dict[str, str]:
    return {"email": user.email}


@app.post("/api/auth/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(request: Request) -> Response:
    request.session.clear()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@app.get("/api/measurements", response_model=list[Measurement])
def list_measurements(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[dict[str, object]]:
    rows = db.scalars(
        select(MeasurementRecord)
        .where(MeasurementRecord.user_id == user.id)
        .order_by(MeasurementRecord.date.desc(), MeasurementRecord.id)
    ).all()
    return [serialize_measurement(record) for record in rows]


@app.post(
    "/api/measurements",
    response_model=Measurement,
    status_code=status.HTTP_201_CREATED,
)
def create_measurement(
    payload: MeasurementPayload,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict[str, object]:
    record = MeasurementRecord(
        id=generate_measurement_id(db),
        user_id=user.id,
        **payload.model_dump(),
    )
    db.add(record)
    db.commit()
    db.refresh(record)
    return serialize_measurement(record)


@app.put("/api/measurements/{measurement_id}", response_model=Measurement)
def update_measurement(
    measurement_id: str,
    payload: MeasurementPayload,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict[str, object]:
    record = db.scalar(
        select(MeasurementRecord).where(
            MeasurementRecord.id == measurement_id,
            MeasurementRecord.user_id == user.id,
        )
    )
    if record is None:
        raise HTTPException(status_code=404, detail="Catatan tidak ditemukan.")
    for field, value in payload.model_dump().items():
        setattr(record, field, value)
    db.commit()
    db.refresh(record)
    return serialize_measurement(record)


@app.delete(
    "/api/measurements/{measurement_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def delete_measurement(
    measurement_id: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Response:
    record = db.scalar(
        select(MeasurementRecord).where(
            MeasurementRecord.id == measurement_id,
            MeasurementRecord.user_id == user.id,
        )
    )
    if record is None:
        raise HTTPException(status_code=404, detail="Catatan tidak ditemukan.")
    db.delete(record)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        app,
        host="0.0.0.0" if IS_DEPLOYED else "127.0.0.1",
        port=int(os.getenv("PORT", "8000")),
    )
