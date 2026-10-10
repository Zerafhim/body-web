from contextlib import asynccontextmanager, contextmanager
from datetime import date
from pathlib import Path
import random
import sqlite3
from typing import AsyncGenerator, Generator

from fastapi import FastAPI, HTTPException, Response, status
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field, field_validator


BASE_DIR = Path(__file__).resolve().parent
DATABASE_PATH = BASE_DIR / "body_data.db"


class BMI:
    """Calculate and classify a body's BMI."""

    @staticmethod
    def calculate(weight: float, height: float) -> float:
        """Return BMI using weight in kilograms and height in meters."""
        if weight < 0:
            raise ValueError("weight must be non-negative")
        if height <= 0:
            raise ValueError("height must be positive")
        return weight / (height**2)

    @staticmethod
    def category(value: float) -> str:
        """Return the standard BMI category for a calculated value."""
        if value < 18.5:
            return "Underweight"
        if value < 25:
            return "Normal weight"
        if value < 30:
            return "Overweight"
        return "Obesity"


bmi = BMI
Bmi = BMI


class MeasurementPayload(BaseModel):
    date: date
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


class Measurement(MeasurementPayload):
    id: str
    age: int
    bmi: float
    bmi_category: str


@contextmanager
def database() -> Generator[sqlite3.Connection, None, None]:
    connection = sqlite3.connect(DATABASE_PATH)
    connection.row_factory = sqlite3.Row
    try:
        yield connection
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def initialize_database() -> None:
    with database() as connection:
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS measurements (
                id TEXT PRIMARY KEY,
                date TEXT NOT NULL,
                weight REAL NOT NULL,
                height REAL NOT NULL,
                note TEXT NOT NULL DEFAULT '',
                name TEXT NOT NULL DEFAULT 'Legacy User',
                gender TEXT NOT NULL DEFAULT 'M',
                birth_year INTEGER NOT NULL DEFAULT 2000
            )
            """
        )
        existing_columns = {
            row["name"]
            for row in connection.execute("PRAGMA table_info(measurements)")
        }
        for column, definition in (
            ("name", "TEXT NOT NULL DEFAULT 'Legacy User'"),
            ("gender", "TEXT NOT NULL DEFAULT 'M'"),
            ("birth_year", "INTEGER NOT NULL DEFAULT 2000"),
        ):
            if column not in existing_columns:
                connection.execute(
                    f"ALTER TABLE measurements ADD COLUMN {column} {definition}"
                )


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncGenerator[None, None]:
    initialize_database()
    yield


app = FastAPI(
    title="Raga API",
    description="API catatan pengukuran tubuh.",
    lifespan=lifespan,
)


@app.get("/", include_in_schema=False)
def home() -> FileResponse:
    return FileResponse(BASE_DIR / "web.html", media_type="text/html")


@app.get("/c.css", include_in_schema=False)
def stylesheet() -> FileResponse:
    return FileResponse(BASE_DIR / "c.css", media_type="text/css")


@app.get("/api/measurements", response_model=list[Measurement])
def list_measurements() -> list[dict[str, object]]:
    with database() as connection:
        rows = connection.execute(
            """
            SELECT id, date, name, gender, birth_year, weight, height, note
            FROM measurements
            ORDER BY date DESC, rowid DESC
            """
        ).fetchall()

    return [
        {
            "id": row["id"],
            "date": row["date"],
            "name": row["name"],
            "gender": row["gender"],
            "birth_year": row["birth_year"],
            "age": date.today().year - row["birth_year"],
            "weight": row["weight"],
            "height": row["height"],
            "note": row["note"],
            "bmi": BMI.calculate(row["weight"], row["height"] / 100),
            "bmi_category": BMI.category(
                BMI.calculate(row["weight"], row["height"] / 100)
            ),
        }
        for row in rows
    ]


def generate_measurement_id(connection: sqlite3.Connection) -> str:
    used_ids = {
        row["id"] for row in connection.execute("SELECT id FROM measurements")
    }
    available_ids = [
        f"BO{number}" for number in range(100, 1000) if f"BO{number}" not in used_ids
    ]
    if not available_ids:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Semua ID BO100 sampai BO999 sudah digunakan.",
        )
    return random.choice(available_ids)


@app.post(
    "/api/measurements",
    response_model=Measurement,
    status_code=status.HTTP_201_CREATED,
)
def create_measurement(payload: MeasurementPayload) -> dict[str, object]:
    with database() as connection:
        measurement_id = generate_measurement_id(connection)
        connection.execute(
            """
            INSERT INTO measurements
                (id, date, name, gender, birth_year, weight, height, note)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                measurement_id,
                payload.date.isoformat(),
                payload.name,
                payload.gender,
                payload.birth_year,
                payload.weight,
                payload.height,
                payload.note,
            ),
        )

    return {
        "id": measurement_id,
        **payload.model_dump(),
        "age": date.today().year - payload.birth_year,
        "bmi": BMI.calculate(payload.weight, payload.height / 100),
        "bmi_category": BMI.category(
            BMI.calculate(payload.weight, payload.height / 100)
        ),
    }


@app.put("/api/measurements/{measurement_id}", response_model=Measurement)
def update_measurement(
    measurement_id: str, payload: MeasurementPayload
) -> dict[str, object]:
    with database() as connection:
        result = connection.execute(
            """
            UPDATE measurements
            SET date = ?, name = ?, gender = ?, birth_year = ?,
                weight = ?, height = ?, note = ?
            WHERE id = ?
            """,
            (
                payload.date.isoformat(),
                payload.name,
                payload.gender,
                payload.birth_year,
                payload.weight,
                payload.height,
                payload.note,
                measurement_id,
            ),
        )
        if result.rowcount == 0:
            raise HTTPException(status_code=404, detail="Catatan tidak ditemukan.")

    return {
        "id": measurement_id,
        **payload.model_dump(),
        "age": date.today().year - payload.birth_year,
        "bmi": BMI.calculate(payload.weight, payload.height / 100),
        "bmi_category": BMI.category(
            BMI.calculate(payload.weight, payload.height / 100)
        ),
    }


@app.delete(
    "/api/measurements/{measurement_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def delete_measurement(measurement_id: str) -> Response:
    with database() as connection:
        result = connection.execute(
            "DELETE FROM measurements WHERE id = ?", (measurement_id,)
        )
        if result.rowcount == 0:
            raise HTTPException(status_code=404, detail="Catatan tidak ditemukan.")
    return Response(status_code=status.HTTP_204_NO_CONTENT)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="127.0.0.1", port=8000)
