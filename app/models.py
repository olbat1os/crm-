from __future__ import annotations

from datetime import date, datetime, time
from typing import Optional, Dict, Any

from sqlmodel import SQLModel, Field
from sqlalchemy import Column, JSON


class Contact(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    created_at: datetime = Field(default_factory=datetime.utcnow, nullable=False)
    updated_at: datetime = Field(default_factory=datetime.utcnow, nullable=False)

    first_name: str
    last_name: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    birth_date: Optional[date] = None
    gender: Optional[str] = None
    city: Optional[str] = None

    instagram_handle: Optional[str] = None
    nickname: Optional[str] = None

    preferences: Optional[Dict[str, Any]] = Field(default=None, sa_column=Column(JSON))
    custom_fields: Optional[Dict[str, Any]] = Field(default=None, sa_column=Column(JSON))

    promoter_id: Optional[int] = Field(default=None, foreign_key="promoter.id")

    total_bookings: int = Field(default=0, nullable=False)
    total_spent_eur: float = Field(default=0.0, nullable=False)
    rating: Optional[int] = Field(default=None)


class Promoter(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    name: str
    phone: Optional[str] = None
    instagram_handle: Optional[str] = None


class BookingStatus:
    DOGOVORENO = "dogovoreno"
    POTVRDJENO = "potvrdjeno"
    OTKAZANO = "otkazano"
    WAITLIST = "waitlist"
    DOSAO = "dosao"


class Booking(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    created_at: datetime = Field(default_factory=datetime.utcnow, nullable=False)
    updated_at: datetime = Field(default_factory=datetime.utcnow, nullable=False)

    contact_id: int = Field(foreign_key="contact.id")
    date: date
    time_from: time

    table_type: Optional[str] = None  # VIP/Bar/Standard
    party_size: Optional[int] = None
    booking_source: Optional[str] = None  # WhatsApp, Instagram, Viber, Phone

    status: str = Field(default=BookingStatus.DOGOVORENO)
    spend_eur: Optional[float] = None
    special_case_note: Optional[str] = None
    comment: Optional[str] = None


class User(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    username: str
    password_hash: str
    avatar_path: Optional[str] = None
    club_name: Optional[str] = None
    working_days_json: Optional[Dict[str, Any]] = Field(default=None, sa_column=Column(JSON))
    working_hours_json: Optional[Dict[str, Any]] = Field(default=None, sa_column=Column(JSON))


