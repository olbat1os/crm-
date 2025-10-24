from __future__ import annotations

from datetime import date, datetime, time
from typing import Optional, Dict, Any
from enum import Enum

from sqlmodel import SQLModel, Field
from sqlalchemy import Column, JSON


class AdminRole(str, Enum):
    SUPER_ADMIN = "super_admin"
    ADMIN = "admin"


class BusinessStatus(str, Enum):
    PENDING = "pending"  # Ожидает активации
    ACTIVE = "active"    # Активен
    SUSPENDED = "suspended"  # Приостановлен
    EXPIRED = "expired"  # Истек срок


class Admin(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    created_at: datetime = Field(default_factory=datetime.utcnow, nullable=False)
    updated_at: datetime = Field(default_factory=datetime.utcnow, nullable=False)
    
    username: str = Field(unique=True, index=True)
    password_hash: str
    email: str = Field(unique=True, index=True)
    full_name: str
    role: AdminRole = Field(default=AdminRole.ADMIN)
    is_active: bool = Field(default=True)
    
    # Двухфакторная аутентификация
    two_factor_code: Optional[str] = None  # Временный код подтверждения
    two_factor_code_expires: Optional[datetime] = None  # Время истечения кода


class Business(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    created_at: datetime = Field(default_factory=datetime.utcnow, nullable=False)
    updated_at: datetime = Field(default_factory=datetime.utcnow, nullable=False)
    
    # Основная информация о бизнесе
    business_name: str
    contact_person: str
    email: str = Field(unique=True, index=True)
    phone: str
    address: Optional[str] = None
    city: Optional[str] = None
    country: Optional[str] = None
    
    # Настройки доступа
    status: BusinessStatus = Field(default=BusinessStatus.PENDING)
    password_hash: Optional[str] = None  # Хеш пароля для входа в систему
    access_start_date: Optional[datetime] = None
    access_end_date: Optional[datetime] = None
    trial_days: int = Field(default=7)  # Количество дней пробного периода
    
    # Дополнительная информация
    business_type: Optional[str] = None  # Тип бизнеса (ресторан, клуб, бар и т.д.)
    description: Optional[str] = None
    notes: Optional[str] = None  # Заметки админа
    
    # Связь с админом, который управляет этим бизнесом
    assigned_admin_id: Optional[int] = Field(default=None, foreign_key="admin.id")
    
    # Настройки бизнеса
    currency: Optional[str] = Field(default="EUR")  # Валюта (EUR, USD, RSD и т.д.)
    working_schedule: Optional[Dict[str, Any]] = Field(default=None, sa_column=Column(JSON))  # Расписание работы
    timezone: Optional[str] = Field(default="Europe/Belgrade")  # Часовой пояс


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
    
    # Связь с бизнесом
    business_id: int = Field(foreign_key="business.id")

    total_bookings: int = Field(default=0, nullable=False)
    total_spent_eur: float = Field(default=0.0, nullable=False)
    rating: Optional[int] = Field(default=None)


class Promoter(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    name: str
    phone: Optional[str] = None
    instagram_handle: Optional[str] = None
    # Связь с бизнесом
    business_id: int = Field(foreign_key="business.id")


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
    
    # Связь с бизнесом
    business_id: int = Field(foreign_key="business.id")


