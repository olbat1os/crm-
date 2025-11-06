from fastapi import FastAPI, Request, Depends, Form, BackgroundTasks, Query, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from sqlmodel import Session, select
from typing import Optional
from datetime import timedelta
from app.db import get_session, create_db_and_tables
from app.models import Business, Admin, AdminRole, BusinessStatus
from app.config import settings
from app.auth import authenticate_admin, require_admin, require_super_admin, get_all_businesses, get_pending_businesses, reset_business_password as auth_reset_business_password, set_business_password, activate_business, activate_business_with_minutes, get_current_admin, send_password_email, check_and_freeze_expired_businesses, unfreeze_business, send_unfreeze_notification, suspend_business, send_suspend_notification
from app.models import Contact, Promoter, User, Booking
from datetime import datetime
from datetime import datetime as _datetime
from datetime import date as _date
from datetime import time as _time
import asyncio

app = FastAPI()

# Подключаем статические файлы
app.mount("/static", StaticFiles(directory="static"), name="static")

# Настраиваем шаблоны
templates = Jinja2Templates(directory="templates")

# Middleware для сессий
from starlette.middleware.sessions import SessionMiddleware
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response
import time

class AdminSessionMiddleware(BaseHTTPMiddleware):
    """Middleware для продления сессии админов"""
    
    async def dispatch(self, request, call_next):
        response = await call_next(request)
        
        # Проверяем, является ли пользователь админом
        admin = request.session.get("admin")
        if admin:
            # Устанавливаем специальные заголовки для продления сессии админа
            response.set_cookie(
                key=settings.session_cookie_name,
                value=request.session.get("_session", ""),
                max_age=settings.admin_session_max_age,  # 12 часов для админов
                httponly=True,
                secure=False,  # Для HTTP
                samesite="lax"
            )
        
        return response

app.add_middleware(
    SessionMiddleware, 
    secret_key=settings.secret_key,
    max_age=settings.session_max_age,  # 0 = безгранично для обычных пользователей
    same_site="lax"
)

# Добавляем middleware для продления админских сессий
app.add_middleware(AdminSessionMiddleware)

# Фоновая задача для проверки истечения сроков
async def check_expired_businesses_task():
    """Фоновая задача для проверки истечения сроков доступа"""
    while True:
        session = None
        try:
            # Получаем сессию базы данных
            session = next(get_session())
            
            # Проверяем и замораживаем истекшие бизнесы
            frozen_count = check_and_freeze_expired_businesses(session)
            
            if frozen_count > 0:
                print(f"🔄 Pozadinska provera: zamrznuto {frozen_count} biznisa")
            else:
                print("🔄 Pozadinska provera: nema isteklih rokova")
                
        except Exception as e:
            print(f"❌ Ошибка в фоновой задаче проверки сроков: {str(e)}")
        finally:
            # ВАЖНО: Закрываем сессию базы данных
            if session:
                try:
                    session.close()
                except Exception as e:
                    print(f"❌ Ошибка при закрытии сессии: {e}")
        
        # Ждем 5 минут перед следующей проверкой (для тестирования)
        # Для продакшена изменить на 3600 (1 час) или 1800 (30 минут)
        await asyncio.sleep(300)  # 5 минут = 300 секунд

# Запускаем фоновую задачу при старте приложения
@app.on_event("startup")
async def startup_event():
    """Запуск фоновых задач при старте приложения"""
    print("🚀 Pokretanje sistema provere isteka rokova...")
    asyncio.create_task(check_expired_businesses_task())
    print("✅ Sistem provere isteka rokova je pokrenut")
    create_db_and_tables()

def get_current_user(request: Request):
    user = request.session.get("user")
    if not user:
        print(f"❌ No user in session. Session keys: {list(request.session.keys())}")
    else:
        print(f"✅ User found: {user}")
    return user

def extend_admin_session(request: Request):
    """Продлевает сессию админа при активности"""
    admin = request.session.get("admin")
    if admin:
        # Обновляем время последней активности
        admin["last_activity"] = time.time()
        request.session["admin"] = admin
        print(f"🔄 Сессия админа {admin.get('username', 'unknown')} продлена")

def admin_activity_required(func):
    """Декоратор для продления сессии админа при активности"""
    async def wrapper(*args, **kwargs):
        # Находим request среди аргументов
        request = None
        for arg in args:
            if hasattr(arg, 'session'):
                request = arg
                break
        
        if request:
            extend_admin_session(request)
        
        return await func(*args, **kwargs)
    return wrapper

def check_business_active(request: Request, session: Session):
    """Проверяет, активен ли бизнес пользователя и не истек ли срок"""
    user = get_current_user(request)
    if not user:
        return None, None
    
    business_id = user.get("business_id")
    if business_id is None:
        # Для статических пользователей создаем фиктивный бизнес объект
        class StaticBusiness:
            id = None
            status = "ACTIVE"
            name = "Static User"
        return StaticBusiness(), None
    
    # Получаем бизнес из базы
    business = session.get(Business, business_id)
    if not business:
        return None, "Business not found"
    
    # Проверяем статус
    if business.status == BusinessStatus.EXPIRED:
        # Автоматически выходим из системы
        request.session.clear()
        return None, "Vaš probni period je istekao. Kontaktirajte administratora za produženje."
    
    if business.status == BusinessStatus.SUSPENDED:
        # Автоматически выходим из системы
        request.session.clear()
        return None, "Vaš nalog je privremeno suspendovan. Kontaktirajte administratora."
    
    if business.status != BusinessStatus.ACTIVE:
        # Автоматически выходим из системы
        request.session.clear()
        return None, "Vaš nalog nije aktivan. Kontaktirajte administratora."
    
    # Проверяем срок действия
    from datetime import datetime
    if business.access_end_date and business.access_end_date < datetime.utcnow():
        # Срок истёк, но разрешаем вход (только просмотр)
        # Заморозка происходит только через фоновую задачу
        pass
    
    return business, None

def check_subscription_expired(business_id: int, session: Session) -> bool:
    """Проверяет, истек ли срок подписки у бизнеса"""
    from datetime import datetime
    business = session.get(Business, business_id)
    if not business:
        return True
    
    if business.access_end_date and business.access_end_date < datetime.utcnow():
        return True
    
    return False

def check_subscription_in_api(request: Request, session: Session) -> Optional[JSONResponse]:
    """Проверяет подписку в API эндпоинтах (только для авторизованных пользователей)"""
    user = get_current_user(request)
    if not user:
        # Не авторизован - это нормально, пусть основная функция обработает
        return None
    
    business_id = user.get("business_id")
    if not business_id:
        return JSONResponse({"success": False, "message": "No business ID"}, status_code=400)
    
    # Проверяем, не истек ли срок подписки
    if check_subscription_expired(business_id, session):
        return JSONResponse({
            "success": False, 
            "message": "Vaš probni period je istekao. Kontaktirajte administratora za produženje pristupa.",
            "expired": True
        }, status_code=403)
    
    return None

def extract_google_maps_data(url: str) -> dict:
    """
    Извлекает данные из разных форматов Google Maps URL:
    - Embed URL (iframe src)
    - Короткие ссылки (maps.app.goo.gl)
    - Стандартные ссылки (maps.google.com)
    - Прямые координаты (lat, lng)
    
    Возвращает словарь с координатами, place_id, и другими данными
    """
    import re
    from urllib.parse import urlparse, parse_qs, unquote
    
    result = {
        "coordinates": None,  # (lat, lng)
        "place_id": None,  # Стандартный place_id
        "cid": None,  # CID формат
        "name": None,
        "standard_url": None
    }
    
    if not url:
        return result
    
    try:
        # Проверяем, является ли ввод просто координатами (формат: "lat, lng" или "lat,lng")
        coord_pattern = r'^\s*(-?\d+\.?\d*)\s*[,;]\s*(-?\d+\.?\d*)\s*$'
        coord_match = re.match(coord_pattern, url.strip())
        if coord_match:
            try:
                lat = float(coord_match.group(1))
                lng = float(coord_match.group(2))
                # Проверяем диапазон координат (широта: -90 до 90, долгота: -180 до 180)
                if -90 <= lat <= 90 and -180 <= lng <= 180:
                    result["coordinates"] = (lat, lng)
                    # Создаем стандартный Google Maps URL из координат
                    result["standard_url"] = f"https://www.google.com/maps?q={lat},{lng}"
                    return result
            except ValueError:
                pass  # Не координаты, продолжаем обработку как URL
        # 1. Обработка embed URL (iframe src)
        if "embed" in url or "pb=" in url:
            # Извлекаем координаты из параметра pb
            # Формат: !2d47.28788607735273!3d56.10066097321502 (долгота, широта)
            coord_match = re.search(r'!2d([0-9.]+)!3d([0-9.]+)', url)
            if coord_match:
                lng = float(coord_match.group(1))
                lat = float(coord_match.group(2))
                result["coordinates"] = (lat, lng)
            
            # Извлекаем Place ID в формате CID из параметра !1s
            # Формат: !1s0x415a37bd27554955%3A0x253203abb4f42699
            place_match = re.search(r'!1s([^!]+)', url)
            if place_match:
                place_data = unquote(place_match.group(1))
                # Формат может быть 0x415a37bd27554955:0x253203abb4f42699
                if ':' in place_data:
                    result["cid"] = place_data
                    # Преобразуем CID в стандартный URL
                    result["standard_url"] = f"https://www.google.com/maps/place/?cid={place_data}"
            
            # Извлекаем название места из параметра !2z
            name_match = re.search(r'!2z([^!]+)', url)
            if name_match:
                result["name"] = unquote(name_match.group(1))
        
        # 2. Обработка коротких ссылок (maps.app.goo.gl)
        elif "goo.gl" in url or "maps.app.goo.gl" in url:
            # Для коротких ссылок нужно развернуть их, но мы можем вернуть оригинальный URL
            result["standard_url"] = url
        
        # 3. Обработка стандартных ссылок maps.google.com
        elif "maps.google.com" in url:
            parsed = urlparse(url)
            params = parse_qs(parsed.query)
            
            # Проверяем параметр cid
            if "cid" in params:
                result["cid"] = params["cid"][0]
                result["standard_url"] = url
            
            # Проверяем параметр place_id
            if "place_id" in params:
                result["place_id"] = params["place_id"][0]
                result["standard_url"] = url
            
            # Извлекаем координаты из пути или параметров
            coord_match = re.search(r'@(-?\d+\.\d+),(-?\d+\.\d+)', url)
            if coord_match:
                lat = float(coord_match.group(2))
                lng = float(coord_match.group(1))
                result["coordinates"] = (lat, lng)
        
        # Если не удалось определить формат, просто сохраняем URL как стандартный
        if not result["standard_url"]:
            result["standard_url"] = url
            
    except Exception as e:
        print(f"Ошибка при обработке Google Maps URL: {e}")
    
    return result

def get_client_stats(session: Session, business_id: int):
    """Получает статистику клиентов для поиска"""
    contacts = session.exec(select(Contact).where(Contact.business_id == business_id).order_by(Contact.created_at.desc())).all()
    if not contacts:
        return [], {}
    
    contact_ids = [c.id for c in contacts]
    all_bookings = session.exec(select(Booking).where(Booking.contact_id.in_(contact_ids))).all()
    
    bookings_by_contact = {}
    for b in all_bookings:
        bookings_by_contact.setdefault(b.contact_id, []).append(b)
    
    month_names = {
        1: "Januar", 2: "Februar", 3: "Mart", 4: "April", 5: "Maj", 6: "Jun",
        7: "Jul", 8: "Avgust", 9: "Septembar", 10: "Oktobar", 11: "Novembar", 12: "Decembar"
    }
    
    client_stats = {}
    for c in contacts:
        lst = bookings_by_contact.get(c.id, [])
        last_visit = None
        last_booking_status = None
        visits_confirmed = 0
        spends = []
        
        for b in lst:
            if last_visit is None or (b.date, b.time_from) > (last_visit[0], last_visit[1] if last_visit[1] else b.time_from):
                last_visit = (b.date, b.time_from)
                last_booking_status = b.status
            # Считаем только успешные завершения (dosao или dosli)
            if b.status in ("dosao", "dosli"):
                visits_confirmed += 1
                # Используем final_check_rsd для расчета средней траты
                if b.final_check_rsd is not None:
                    spends.append(b.final_check_rsd)
        
        avg_spend = (sum(spends) / len(spends)) if spends else None
        last_visit_str = None
        if last_visit is not None:
            d, t = last_visit
            month_name = month_names.get(d.month, str(d.month))
            last_visit_str = f"{d.day}. {month_name} {d.year} | {t.strftime('%H:%M')}"
        
        client_stats[c.id] = {
            "last_visit": last_visit[0].isoformat() if last_visit else None,
            "last_visit_str": last_visit_str,
            "last_booking_status": last_booking_status,
            "visits_confirmed": visits_confirmed,
            "avg_spend": avg_spend,
        }
    
    return contacts, client_stats

@app.get("/", response_class=HTMLResponse)
async def landing_page(request: Request):
    return templates.TemplateResponse("landing.html", {"request": request, "title": "LovaCRM"})

@app.get("/login", response_class=HTMLResponse)
async def login_page(request: Request):
    return templates.TemplateResponse("login.html", {"request": request, "title": "Login"})

@app.post("/login")
async def login(request: Request, username: str = Form(...), password: str = Form(...), session: Session = Depends(get_session)):
    # Проверяем статические учетные данные
    if username == settings.single_username and password == settings.single_password:
        request.session["user"] = {"username": username, "business_id": None}
        return RedirectResponse(url="/dashboard", status_code=302)
    
    # Проверяем бизнесы в базе данных
    from app.auth import hash_password
    password_hash = hash_password(password)
    
    # Ищем бизнес по email
    business = session.exec(select(Business).where(Business.email == username)).first()
    if business and business.password_hash and business.password_hash == password_hash:
        # Проверяем статус бизнеса
        if business.status == BusinessStatus.ACTIVE:
            # Разрешаем вход (даже если срок истек - только просмотр)
            request.session["user"] = {"username": username, "business_id": business.id}
            return RedirectResponse(url="/dashboard", status_code=302)
        elif business.status == BusinessStatus.EXPIRED:
            # Замороженные аккаунты не могут входить
            return templates.TemplateResponse("login.html", {
                "request": request, 
                "title": "Login", 
                "error": "Rok pristupa je istekao. Nalog je zamrznut. Obratite se administratoru za produženje."
            }, status_code=400)
        else:
            # Другие статусы (PENDING, SUSPENDED) не могут входить
            return templates.TemplateResponse("login.html", {
                "request": request, 
                "title": "Login", 
                "error": "Account is not active. Please contact administrator."
            }, status_code=400)
    
    return templates.TemplateResponse("login.html", {"request": request, "title": "Login", "error": "Invalid credentials"}, status_code=400)

@app.get("/dashboard", response_class=HTMLResponse)
async def dashboard(request: Request, period: Optional[str] = Query("current_month"), session: Session = Depends(get_session)):
    """Страница дашборда с метриками"""
    try:
        user = get_current_user(request)
        if not user:
            return RedirectResponse(url="/login", status_code=302)
        
        # Проверяем активность бизнеса
        business, error = check_business_active(request, session)
        if error:
            return templates.TemplateResponse("login.html", {
                "request": request,
                "title": "Login",
                "error": error
            }, status_code=400)
        
        business_id = user.get("business_id")
        if not business_id:
            # Для статических пользователей возвращаем пустой дашборд
            return templates.TemplateResponse("dashboard.html", {
                "request": request,
                "title": "CRM",
                "user": user,
                "contacts": [],
                "client_stats": {},
                "has_data": False,
                "total_contacts": 0,
                "avg_spend": 0,
                "guests_with_bookings": 0,
                "google_rating": None,
                "attendance_rate": 0,
                "new_clients_percent": 0,
                "regular_clients_percent": 0,
                "retention": 0,
                "marketing_data": {"instagram": 0, "promoter": 0, "random": 0, "whatsapp": 0, "calls": 0, "email": 0},
                "total_spend": 0,
                "occupancy_data": {},
                "occupancy_labels": [],
                "occupancy_type": "months",
                "period": period,
                "dashboard_config": {},
                "avg_spend_trend": None,
                "attendance_trend": None,
                "has_google_rating_data": False,
                "has_attendance_data": False,
                "has_retention_data": False,
                "has_marketing_data": False,
                "has_occupancy_data": False,
                "has_novi_stalni_data": False
            })
        
        # Получаем бизнес из базы
        business = session.get(Business, business_id)
        if not business:
            return RedirectResponse(url="/login", status_code=302)
        
        # Определяем период для фильтрации
        now = datetime.utcnow()
        if period == "current_month":
            start_date = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
            end_date = now
        elif period == "previous_month":
            start_date = (now.replace(day=1) - timedelta(days=1)).replace(day=1, hour=0, minute=0, second=0, microsecond=0)
            end_date = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0) - timedelta(seconds=1)
        elif period == "year":
            start_date = now.replace(month=1, day=1, hour=0, minute=0, second=0, microsecond=0)
            end_date = now
        else:  # all_time
            start_date = None
            end_date = None
        
        # Получаем контакты и бронирования для бизнеса
        contacts_query = select(Contact).where(Contact.business_id == business.id)
        contacts = session.exec(contacts_query).all()
        
        bookings_query = select(Booking).where(Booking.contact_id.in_([c.id for c in contacts]))
        if start_date:
            bookings_query = bookings_query.where(Booking.date >= start_date.date())
        if end_date:
            bookings_query = bookings_query.where(Booking.date <= end_date.date())
        bookings = session.exec(bookings_query).all()
        
        # Используем правильный статус для успешных резерваций (dosao или dosli)
        confirmed_bookings = [b for b in bookings if b.status in ("dosao", "dosli")]
        
        # Рассчитываем метрики
        # Средний чек (используем final_check_rsd для успешных завершений)
        total_spend = sum(b.final_check_rsd or 0 for b in confirmed_bookings)
        avg_spend = total_spend / len(confirmed_bookings) if confirmed_bookings else 0
        
        # Количество гостей (сумма party_size)
        guests_count = sum(b.party_size or 0 for b in confirmed_bookings)
        
        # Google Maps рейтинг
        google_rating_value = business.google_rating
        if not google_rating_value and business.google_rating_history:
            history_keys = list(business.google_rating_history.keys())
            if history_keys:
                google_rating_value = business.google_rating_history.get(history_keys[-1])
        
        # Общая потраченная сумма (в RSD, из final_check_rsd)
        total_spend_value = total_spend
        
        # Доходимость (процент успешных резерваций - dosao/dosli от всех бронирований)
        attendance_rate = (len(confirmed_bookings) / len(bookings) * 100) if bookings else 0
        
        # Новые / Постоянные гости
        new_clients = [c for c in contacts if c.preferences and "Novi" in c.preferences.get("tags", [])]
        regular_clients = [c for c in contacts if c.preferences and "Stalni gost" in c.preferences.get("tags", [])]
        new_clients_count = len(new_clients)
        regular_clients_count = len(regular_clients)
        total_tagged = new_clients_count + regular_clients_count
        new_clients_percent = (new_clients_count / total_tagged * 100) if total_tagged > 0 else 0
        regular_clients_percent = (regular_clients_count / total_tagged * 100) if total_tagged > 0 else 0
        
        # Retention (количество бронирований / количество контактов с хотя бы одной успешной бронью)
        contacts_with_bookings = set(b.contact_id for b in confirmed_bookings)
        retention_value = (len(bookings) / len(contacts_with_bookings)) if contacts_with_bookings else 0
        
        # Marketing source
        marketing_data = {}
        source_counts = {}
        for booking in bookings:
            contact = next((c for c in contacts if c.id == booking.contact_id), None)
            if contact:
                source = contact.preferences.get("communication_method", "random") if contact.preferences else "random"
                # Классификация источников
                if source.lower() in ["instagram", "инстаграм"]:
                    source = "instagram"
                elif source.lower() in ["telefon", "phone", "calls"]:
                    source = "calls"
                elif source.lower() in ["wa", "whatsapp", "whats app"]:
                    source = "whatsapp"
                elif source.lower() in ["email", "e-mail"]:
                    source = "email"
                elif contact.promoter_id or (contact.preferences and contact.preferences.get("promoter_name")):
                    source = "promoter"
                else:
                    source = "random"
                source_counts[source] = source_counts.get(source, 0) + 1
        
        total_bookings_for_marketing = sum(source_counts.values())
        for source, count in source_counts.items():
            marketing_data[source] = {
                "count": count,
                "percentage": (count / total_bookings_for_marketing * 100) if total_bookings_for_marketing > 0 else 0
            }
        
        # Тренды (сравнение с предыдущим периодом)
        # Для "all_time" и "year" не показываем тренды
        if period == "all_time":
            avg_spend_trend = None
            attendance_trend = None
        elif period == "year":
            # Для года сравниваем с предыдущим годом
            prev_year_start = now.replace(year=now.year - 1, month=1, day=1, hour=0, minute=0, second=0, microsecond=0)
            prev_year_end = now.replace(year=now.year - 1, month=12, day=31, hour=23, minute=59, second=59, microsecond=0)
            contact_ids = [c.id for c in contacts]
            if contact_ids:
                prev_year_all = session.exec(
                    select(Booking).where(
                        Booking.contact_id.in_(contact_ids),
                        Booking.date >= prev_year_start.date(),
                        Booking.date <= prev_year_end.date()
                    )
                ).all()
                prev_year_bookings = [b for b in prev_year_all if b.status in ("dosao", "dosli")]
            else:
                prev_year_bookings = []
            
            # Если нет данных за предыдущий год, не показываем тренды
            if not prev_year_bookings:
                avg_spend_trend = None
                attendance_trend = None
            else:
                prev_year_spend = sum(b.final_check_rsd or 0 for b in prev_year_bookings)
                prev_year_avg_spend = prev_year_spend / len(prev_year_bookings) if prev_year_bookings else 0
                avg_spend_trend = "up" if avg_spend > prev_year_avg_spend else "down" if avg_spend < prev_year_avg_spend else None
                
                prev_year_all_bookings = session.exec(
                    select(Booking).where(
                        Booking.contact_id.in_([c.id for c in contacts]),
                        Booking.date >= prev_year_start.date(),
                        Booking.date <= prev_year_end.date()
                    )
                ).all()
                prev_year_attendance = (len(prev_year_bookings) / len(prev_year_all_bookings) * 100) if prev_year_bookings and prev_year_all_bookings else 0
                attendance_trend = "up" if attendance_rate > prev_year_attendance else "down" if attendance_rate < prev_year_attendance else None
        else:
            # Для текущего и предыдущего месяца - сравниваем с предыдущим месяцем
            prev_month_start = (now.replace(day=1) - timedelta(days=1)).replace(day=1, hour=0, minute=0, second=0, microsecond=0)
            prev_month_end = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0) - timedelta(seconds=1)
            # Получаем успешные резервации за предыдущий месяц (dosao/dosli)
            contact_ids = [c.id for c in contacts]
            if contact_ids:
                prev_month_all = session.exec(
                    select(Booking).where(
                        Booking.contact_id.in_(contact_ids),
                        Booking.date >= prev_month_start.date(),
                        Booking.date <= prev_month_end.date()
                    )
                ).all()
                prev_month_bookings = [b for b in prev_month_all if b.status in ("dosao", "dosli")]
            else:
                prev_month_bookings = []
            prev_month_spend = sum(b.final_check_rsd or 0 for b in prev_month_bookings)
            prev_month_avg_spend = prev_month_spend / len(prev_month_bookings) if prev_month_bookings else 0
            avg_spend_trend = "up" if avg_spend > prev_month_avg_spend else "down" if avg_spend < prev_month_avg_spend else None
            
            prev_month_all_bookings = session.exec(
                select(Booking).where(
                    Booking.contact_id.in_([c.id for c in contacts]),
                    Booking.date >= prev_month_start.date(),
                    Booking.date <= prev_month_end.date()
                )
            ).all()
            prev_month_attendance = (len(prev_month_bookings) / len(prev_month_all_bookings) * 100) if prev_month_bookings and prev_month_all_bookings else 0
            attendance_trend = "up" if attendance_rate > prev_month_attendance else "down" if attendance_rate < prev_month_attendance else None
        
        # Проверка наличия данных для каждой метрики
        has_data = {
            "avg_spend": avg_spend > 0,
            "guests_count": guests_count > 0,
            "google_rating": google_rating_value is not None,
            "total_spend": total_spend_value > 0,
            "attendance": attendance_rate > 0,
            "new_regular": total_tagged > 0,
            "retention": retention_value > 0,
            "marketing": total_bookings_for_marketing > 0
        }
        
        dashboard_config = business.dashboard_config or {}
        
        # Получаем статистику клиентов
        contacts, client_stats = get_client_stats(session, business_id)
        
        # Форматируем marketing_data для шаблона
        marketing_data_formatted = {
            "instagram": marketing_data.get("instagram", {}).get("percentage", 0),
            "whatsapp": marketing_data.get("whatsapp", {}).get("percentage", 0),
            "calls": marketing_data.get("calls", {}).get("percentage", 0),
            "email": marketing_data.get("email", {}).get("percentage", 0),
            "promoter": marketing_data.get("promoter", {}).get("percentage", 0),
            "random": marketing_data.get("random", {}).get("percentage", 0)
        }
        
        # Рассчитываем заполняемость (occupancy) в зависимости от периода
        from collections import defaultdict
        from calendar import month_abbr
        
        occupancy_data = {}
        occupancy_labels = []
        occupancy_type = "months"  # "weeks", "months" или "years"
        
        if period in ("current_month", "previous_month"):
            # Для текущего/прошлого месяца - по неделям (4 недели)
            occupancy_type = "weeks"
            target_month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
            if period == "previous_month":
                target_month_start = (now.replace(day=1) - timedelta(days=1)).replace(day=1, hour=0, minute=0, second=0, microsecond=0)
            
            # Определяем последний день месяца
            if target_month_start.month == 12:
                next_month = target_month_start.replace(year=target_month_start.year + 1, month=1)
            else:
                next_month = target_month_start.replace(month=target_month_start.month + 1)
            month_end = (next_month - timedelta(days=1)).date()
            month_start_date = target_month_start.date()
            
            # Разбиваем на 4 недели
            weeks_bookings = defaultdict(int)
            total_days = (month_end - month_start_date).days + 1
            days_per_week = total_days / 4
            
            for week_num in range(1, 5):
                week_start = month_start_date + timedelta(days=int((week_num - 1) * days_per_week))
                if week_num == 4:
                    week_end = month_end
                else:
                    week_end = month_start_date + timedelta(days=int(week_num * days_per_week) - 1)
                
                # Считаем успешные резервации за эту неделю (dosao/dosli)
                week_bookings = [b for b in confirmed_bookings 
                                if week_start <= b.date <= week_end]
                weeks_bookings[f"week_{week_num}"] = len(week_bookings)
                # Названия недель на сербском
                week_names = {1: "Prva", 2: "Druga", 3: "Treća", 4: "Četvrta"}
                occupancy_labels.append(f"{week_names[week_num]} nedelja")
            
            occupancy_data = weeks_bookings
            
        elif period == "year":
            # За год - по месяцам (12 месяцев, начиная с января текущего года)
            occupancy_type = "months"
            months_bookings = defaultdict(int)
            
            current_month = now.month
            current_year = now.year
            
            # Год начинается с января текущего года
            # Создаем список всех 12 месяцев от января текущего года
            for month_num in range(1, 13):
                target_month = month_num
                target_year = current_year
                
                month_start = datetime(target_year, target_month, 1).date()
                if target_month == 12:
                    month_end = datetime(target_year + 1, 1, 1).date() - timedelta(days=1)
                else:
                    month_end = datetime(target_year, target_month + 1, 1).date() - timedelta(days=1)
                
                # Если это текущий месяц, ограничиваем до сегодняшней даты
                if target_month == current_month and target_year == current_year:
                    month_end = min(month_end, now.date())
                
                # Считаем успешные резервации за этот месяц (dosao/dosli)
                month_bookings = [b for b in confirmed_bookings 
                                 if month_start <= b.date <= month_end]
                month_key = f"{target_year}_{target_month:02d}"
                months_bookings[month_key] = len(month_bookings)
                
                # Метка месяца (короткое название)
                month_name = month_abbr[target_month]
                occupancy_labels.append(month_name)
            
            occupancy_data = months_bookings
            
        else:  # all_time - только 2025 и 2026 год
            occupancy_type = "years"
            years_bookings = defaultdict(int)
            
            current_year = now.year
            # Показываем только 2025 и 2026 год
            target_years = [2025, 2026]
            
            for target_year in target_years:
                year_start = datetime(target_year, 1, 1).date()
                year_end = datetime(target_year, 12, 31).date()
                
                # Если это текущий год, ограничиваем до сегодняшней даты
                if target_year == current_year:
                    year_end = now.date()
                
                # Считаем успешные резервации за этот год (dosao/dosli)
                year_bookings = [b for b in confirmed_bookings 
                                if year_start <= b.date <= year_end]
                year_key = str(target_year)
                years_bookings[year_key] = len(year_bookings)
                
                # Метка года (полный год, например 2025, 2026)
                year_label = str(target_year)
                occupancy_labels.append(year_label)  # Добавляем в порядке 2025, 2026
            
            occupancy_data = years_bookings
        
        return templates.TemplateResponse("dashboard.html", {
            "request": request,
            "title": "CRM",
            "user": user,
            "contacts": contacts,
            "client_stats": client_stats,
            "has_data": bool(contacts),
            "total_contacts": len(contacts),
            "avg_spend": round(avg_spend, 2),
            "guests_with_bookings": guests_count,
            "google_rating": round(google_rating_value, 1) if google_rating_value else None,
            "attendance_rate": round(attendance_rate, 1),
            "new_clients_percent": round(new_clients_percent, 1),
            "regular_clients_percent": round(regular_clients_percent, 1),
            "retention": round(retention_value, 2),
            "marketing_data": marketing_data_formatted,
            "total_spend": round(total_spend_value, 2),
            "occupancy_data": occupancy_data,
            "occupancy_labels": occupancy_labels,
            "occupancy_type": occupancy_type,
            "period": period,
            "current_period": period,
            "dashboard_config": dashboard_config,
            "avg_spend_trend": avg_spend_trend,
            "attendance_trend": attendance_trend,
            "has_google_rating_data": has_data.get("google_rating", False),
            "has_attendance_data": has_data.get("attendance", False),
            "has_retention_data": has_data.get("retention", False),
            "has_marketing_data": has_data.get("marketing", False),
            "has_occupancy_data": len(occupancy_data) > 0 and sum(occupancy_data.values()) > 0,
            "has_novi_stalni_data": has_data.get("new_regular", False),
            "has_avg_spend_data": has_data.get("avg_spend", False),
            "has_total_spend_data": has_data.get("total_spend", False),
            "has_guests_data": has_data.get("guests_count", False),
            "dashboardData": {
                "avg_spend": round(avg_spend, 2),
                "guests_count": guests_count,
                "google_rating": round(google_rating_value, 1) if google_rating_value else None,
                "total_spend": round(total_spend_value, 2),
                "attendance_rate": round(attendance_rate, 1),
                "new_clients_percent": round(new_clients_percent, 1),
                "regular_clients_percent": round(regular_clients_percent, 1),
                "retention_value": round(retention_value, 2),
                "marketing_data": marketing_data,
                "avg_spend_trend": avg_spend_trend,
                "attendance_trend": attendance_trend,
                "has_data": has_data
            }
        })
        
    except Exception as e:
        print(f"Dashboard error: {str(e)}")
        import traceback
        traceback.print_exc()
        return templates.TemplateResponse("error.html", {
            "request": request,
            "title": "Error",
            "error": f"Dashboard error: {str(e)}"
        }, status_code=500)

@app.get("/api/dashboard/config")
async def get_dashboard_config(request: Request, session: Session = Depends(get_session)):
    """Получить конфигурацию дашборда"""
    user = get_current_user(request)
    if not user:
        raise HTTPException(status_code=401, detail="Не авторизован")
    
    business_id = user.get("business_id")
    if not business_id:
        return JSONResponse({"config": {}, "success": True})
    
    business = session.get(Business, business_id)
    if not business:
        raise HTTPException(status_code=404, detail="Бизнес не найден")
    
    config = business.dashboard_config or {}
    # Return dashboard config as is (no filtering needed)
    
    return JSONResponse({"config": config, "success": True})

@app.post("/api/dashboard/config")
async def save_dashboard_config(request: Request, session: Session = Depends(get_session)):
    """Сохранить конфигурацию дашборда"""
    user = get_current_user(request)
    if not user:
        raise HTTPException(status_code=401, detail="Не авторизован")
    
    business_id = user.get("business_id")
    if not business_id:
        return JSONResponse({"success": False, "message": "No business ID"})
    
    business = session.get(Business, business_id)
    if not business:
        raise HTTPException(status_code=404, detail="Бизнес не найден")
    
    data = await request.json()
    business.dashboard_config = data.get("config", {})
    session.add(business)
    session.commit()
    
    return JSONResponse({"success": True})

@app.get("/booking", response_class=HTMLResponse)
async def booking_page(request: Request, session: Session = Depends(get_session)):
    user = get_current_user(request)
    if not user:
        return RedirectResponse(url="/login", status_code=302)

    # Проверяем активность бизнеса
    business, error = check_business_active(request, session)
    if error:
        return templates.TemplateResponse("login.html", {
            "request": request,
            "title": "Login",
            "error": error
        }, status_code=400)

    business_id = user.get("business_id")

    # Получаем дату из query, по умолчанию сегодня
    query_params = dict(request.query_params)
    date_str = query_params.get("date")
    try:
        selected_date = _datetime.strptime(date_str, "%Y-%m-%d").date() if date_str else _datetime.utcnow().date()
    except Exception:
        selected_date = _datetime.utcnow().date()

    # Загружаем бронирования на выбранную дату (включая ночные резервации)
    if business_id:
        contact_ids_for_business = session.exec(select(Contact.id).where(Contact.business_id == business_id)).all()
        contact_ids_for_business = [cid for (cid,) in contact_ids_for_business] if contact_ids_for_business and isinstance(contact_ids_for_business[0], tuple) else contact_ids_for_business
        if contact_ids_for_business:
            # Загружаем резервации, которые начинаются в выбранную дату
            bookings_start = session.exec(
                select(Booking)
                .where(Booking.date == selected_date, Booking.contact_id.in_(contact_ids_for_business))
                .order_by(Booking.time_from)
            ).all()
            
            # Загружаем ночные резервации, которые заканчиваются в выбранную дату
            bookings_end = session.exec(
                select(Booking)
                .where(Booking.end_date == selected_date, Booking.contact_id.in_(contact_ids_for_business))
                .order_by(Booking.time_from)
            ).all()
            
            # Объединяем и сортируем резервации
            # Сначала ночные, которые заканчиваются в выбранную дату (с «луной»), затем остальные по времени
            all_bookings = list(bookings_start) + list(bookings_end)
            bookings = sorted(
                all_bookings,
                key=lambda b: (
                    0 if (getattr(b, "end_date", None) == selected_date) else 1,
                    getattr(b, "time_from", None) or _datetime.strptime("00:00", "%H:%M").time(),
                ),
            )
        else:
            bookings = []
    else:
        # Загружаем резервации, которые начинаются в выбранную дату
        bookings_start = session.exec(select(Booking).where(Booking.date == selected_date).order_by(Booking.time_from)).all()
        
        # Загружаем ночные резервации, которые заканчиваются в выбранную дату
        bookings_end = session.exec(select(Booking).where(Booking.end_date == selected_date).order_by(Booking.time_from)).all()
        
        # Объединяем и сортируем резервации
        # Сначала ночные, которые заканчиваются в выбранную дату (с «луной»), затем остальные по времени
        all_bookings = list(bookings_start) + list(bookings_end)
        bookings = sorted(
            all_bookings,
            key=lambda b: (
                0 if (getattr(b, "end_date", None) == selected_date) else 1,
                getattr(b, "time_from", None) or _datetime.strptime("00:00", "%H:%M").time(),
            ),
        )

    # Для отображения имени клиента подготовим карту id->Contact
    contact_ids = {b.contact_id for b in bookings}
    contacts_map = {}
    if contact_ids:
        contacts = session.exec(select(Contact).where(Contact.id.in_(contact_ids))).all()
        contacts_map = {c.id: c for c in contacts}

    # Подсчитываем общее количество людей во всех резервациях на выбранную дату
    total_guests_count = sum(b.party_size or 0 for b in bookings)

    # Данные для поиска
    contacts, client_stats = get_client_stats(session, business_id) if business_id else ([], {})

    return templates.TemplateResponse("booking.html", {
        "request": request,
        "title": "Booking",
        "user": user,
        "bookings": bookings,
        "contacts_map": contacts_map,
        "selected_date": selected_date,
        "contacts": contacts,
        "client_stats": client_stats,
        "total_guests_count": total_guests_count,
        "business_capacity": business.capacity if business else None,
    })

@app.get("/clients", response_class=HTMLResponse)
async def clients_page(request: Request, session: Session = Depends(get_session)):
    user = get_current_user(request)
    if not user:
        return RedirectResponse(url="/login", status_code=302)
    
    # Проверяем активность бизнеса
    business, error = check_business_active(request, session)
    if error:
        return templates.TemplateResponse("login.html", {
            "request": request,
            "title": "Login",
            "error": error
        }, status_code=400)
    
    business_id = user.get("business_id")
    if not business_id:
        return RedirectResponse(url="/login", status_code=302)
    
    contacts, client_stats = get_client_stats(session, business_id)
    
    return templates.TemplateResponse("clients.html", {
        "request": request, 
        "title": "Clients",
        "contacts": contacts,
        "client_stats": client_stats
    })

@app.get("/map", response_class=HTMLResponse)
async def map_page(request: Request, session: Session = Depends(get_session)):
    user = get_current_user(request)
    if not user:
        return RedirectResponse(url="/login", status_code=302)
    
    # Проверяем активность бизнеса
    business, error = check_business_active(request, session)
    if error:
        return templates.TemplateResponse("login.html", {
            "request": request,
            "title": "Login",
            "error": error
        }, status_code=400)
    
    business_id = user.get("business_id")
    contacts, client_stats = get_client_stats(session, business_id) if business_id else ([], {})
    
    return templates.TemplateResponse("map.html", {
        "request": request, 
        "title": "Map", 
        "contacts": contacts, 
        "client_stats": client_stats
    })

@app.get("/marketing", response_class=HTMLResponse)
async def marketing_page(request: Request, session: Session = Depends(get_session)):
    user = get_current_user(request)
    if not user:
        return RedirectResponse(url="/login", status_code=302)
    
    # Проверяем активность бизнеса
    business, error = check_business_active(request, session)
    if error:
        return templates.TemplateResponse("login.html", {
            "request": request,
            "title": "Login",
            "error": error
        }, status_code=400)
    
    business_id = user.get("business_id")
    contacts, client_stats = get_client_stats(session, business_id) if business_id else ([], {})
    
    return templates.TemplateResponse("marketing.html", {
        "request": request, 
        "title": "Marketing", 
        "contacts": contacts, 
        "client_stats": client_stats
    })

@app.get("/settings", response_class=HTMLResponse)
async def settings_page(request: Request, session: Session = Depends(get_session)):
    user = get_current_user(request)
    if not user:
        return RedirectResponse(url="/login", status_code=302)
    
    # Проверяем активность бизнеса
    business, error = check_business_active(request, session)
    if error:
        return templates.TemplateResponse("login.html", {
            "request": request,
            "title": "Login",
            "error": error
        }, status_code=400)
    
    business_id = user.get("business_id")
    if not business_id:
        return RedirectResponse(url="/login", status_code=302)
    
    # Получаем сотрудников только для текущего бизнеса
    promoters = session.exec(select(Promoter).where(Promoter.business_id == business_id)).all()
    contacts, client_stats = get_client_stats(session, business_id)
    
    return templates.TemplateResponse("settings.html", {
        "request": request, 
        "title": "Settings",
        "promoters": promoters,
        "business_id": business_id,
        "contacts": contacts,
        "client_stats": client_stats
    })

# API для работы с настройками бизнеса
@app.get("/api/business/subscription-status")
async def get_subscription_status(request: Request, session: Session = Depends(get_session)):
    """Получить статус подписки"""
    user = get_current_user(request)
    if not user:
        return JSONResponse({"success": False, "error": "Unauthorized"}, status_code=401)
    
    business_id = user.get("business_id")
    if not business_id:
        return JSONResponse({"success": False, "error": "No business ID"}, status_code=400)
    
    business = session.get(Business, business_id)
    if not business:
        return JSONResponse({"success": False, "error": "Business not found"}, status_code=404)
    
    from datetime import datetime
    is_expired = business.access_end_date and business.access_end_date < datetime.utcnow()
    
    return {
        "success": True,
        "is_expired": is_expired,
        "access_end_date": business.access_end_date.isoformat() if business.access_end_date else None,
        "status": business.status.value
    }

@app.get("/api/business/settings")
async def get_business_settings(request: Request, session: Session = Depends(get_session)):
    """Получить настройки текущего бизнеса"""
    user = get_current_user(request)
    if not user:
        return JSONResponse({"success": False, "error": "Unauthorized"}, status_code=401)
    
    business_id = user.get("business_id")
    if not business_id:
        return JSONResponse({"success": False, "error": "Business not found"}, status_code=404)
    
    business = session.get(Business, business_id)
    if not business:
        return JSONResponse({"success": False, "error": "Business not found"}, status_code=404)
    
    return {
        "success": True,
        "settings": {
            "business_name": business.business_name,
            "address": business.address,
            "email": business.email,
            "currency": business.currency or "EUR",
            "capacity": business.capacity,
            "booking_duration": business.booking_duration or 2,
            "working_schedule": business.working_schedule or {},
            "timezone": business.timezone or "Europe/Belgrade"
        }
    }

@app.post("/api/business/settings")
async def update_business_settings(request: Request, session: Session = Depends(get_session)):
    """Обновить настройки бизнеса"""
    # Проверяем подписку
    subscription_check = check_subscription_in_api(request, session)
    if subscription_check:
        return subscription_check
    
    user = get_current_user(request)
    if not user:
        return JSONResponse({"success": False, "error": "Unauthorized"}, status_code=401)
    
    business_id = user.get("business_id")
    if not business_id:
        return JSONResponse({"success": False, "error": "Business not found"}, status_code=404)
    
    business = session.get(Business, business_id)
    if not business:
        return JSONResponse({"success": False, "error": "Business not found"}, status_code=404)
    
    try:
        data = await request.json()
        
        # Обновляем поля
        if "business_name" in data:
            business.business_name = data["business_name"]
        if "address" in data:
            business.address = data["address"]
        if "email" in data:
            business.email = data["email"]
        if "currency" in data:
            business.currency = data["currency"]
        if "capacity" in data:
            business.capacity = data["capacity"]
        if "booking_duration" in data:
            business.booking_duration = data["booking_duration"]
        if "working_schedule" in data:
            business.working_schedule = data["working_schedule"]
        if "timezone" in data:
            business.timezone = data["timezone"]
        
        # Обработка Google Maps URL
        if "google_maps_url" in data:
            old_url = business.google_maps_url
            new_url = data["google_maps_url"].strip()
            
            # Извлекаем данные из URL (включая обработку прямых координат)
            maps_data = extract_google_maps_data(new_url)
            print(f"📊 Извлеченные данные из Google Maps URL: {maps_data}")
            
            # Если это координаты, используем стандартный URL вместо координат
            if maps_data.get("standard_url") and maps_data.get("coordinates"):
                # Если введены координаты, сохраняем стандартный URL
                business.google_maps_url = maps_data["standard_url"]
                print(f"✅ Координаты преобразованы в URL: {maps_data['standard_url']}")
            elif new_url:
                # Для обычных URL сохраняем как есть
                business.google_maps_url = new_url
            else:
                business.google_maps_url = None
            
            # Если URL изменился и есть координаты или CID, логируем для дальнейшего использования
            if maps_data.get("coordinates"):
                print(f"📍 Координаты: {maps_data['coordinates']}")
            if maps_data.get("cid"):
                print(f"🆔 CID: {maps_data['cid']}")
            if maps_data.get("place_id"):
                print(f"🆔 Place ID: {maps_data['place_id']}")
        
        # Обработка ручного рейтинга
        if "google_rating_manual" in data:
            try:
                rating = float(data["google_rating_manual"]) if data["google_rating_manual"] else None
                if rating and 0 <= rating <= 5:
                    business.google_rating = rating
                elif data["google_rating_manual"] is None or data["google_rating_manual"] == "":
                    business.google_rating = None
            except (ValueError, TypeError):
                pass  # Игнорируем неверные значения
        
        business.updated_at = _datetime.utcnow()
        session.add(business)
        session.commit()
        session.refresh(business)
        return JSONResponse({"success": True, "settings": business.model_dump()}, status_code=200)
        
    except Exception as e:
        session.rollback()
        return JSONResponse({"success": False, "error": str(e)}, status_code=500)

@app.post("/api/business/reset-password")
async def reset_business_password_api(request: Request, session: Session = Depends(get_session)):
    """Сбросить пароль бизнеса (без проверки текущего пароля)"""
    print("🔐 API: reset_business_password called")
    
    user = get_current_user(request)
    if not user:
        print("❌ API: Unauthorized user")
        return JSONResponse({"success": False, "error": "Unauthorized"}, status_code=401)
    
    business_id = user.get("business_id")
    if not business_id:
        print("❌ API: No business_id in user")
        return JSONResponse({"success": False, "error": "Business not found"}, status_code=404)
    
    print(f"✅ API: User authorized, business_id: {business_id}")
    
    business = session.get(Business, business_id)
    if not business:
        print("❌ API: Business not found in database")
        return JSONResponse({"success": False, "error": "Business not found"}, status_code=404)
    
    print(f"✅ API: Business found: {business.business_name}")
    
    try:
        data = await request.json()
        new_password = data.get("new_password")
        
        print(f"📝 API: Received data - new_password length: {len(new_password) if new_password else 0}")
        
        if not new_password:
            print("❌ API: No new password provided")
            return JSONResponse({"success": False, "error": "New password is required"}, status_code=400)
        
        # Хешируем новый пароль (используем SHA256, как при логине)
        print("🔐 API: Hashing new password...")
        from app.auth import hash_password
        business.password_hash = hash_password(new_password)
        
        business.updated_at = _datetime.utcnow()
        session.add(business)
        session.commit()
        
        print("✅ API: Password saved to database")
        
        # Отправляем email уведомление о смене пароля
        print("📧 API: Sending email notification...")
        try:
            from app.email_service import send_notification_email
            
            subject = "🔐 Password je uspešno promenjen - LovaCRM"
            message = f"""
            Zdravo, {business.business_name}!
            
            ✅ POTVRDA: Vaš password je uspešno promenjen!
            
            Detalji:
            📧 Email: {business.email}
            🏢 Naziv biznisa: {business.business_name}
            📅 Datum promene: {_datetime.utcnow().strftime('%Y-%m-%d %H:%M')}
            
            Vaš novi password je aktiviran i možete se prijaviti na sistem.
            
            Ako niste vi promenili password, kontaktirajte nas odmah!
            
            Sa poštovanjem,
            Tim LovaCRM
            """
            
            email_sent = send_notification_email(
                to_email=business.email,
                subject=subject,
                message=message,
                notification_type="success"
            )
            
            if email_sent:
                print("✅ API: Email o promeni passworda je poslat!")
            else:
                print("❌ API: Greška pri slanju email-a o promeni passworda")
                
        except Exception as email_error:
            print(f"❌ API: Greška pri slanju email-a: {str(email_error)}")
        
        print("✅ API: Password reset completed successfully")
        return {"success": True}
        
    except Exception as e:
        session.rollback()
        print(f"❌ API: Error in reset password: {str(e)}")
        return JSONResponse({"success": False, "error": str(e)}, status_code=500)

@app.post("/api/business/change-password")
async def change_business_password(request: Request, session: Session = Depends(get_session)):
    """Изменить пароль бизнеса"""
    print("🔐 API: change_business_password called")
    
    user = get_current_user(request)
    if not user:
        print("❌ API: Unauthorized user")
        return JSONResponse({"success": False, "error": "Unauthorized"}, status_code=401)
    
    business_id = user.get("business_id")
    if not business_id:
        print("❌ API: No business_id in user")
        return JSONResponse({"success": False, "error": "Business not found"}, status_code=404)
    
    print(f"✅ API: User authorized, business_id: {business_id}")
    
    business = session.get(Business, business_id)
    if not business:
        print("❌ API: Business not found in database")
        return JSONResponse({"success": False, "error": "Business not found"}, status_code=404)
    
    print(f"✅ API: Business found: {business.business_name}")
    
    try:
        data = await request.json()
        new_password = data.get("new_password")
        current_password = data.get("current_password")
        
        print(f"📝 API: Received data - new_password length: {len(new_password) if new_password else 0}")
        print(f"📝 API: Received data - current_password length: {len(current_password) if current_password else 0}")
        
        if not new_password:
            print("❌ API: No new password provided")
            return JSONResponse({"success": False, "error": "New password is required"}, status_code=400)
        
        # Проверяем текущий пароль (если указан)
        if current_password and business.password_hash:
            print("🔍 API: Checking current password...")
            from app.auth import hash_password
            current_password_hash = hash_password(current_password)
            
            if current_password_hash != business.password_hash:
                print("❌ API: Current password is incorrect")
                return JSONResponse({"success": False, "error": "Trenutni password je netačan!"}, status_code=400)
            print("✅ API: Current password verified")
        else:
            print("⚠️ API: No current password provided or no password_hash in business")
        
        # Хешируем новый пароль (используем SHA256, как при логине)
        print("🔐 API: Hashing new password...")
        from app.auth import hash_password
        business.password_hash = hash_password(new_password)
        
        business.updated_at = _datetime.utcnow()
        session.add(business)
        session.commit()
        
        print("✅ API: Password saved to database")
        
        # Отправляем email уведомление о смене пароля
        print("📧 API: Sending email notification...")
        try:
            from app.email_service import send_notification_email
            
            subject = "🔐 Password je uspešno promenjen - LovaCRM"
            message = f"""
            Zdravo, {business.business_name}!
            
            ✅ POTVRDA: Vaš password je uspešno promenjen!
            
            Detalji:
            📧 Email: {business.email}
            🏢 Naziv biznisa: {business.business_name}
            📅 Datum promene: {_datetime.utcnow().strftime('%Y-%m-%d %H:%M')}
            
            Vaš novi password je aktiviran i možete se prijaviti na sistem.
            
            Ako niste vi promenili password, kontaktirajte nas odmah!
            
            Sa poštovanjem,
            Tim LovaCRM
            """
            
            email_sent = send_notification_email(
                to_email=business.email,
                subject=subject,
                message=message,
                notification_type="success"
            )
            
            if email_sent:
                print("✅ API: Email o promeni passworda je poslat!")
            else:
                print("❌ API: Greška pri slanju email-a o promeni passworda")
                
        except Exception as email_error:
            print(f"❌ API: Greška pri slanju email-a: {str(email_error)}")
        
        print("✅ API: Password change completed successfully")
        return {"success": True}
        
    except Exception as e:
        session.rollback()
        return JSONResponse({"success": False, "error": str(e)}, status_code=500)

# API для работы с промоутерами
@app.get("/api/promoters")
async def get_promoters(request: Request, session: Session = Depends(get_session)):
    """Получить список промоутеров для текущего бизнеса"""
    user = get_current_user(request)
    if not user:
        return JSONResponse({"success": False, "error": "Unauthorized"}, status_code=401)
    
    business_id = user.get("business_id")
    if not business_id:
        return JSONResponse({"success": False, "error": "Business not found"}, status_code=404)
    
    promoters = session.exec(select(Promoter).where(Promoter.business_id == business_id)).all()
    
    return {
        "success": True,
        "promoters": [
            {
                "id": p.id,
                "name": p.name,
                "phone": p.phone,
                "email": p.email,
                "instagram_handle": p.instagram_handle,
                "role": p.role or "Employee"
            }
            for p in promoters
        ]
    }

@app.post("/api/promoters")
async def create_promoter(request: Request, session: Session = Depends(get_session)):
    """Создать нового промоутера"""
    # Проверяем подписку
    subscription_check = check_subscription_in_api(request, session)
    if subscription_check:
        return subscription_check
    
    user = get_current_user(request)
    if not user:
        return JSONResponse({"success": False, "error": "Unauthorized"}, status_code=401)
    
    business_id = user.get("business_id")
    if not business_id:
        return JSONResponse({"success": False, "error": "Business not found"}, status_code=404)
    
    try:
        data = await request.json()
        
        promoter = Promoter(
            name=data.get("name", ""),
            phone=data.get("phone"),
            email=data.get("email"),
            instagram_handle=data.get("instagram_handle"),
            role=data.get("role", "Employee"),
            business_id=business_id
        )
        
        session.add(promoter)
        session.commit()
        session.refresh(promoter)
        
        return {
            "success": True,
            "promoter": {
                "id": promoter.id,
                "name": promoter.name,
                "phone": promoter.phone,
                "email": promoter.email,
                "instagram_handle": promoter.instagram_handle,
                "role": promoter.role or "Employee"
            }
        }
        
    except Exception as e:
        session.rollback()
        return JSONResponse({"success": False, "error": str(e)}, status_code=500)

@app.put("/api/promoters/{promoter_id}")
async def update_promoter(promoter_id: int, request: Request, session: Session = Depends(get_session)):
    """Обновить промоутера"""
    user = get_current_user(request)
    if not user:
        return JSONResponse({"success": False, "error": "Unauthorized"}, status_code=401)
    
    business_id = user.get("business_id")
    if not business_id:
        return JSONResponse({"success": False, "error": "Business not found"}, status_code=404)
    
    try:
        promoter = session.get(Promoter, promoter_id)
        if not promoter:
            return JSONResponse({"success": False, "error": "Promoter not found"}, status_code=404)
        
        # Проверяем, что промоутер принадлежит текущему бизнесу
        if promoter.business_id != business_id:
            return JSONResponse({"success": False, "error": "Unauthorized"}, status_code=403)
        
        data = await request.json()
        
        # Обновляем поля
        if "name" in data:
            promoter.name = data["name"]
        if "phone" in data:
            promoter.phone = data.get("phone")
        if "email" in data:
            promoter.email = data.get("email")
        if "role" in data:
            promoter.role = data.get("role")
        if "instagram_handle" in data:
            promoter.instagram_handle = data.get("instagram_handle")
        
        session.add(promoter)
        session.commit()
        session.refresh(promoter)
        
        return {
            "success": True,
            "promoter": {
                "id": promoter.id,
                "name": promoter.name,
                "phone": promoter.phone,
                "email": promoter.email,
                "instagram_handle": promoter.instagram_handle,
                "role": promoter.role or "Employee"
            }
        }
        
    except Exception as e:
        session.rollback()
        return JSONResponse({"success": False, "error": str(e)}, status_code=500)

@app.delete("/api/promoters/{promoter_id}")
async def delete_promoter(promoter_id: int, request: Request, session: Session = Depends(get_session)):
    """Удалить промоутера"""
    user = get_current_user(request)
    if not user:
        return JSONResponse({"success": False, "error": "Unauthorized"}, status_code=401)
    
    business_id = user.get("business_id")
    if not business_id:
        return JSONResponse({"success": False, "error": "Business not found"}, status_code=404)
    
    try:
        promoter = session.get(Promoter, promoter_id)
        if not promoter:
            return JSONResponse({"success": False, "error": "Promoter not found"}, status_code=404)
        
        # Проверяем, что промоутер принадлежит текущему бизнесу
        if promoter.business_id != business_id:
            return JSONResponse({"success": False, "error": "Unauthorized"}, status_code=403)
        
        session.delete(promoter)
        session.commit()
        
        return {"success": True}
        
    except Exception as e:
        session.rollback()
        return JSONResponse({"success": False, "error": str(e)}, status_code=500)

@app.get("/api/users")
async def get_users(request: Request, session: Session = Depends(get_session)):
    """Получить список пользователей с ролями для текущего бизнеса (для settings страницы)"""
    print("🔍 GET /api/users called")  # Логирование для отладки
    user = get_current_user(request)
    if not user:
        print("❌ Unauthorized request to /api/users")
        return JSONResponse({"success": False, "error": "Unauthorized"}, status_code=401)
    
    business_id = user.get("business_id")
    if not business_id:
        print(f"❌ Business not found for user: {user}")
        return JSONResponse({"success": False, "error": "Business not found"}, status_code=404)
    
    promoters = session.exec(select(Promoter).where(Promoter.business_id == business_id)).all()
    
    return JSONResponse({
        "success": True,
        "users": [
            {
                "id": p.id,
                "name": p.name,
                "phone": p.phone or "",
                "email": p.email or "",
                "role": p.role or "Employee"
            }
            for p in promoters
        ]
    })

@app.post("/api/users")
async def create_user(request: Request, session: Session = Depends(get_session)):
    """Создать нового пользователя с ролью"""
    print("🔍 POST /api/users called")  # Логирование для отладки
    # Проверяем подписку
    subscription_check = check_subscription_in_api(request, session)
    if subscription_check:
        return subscription_check
    
    user = get_current_user(request)
    if not user:
        print("❌ Unauthorized POST request to /api/users")
        return JSONResponse({"success": False, "error": "Unauthorized"}, status_code=401)
    
    business_id = user.get("business_id")
    if not business_id:
        return JSONResponse({"success": False, "error": "Business not found"}, status_code=404)
    
    try:
        data = await request.json()
        
        # Валидация обязательных полей
        if not data.get("name") or not data.get("name").strip():
            return JSONResponse({"success": False, "error": "Ime je obavezno polje"}, status_code=400)
        
        promoter = Promoter(
            name=data.get("name", "").strip(),
            phone=data.get("phone", "").strip() if data.get("phone") else None,
            email=data.get("email", "").strip() if data.get("email") else None,
            role=data.get("role", "Employee"),
            business_id=business_id
        )
        
        session.add(promoter)
        session.commit()
        session.refresh(promoter)
        
        return JSONResponse({
            "success": True,
            "user": {
                "id": promoter.id,
                "name": promoter.name,
                "phone": promoter.phone or "",
                "email": promoter.email or "",
                "role": promoter.role or "Employee"
            }
        })
        
    except Exception as e:
        session.rollback()
        error_msg = str(e)
        print(f"❌ Error creating user: {error_msg}")  # Логируем ошибку на сервере
        # Проверяем, не связана ли ошибка с отсутствием полей в БД
        if "no such column" in error_msg.lower():
            return JSONResponse({
                "success": False, 
                "error": "База данных требует обновления. Пожалуйста, запустите миграцию: python migrate_promoter_fields.py"
            }, status_code=500)
        return JSONResponse({"success": False, "error": error_msg}, status_code=500)

@app.put("/api/users/{user_id}")
async def update_user(user_id: int, request: Request, session: Session = Depends(get_session)):
    """Обновить пользователя"""
    user = get_current_user(request)
    if not user:
        return JSONResponse({"success": False, "error": "Unauthorized"}, status_code=401)
    
    business_id = user.get("business_id")
    if not business_id:
        return JSONResponse({"success": False, "error": "Business not found"}, status_code=404)
    
    try:
        promoter = session.get(Promoter, user_id)
        if not promoter:
            return JSONResponse({"success": False, "error": "User not found"}, status_code=404)
        
        # Проверяем, что пользователь принадлежит текущему бизнесу
        if promoter.business_id != business_id:
            return JSONResponse({"success": False, "error": "Unauthorized"}, status_code=403)
        
        data = await request.json()
        
        # Обновляем поля
        if "name" in data:
            promoter.name = data["name"]
        if "phone" in data:
            promoter.phone = data.get("phone")
        if "email" in data:
            promoter.email = data.get("email")
        if "role" in data:
            promoter.role = data.get("role")
        
        session.add(promoter)
        session.commit()
        session.refresh(promoter)
        
        return {
            "success": True,
            "user": {
                "id": promoter.id,
                "name": promoter.name,
                "phone": promoter.phone or "",
                "email": promoter.email or "",
                "role": promoter.role or "Employee"
            }
        }
        
    except Exception as e:
        session.rollback()
        return JSONResponse({"success": False, "error": str(e)}, status_code=500)

@app.delete("/api/users/{user_id}")
async def delete_user(user_id: int, request: Request, session: Session = Depends(get_session)):
    """Удалить пользователя"""
    user = get_current_user(request)
    if not user:
        return JSONResponse({"success": False, "error": "Unauthorized"}, status_code=401)
    
    business_id = user.get("business_id")
    if not business_id:
        return JSONResponse({"success": False, "error": "Business not found"}, status_code=404)
    
    try:
        promoter = session.get(Promoter, user_id)
        if not promoter:
            return JSONResponse({"success": False, "error": "User not found"}, status_code=404)
        
        # Проверяем, что пользователь принадлежит текущему бизнесу
        if promoter.business_id != business_id:
            return JSONResponse({"success": False, "error": "Unauthorized"}, status_code=403)
        
        session.delete(promoter)
        session.commit()
        
        return {"success": True}
        
    except Exception as e:
        session.rollback()
        return JSONResponse({"success": False, "error": str(e)}, status_code=500)

@app.get("/clients/new", response_class=HTMLResponse)
async def new_client_form(request: Request):
    user = get_current_user(request)
    if not user:
        return RedirectResponse(url="/login", status_code=302)
    return templates.TemplateResponse("client_form.html", {"request": request, "title": "Novi klijent", "user": user})

@app.get("/clients/quick-add")
async def quick_add_client(request: Request, session: Session = Depends(get_session)):
    user = get_current_user(request)
    if not user:
        return RedirectResponse(url="/login", status_code=302)
    
    business_id = user.get("business_id")
    if not business_id:
        return RedirectResponse(url="/login", status_code=302)
    
    # Проверяем подписку
    if check_subscription_expired(business_id, session):
        # Перенаправляем на страницу клиентов с сообщением об ошибке
        return RedirectResponse(url="/clients?error=subscription_expired", status_code=302)
    
    # Находим максимальный номер клиента среди всех клиентов с именем "Klijent №X" для данного бизнеса
    contacts = session.exec(select(Contact).where(Contact.business_id == business_id, Contact.first_name.like("Klijent №%"))).all()
    max_number = 0
    
    for contact in contacts:
        # Извлекаем номер из имени "Klijent №X" (используем № как разделитель)
        if contact.first_name.startswith("Klijent №"):
            try:
                # Ищем номер после "Klijent №"
                number_part = contact.first_name.split("№")[1].strip()
                number = int(number_part)
                max_number = max(max_number, number)
            except (ValueError, IndexError):
                continue
    
    # Создаем нового клиента с следующим номером
    next_number = max_number + 1
    contact = Contact(
        business_id=business_id,
        first_name=f"Klijent №{next_number}",
        last_name=None,
        phone=None,
        email=None,
        instagram_handle=None,
        nickname=None,
        gender=None,
        city=None,
        birth_date=None,
        preferences=None,
        rating=None,
        created_at=datetime.utcnow()
    )
    session.add(contact)
    session.commit()
    session.refresh(contact)
    return RedirectResponse(url=f"/clients/{contact.id}", status_code=302)

@app.post("/clients/new")
async def create_client(
    request: Request,
    first_name: str = Form(...),
    last_name: str = Form(None),
    phone: str = Form(None),
    email: str = Form(None),
    instagram_handle: str = Form(None),
    nickname: str = Form(None),
    gender: str = Form(None),
    city: str = Form(None),
    birth_date: str = Form(None),
    communication_method: str = Form(None),
    promoter_name: str = Form(None),
    rating: str = Form(None),
    preferences_text: str = Form(None),
    is_regular: str = Form(None),
    knows_owner: str = Form(None),
    session: Session = Depends(get_session),
):
    user = get_current_user(request)
    if not user:
        return RedirectResponse(url="/login", status_code=302)
    
    business_id = user.get("business_id")
    if not business_id:
        return RedirectResponse(url="/login", status_code=302)
    
    # Parse birth_date
    parsed_birth_date = None
    if birth_date:
        try:
            parsed_birth_date = _datetime.strptime(birth_date, "%Y-%m-%d").date()
        except Exception:
            pass
    
    # Build preferences JSON
    preferences = {}
    if communication_method:
        preferences["communication_method"] = communication_method
    if promoter_name:
        preferences["promoter_name"] = promoter_name
    if preferences_text:
        preferences["preferences_text"] = preferences_text
    preferences["is_regular"] = True if is_regular else False
    preferences["knows_owner"] = True if knows_owner else False
    
    # Parse rating
    parsed_rating = None
    if rating is not None and rating != "":
        try:
            parsed_rating = int(rating)
        except Exception:
            pass
    
    contact = Contact(
        business_id=business_id,
        first_name=first_name,
        last_name=last_name,
        phone=phone,
        email=email,
        instagram_handle=instagram_handle,
        nickname=nickname,
        gender=gender,
        city=city,
        birth_date=parsed_birth_date,
        preferences=preferences if preferences else None,
        rating=parsed_rating,
        created_at=datetime.utcnow()
    )
    session.add(contact)
    session.commit()
    session.refresh(contact)
    return RedirectResponse(url="/clients", status_code=302)

@app.get("/clients/{contact_id}", response_class=HTMLResponse)
async def client_detail(request: Request, contact_id: int, session: Session = Depends(get_session)):
    user = get_current_user(request)
    if not user:
        return RedirectResponse(url="/login", status_code=302)
    
    business_id = user.get("business_id")
    if not business_id:
        return RedirectResponse(url="/login", status_code=302)
    
    contact = session.get(Contact, contact_id)
    if not contact or contact.business_id != business_id:
        return RedirectResponse(url="/clients", status_code=302)
    
    # Получаем бронирования для этого клиента
    bookings = session.exec(select(Booking).where(Booking.contact_id == contact_id).order_by(Booking.date.desc(), Booking.time_from.desc())).all()
    visits_count = len(bookings)
    total_spent = sum([b.spend_eur or 0 for b in bookings if b.spend_eur])
    rating = contact.rating or 0
    
    # Данные для поиска по всем клиентам бизнеса
    all_contacts, all_client_stats = get_client_stats(session, business_id)
    
    response = templates.TemplateResponse("client_detail.html", {
        "request": request,
        "title": f"Klijent: {contact.first_name}",
        "user": user,
        "contact": contact,
        "bookings": bookings,
        "visits_count": visits_count,
        "total_spent": total_spent,
        "rating": rating,
        "all_contacts": all_contacts,
        "all_client_stats": all_client_stats
    })
    
    # Добавляем заголовки против кэширования
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Pragma"] = "no-cache"
    response.headers["Expires"] = "0"
    
    return response

@app.post("/register")
async def register(
    request: Request,
    business_name: str = Form(...),
    contact_person: str = Form(...),
    email: str = Form(...),
    phone: str = Form(...),
    address: str = Form(None),
    city: str = Form(None),
    country: str = Form(None),
    business_type: str = Form(None),
    description: str = Form(None),
    social_media: str = Form(None),
    session: Session = Depends(get_session),
):
    try:
        # Проверяем, не существует ли уже бизнес с таким email
        existing_business = session.exec(select(Business).where(Business.email == email)).first()
        if existing_business:
            # Формируем подробное сообщение в зависимости от статуса
            if existing_business.status == BusinessStatus.PENDING:
                error_msg = "⚠️ Sa ovim podacima već postoji korisnik! Vaša zahtev je poslat na odobrenje administratora."
            elif existing_business.status == BusinessStatus.ACTIVE:
                error_msg = "⚠️ Sa ovim podacima već postoji aktivan korisnik! Molimo prijavite se."
            elif existing_business.status == BusinessStatus.SUSPENDED:
                error_msg = "⚠️ Sa ovim podacima već postoji korisnik! Vaš nalog je privremeno suspendovan. Kontaktirajte administratora."
            elif existing_business.status == BusinessStatus.EXPIRED:
                error_msg = "⚠️ Sa ovim podacima već postoji korisnik! Vaš probni period je istekao. Kontaktirajte administratora za produženje."
            else:
                error_msg = "⚠️ Sa ovim podacima već postoji korisnik!"
            
            return templates.TemplateResponse("landing.html", {
                "request": request,
                "title": "LovaCRM",
                "error": error_msg
            }, status_code=400)
        
        # Автоматически заполняем город "Beograd" если поле пустое
        if not city or city.strip() == "":
            city = "Beograd"
            print(f"🏙️ Автоматически заполнен город: {city}")
        
        # Создаем новый бизнес
        business = Business(
            business_name=business_name,
            contact_person=contact_person,
            email=email,
            phone=phone,
            address=address,
            city=city,
            country=country,
            business_type=business_type,
            description=description,
            social_media=social_media,
            status=BusinessStatus.PENDING  # Сначала PENDING
        )
        
        session.add(business)
        session.commit()
        session.refresh(business)
        
        # Генерируем случайный пароль для бизнеса
        from app.auth import generate_random_password, hash_password
        random_password = generate_random_password(length=12)
        business.password_hash = hash_password(random_password)
        session.add(business)
        session.commit()
        session.refresh(business)
        
        # Автоматически активируем бизнес на 1 день (пробный период)
        from app.auth import activate_business_with_minutes
        success = activate_business_with_minutes(
            session=session,
            business_id=business.id,
            access_minutes=1440,  # 1 день (24 часа * 60 минут)
            assigned_admin_id=None
        )
        
        if success:
            # Обновляем информацию о бизнесе
            session.refresh(business)
            
            # Отправляем email клиенту с инструкциями
            try:
                from app.email_service import send_notification_email
                subject = "🎉 Dobrodošli u LovaCRM - Vaš probni period je aktivan!"
                message = f"""
                Zdravo, {business.business_name}!
                
                🎉 DOBRODOŠLI U LOVACRM!
                
                Vaš probni period je automatski aktiviran!
                
                Detalji:
                📧 Email: {business.email}
                🏢 Naziv biznisa: {business.business_name}
                ⏰ Probni period: 1 dan
                📅 Pristup do: {business.access_end_date.strftime('%Y-%m-%d %H:%M') if business.access_end_date else 'N/A'}
                
                🔐 PRISTUPNI PODACI:
                Link za prijavu: {request.base_url}login
                Email: {business.email}
                Password: {random_password}
                
                ⚠️ NAPOMENA:
                Ovo je probni period od 1 dana.
                Nakon isteka probnog perioda, vaš nalog će biti privremeno suspendovan.
                Za produženje pristupa, kontaktirajte našu podršku.
                
                Sa poštovanjem,
                Tim LovaCRM
                """
                send_notification_email(
                    to_email=business.email,
                    subject=subject,
                    message=message,
                    notification_type="success"
                )
            except Exception as email_error:
                print(f"❌ Greška pri slanju email-a klijentu: {str(email_error)}")
            
            # Отправляем email админу о новой регистрации
            try:
                from app.email_service import send_notification_email
                admin_subject = "🔔 Nova registracija u LovaCRM sistemu"
                admin_message = f"""
                Zdravo, Admin!
                
                🔔 NOVA REGISTRACIJA U LOVACRM SISTEMU
                
                Detalji novog korisnika:
                📧 Email: {business.email}
                🏢 Naziv biznisa: {business.business_name}
                👤 Kontakt osoba: {business.contact_person}
                📞 Telefon: {business.phone}
                📍 Adresa: {business.address or 'N/A'}
                🏙️ Grad: {business.city or 'N/A'}
                🌍 Zemlja: {business.country or 'N/A'}
                🏢 Tip biznisa: {business.business_type or 'N/A'}
                📝 Opis: {business.description or 'N/A'}
                📱 Društvene mreže: {business.social_media or 'N/A'}
                
                🔐 PRISTUPNI PODACI:
                Email: {business.email}
                Password: {random_password}
                Status: {business.status.value}
                ⏰ Probni period: 1 dan
                📅 Pristup do: {business.access_end_date.strftime('%Y-%m-%d %H:%M') if business.access_end_date else 'N/A'}
                
                🌐 Admin panel: {request.base_url}admin/login
                
                Sa poštovanjem,
                LovaCRM Sistem
                """
                send_notification_email(
                    to_email=settings.admin_email,
                    subject=admin_subject,
                    message=admin_message,
                    notification_type="info"
                )
            except Exception as admin_email_error:
                print(f"❌ Greška pri slanju email-a adminu: {str(admin_email_error)}")
            
            # Выводим информацию в консоль
            print("=" * 60)
            print("🎉 NOVI BIZNIS REGISTROVAN I AKTIVIRAN!")
            print(f"📧 Email: {business.email}")
            print(f"🏢 Naziv: {business.business_name}")
            print(f"🔐 Password: {random_password}")
            print(f"⏰ Probni period: 1 dan")
            print(f"📅 Pristup do: {business.access_end_date.strftime('%Y-%m-%d %H:%M') if business.access_end_date else 'N/A'}")
            print("📧 Email poslat klijentu i adminu!")
            print("=" * 60)
        
        return templates.TemplateResponse("landing.html", {
            "request": request,
            "title": "LovaCRM",
            "success": "🎉 Uspešno! Vaš probni period je započeo! Proverite email za pristupne podatke."
            })
        
    except Exception as e:
        print(f"Registration error: {str(e)}")
        return templates.TemplateResponse("landing.html", {
            "request": request,
            "title": "LovaCRM",
            "error": f"Greška pri registraciji: {str(e)}"
        }, status_code=400)

@app.get("/logout")
async def logout(request: Request):
    request.session.clear()
    return RedirectResponse(url="/login", status_code=302)

# Admin routes
@app.get("/admin/login", response_class=HTMLResponse)
async def admin_login_page(request: Request):
    return templates.TemplateResponse("admin_login_new.html", {"request": request, "title": "Admin Login"})

@app.post("/admin/login")
async def admin_login(request: Request, username: str = Form(...), password: str = Form(...), session: Session = Depends(get_session)):
    admin = authenticate_admin(session, username, password)
    if admin:
        # Генерируем код 2FA
        from app.auth import generate_2fa_code, send_2fa_code
        from datetime import datetime, timedelta
        
        code = generate_2fa_code()
        admin.two_factor_code = code
        admin.two_factor_code_expires = datetime.utcnow() + timedelta(minutes=5)
        session.add(admin)
        session.commit()
        
        # Отправляем код на email
        send_2fa_code(admin.email, code, admin.full_name)
        
        # Сохраняем временные данные в сессии для проверки кода
        request.session["admin_pending"] = {
            "id": admin.id,
            "username": admin.username,
            "role": admin.role.value
        }
        
        print(f"🔐 2FA код отправлен админу {admin.username}: {code}")
        
        # Перенаправляем на страницу ввода кода
        return RedirectResponse(url="/admin/verify-code", status_code=302)
    return templates.TemplateResponse("admin_login_new.html", {"request": request, "title": "Admin Login", "error": "Invalid credentials"}, status_code=400)

@app.get("/admin/verify-code", response_class=HTMLResponse)
async def admin_verify_code_page(request: Request):
    # Проверяем, есть ли pending admin в сессии
    admin_pending = request.session.get("admin_pending")
    if not admin_pending:
        return RedirectResponse(url="/admin/login", status_code=302)
    
    return templates.TemplateResponse("admin_verify_code.html", {
        "request": request,
        "title": "Verify Code"
    })

@app.post("/admin/verify-code")
async def admin_verify_code(request: Request, code: str = Form(...), session: Session = Depends(get_session)):
    admin_pending = request.session.get("admin_pending")
    if not admin_pending:
        return RedirectResponse(url="/admin/login", status_code=302)
    
    # Получаем админа из базы
    admin = session.get(Admin, admin_pending["id"])
    if not admin:
        return templates.TemplateResponse("admin_verify_code.html", {
            "request": request,
            "title": "Verify Code",
            "error": "Admin not found"
        }, status_code=400)
    
    # Проверяем код
    from datetime import datetime
    if admin.two_factor_code != code:
        return templates.TemplateResponse("admin_verify_code.html", {
            "request": request,
            "title": "Verify Code",
            "error": "Неверный код. Проверьте email и попробуйте снова."
        }, status_code=400)
    
    # Проверяем срок действия
    if admin.two_factor_code_expires and admin.two_factor_code_expires < datetime.utcnow():
        return templates.TemplateResponse("admin_verify_code.html", {
            "request": request,
            "title": "Verify Code",
            "error": "Код истёк. Пожалуйста, войдите заново."
        }, status_code=400)
    
    # Код верный, очищаем его и входим
    admin.two_factor_code = None
    admin.two_factor_code_expires = None
    session.add(admin)
    session.commit()
    
    # Переносим данные из admin_pending в admin
    request.session["admin"] = admin_pending
    del request.session["admin_pending"]
    
    print(f"✅ Админ {admin.username} успешно вошёл с 2FA")
    
    return RedirectResponse(url="/admin", status_code=302)

@app.get("/admin", response_class=HTMLResponse)
@app.get("/admin/dashboard", response_class=HTMLResponse)
async def admin_dashboard(request: Request, session: Session = Depends(get_session)):
    admin = get_current_admin(request)
    if not admin:
        return RedirectResponse(url="/admin/login", status_code=302)
    
    # Продлеваем сессию админа при активности
    extend_admin_session(request)
    
    businesses = get_all_businesses(session)
    pending_businesses = get_pending_businesses(session)
    
    # Подсчитываем статистику
    total_businesses = len(businesses)
    active_businesses = len([b for b in businesses if b.status == BusinessStatus.ACTIVE])
    pending_businesses_count = len(pending_businesses)
    suspended_businesses = len([b for b in businesses if b.status == BusinessStatus.SUSPENDED])
    expired_businesses = len([b for b in businesses if b.status == BusinessStatus.EXPIRED])
    
    # Подсчитываем общее количество бронирований
    bookings_query = select(Booking)
    bookings_result = session.exec(bookings_query)
    total_bookings = len(list(bookings_result))
    
    stats = {
        "total_businesses": total_businesses,
        "active_businesses": active_businesses,
        "pending_businesses": pending_businesses_count,
        "suspended_businesses": suspended_businesses,
        "expired_businesses": expired_businesses,
        "total_bookings": total_bookings
    }
    
    # Сортируем бизнесы по дате создания (новые первые)
    recent_businesses = sorted(businesses, key=lambda x: x.created_at or datetime.min, reverse=True)[:10]
    
    return templates.TemplateResponse("admin_dashboard_new.html", {
        "request": request,
        "title": "Admin Dashboard",
        "admin": admin,
        "stats": stats,
        "recent_businesses": recent_businesses
    })

@app.get("/admin/businesses", response_class=HTMLResponse)
async def admin_businesses(request: Request, session: Session = Depends(get_session)):
    admin = get_current_admin(request)
    if not admin:
        return RedirectResponse(url="/admin/login", status_code=302)
    
    # Продлеваем сессию админа при активности
    extend_admin_session(request)
    
    businesses = get_all_businesses(session)
    return templates.TemplateResponse("admin_businesses_new.html", {
        "request": request,
        "title": "Businesses",
        "admin": admin,
        "businesses": businesses
    })

@app.get("/admin/pending", response_class=HTMLResponse)
async def admin_pending(request: Request, session: Session = Depends(get_session)):
    admin = get_current_admin(request)
    if not admin:
        return RedirectResponse(url="/admin/login", status_code=302)
    
    pending_businesses = get_pending_businesses(session)
    return templates.TemplateResponse("admin_pending_new.html", {
        "request": request,
        "title": "Pending Businesses",
        "admin": admin,
        "pending_businesses": pending_businesses
    })

@app.post("/admin/businesses/{business_id}/activate")
async def admin_activate_business(
    business_id: int,
    request: Request,
    access_days: int = Form(7),
    access_hours: int = Form(0),
    access_minutes: int = Form(0),
    session: Session = Depends(get_session)
):
    admin = get_current_admin(request)
    if not admin:
        return JSONResponse({"success": False, "error": "Unauthorized"}, status_code=401)
    
    try:
        # Вычисляем общее время доступа в минутах
        total_minutes = access_days * 24 * 60 + access_hours * 60 + access_minutes
        
        # Если указано время, используем его, иначе используем дни
        if total_minutes > 0:
            success = activate_business_with_minutes(session, business_id, total_minutes, admin["id"])
        else:
            success = activate_business(session, business_id, access_days, admin["id"])
        
        if success:
            try:
                # Генерируем пароль для бизнеса
                business = session.get(Business, business_id)
                
                if business:
                    # Генерируем новый пароль
                    new_password = set_business_password(session, business_id)
                    
                    # Отправляем пароль на email (выводится в консоль)
                    send_password_email(
                        business.email, 
                        business.business_name, 
                        new_password, 
                        is_reset=False
                    )
                    
                    # Выводим дополнительную информацию в консоль
                    print("=" * 60)
                    print("🎉 БИЗНЕС АКТИВИРОВАН!")
                    print(f"📧 Email: {business.email}")
                    print(f"🏢 Название: {business.business_name}")
                    print(f"👤 Контактное лицо: {business.contact_person}")
                    print(f"📞 Телефон: {business.phone}")
                    print(f"🔑 Пароль: {new_password}")
                    print(f"⏰ Доступ до: {business.access_end_date}")
                    print(f"👨‍💼 Активировал: {admin['username']}")
                    print("=" * 60)
                else:
                    print(f"❌ ОШИБКА: Бизнес с ID {business_id} не найден после активации")
                    
            except Exception as e:
                print(f"❌ ОШИБКА при генерации пароля: {str(e)}")
                # Не прерываем выполнение, активация уже прошла успешно
            
            return JSONResponse({"success": True, "message": "Бизнес успешно активирован, пароль отправлен на email"})
        else:
            return JSONResponse({"success": False, "error": "Бизнес не найден"}, status_code=404)
            
    except Exception as e:
        return JSONResponse({"success": False, "error": str(e)}, status_code=500)

@app.get("/admin/settings", response_class=HTMLResponse)
async def admin_settings(request: Request, session: Session = Depends(get_session)):
    admin = get_current_admin(request)
    if not admin:
        return RedirectResponse(url="/admin/login", status_code=302)
    
    # Подсчитываем статистику системы
    businesses = get_all_businesses(session)
    bookings_query = select(Booking)
    bookings_result = session.exec(bookings_query)
    total_bookings = len(list(bookings_result))
    
    system_stats = {
        "total_users": len(businesses),
        "total_bookings": total_bookings,
        "emails_sent": 0,  # TODO: добавить подсчет отправленных email
        "system_uptime": 24  # TODO: добавить реальное время работы
    }
    
    return templates.TemplateResponse("admin_settings_new.html", {
        "request": request, 
        "title": "Admin Settings",
        "admin": admin,
        "system_stats": system_stats,
        "last_update": "2024-01-15"
    })

@app.get("/admin/logout")
async def admin_logout(request: Request):
    request.session.clear()
    return RedirectResponse(url="/admin/login", status_code=302)

@app.delete("/admin/businesses/{business_id}")
async def admin_delete_business(
    business_id: int,
    request: Request,
    session: Session = Depends(get_session)
):
    """Удалить бизнес и все связанные данные (каскадное удаление)"""
    admin = get_current_admin(request)
    if not admin:
        return JSONResponse({"success": False, "error": "Unauthorized"}, status_code=401)
    
    try:
        # Получаем бизнес
        business = session.get(Business, business_id)
        if not business:
            return JSONResponse({"success": False, "error": "Biznis nije pronađen"}, status_code=404)
        
        business_name = business.business_name
        
        # 1. Получаем всех клиентов бизнеса
        contacts = session.exec(
            select(Contact).where(Contact.business_id == business_id)
        ).all()
        
        contacts_count = len(contacts)
        bookings_count = 0
        
        # 2. Удаляем все резервации для всех клиентов
        for contact in contacts:
            bookings = session.exec(
                select(Booking).where(Booking.contact_id == contact.id)
            ).all()
            bookings_count += len(bookings)
            for booking in bookings:
                session.delete(booking)
        
        # 3. Удаляем всех клиентов
        for contact in contacts:
            session.delete(contact)
        
        # 4. Удаляем всех промоутеров (пользователей) бизнеса
        promoters = session.exec(
            select(Promoter).where(Promoter.business_id == business_id)
        ).all()
        promoters_count = len(promoters)
        for promoter in promoters:
            session.delete(promoter)
        
        # 5. Удаляем сам бизнес
        session.delete(business)
        
        # Сохраняем изменения
        session.commit()
        
        print(f"🗑️ Biznis obrisan: {business_name} (ID: {business_id})")
        print(f"   Obrisano klijenata: {contacts_count}")
        print(f"   Obrisano rezervacija: {bookings_count}")
        print(f"   Obrisano korisnika: {promoters_count}")
        
        return JSONResponse({
            "success": True,
            "message": f"Biznis '{business_name}' i svi podaci su uspešno obrisani",
            "deleted_contacts": contacts_count,
            "deleted_bookings": bookings_count,
            "deleted_promoters": promoters_count
        })
        
    except Exception as e:
        session.rollback()
        print(f"❌ Greška pri brisanju biznisa: {str(e)}")
        return JSONResponse({"success": False, "error": str(e)}, status_code=500)

@app.get("/admin/businesses/{business_id}", response_class=HTMLResponse)
async def admin_business_detail(business_id: int, request: Request, session: Session = Depends(get_session)):
    """Просмотр деталей конкретного бизнеса"""
    admin = get_current_admin(request)
    if not admin:
        return RedirectResponse(url="/admin/login", status_code=302)
    
    business = session.get(Business, business_id)
    if not business:
        return templates.TemplateResponse("error.html", {
            "request": request,
            "title": "Business Not Found",
            "error": f"Business with ID {business_id} not found"
        }, status_code=404)
    
    return templates.TemplateResponse("admin_business_detail_new.html", {
        "request": request,
        "title": f"Business: {business.business_name}",
        "admin": admin,
        "business": business,
        "now": datetime.utcnow()
    })

@app.get("/admin/businesses/{business_id}/edit", response_class=HTMLResponse)
async def admin_business_edit_form(business_id: int, request: Request, session: Session = Depends(get_session)):
    """Форма редактирования бизнеса"""
    admin = get_current_admin(request)
    if not admin:
        return RedirectResponse(url="/admin/login", status_code=302)
    
    business = session.get(Business, business_id)
    if not business:
        return templates.TemplateResponse("error.html", {
            "request": request,
            "title": "Business Not Found",
            "error": f"Business with ID {business_id} not found"
        }, status_code=404)
    
    return templates.TemplateResponse("admin_business_edit.html", {
        "request": request,
        "title": f"Edit Business: {business.business_name}",
        "admin": admin,
        "business": business
    })

@app.post("/admin/businesses/{business_id}/edit")
async def admin_business_edit(
    business_id: int,
    request: Request,
    session: Session = Depends(get_session),
    business_name: str = Form(...),
    contact_person: str = Form(...),
    email: str = Form(...),
    phone: str = Form(...),
    address: str = Form(None),
    city: str = Form(None),
    country: str = Form(None),
    business_type: str = Form(None),
    description: str = Form(None),
    notes: str = Form(None)
):
    """Обновление данных бизнеса"""
    admin = get_current_admin(request)
    if not admin:
        return RedirectResponse(url="/admin/login", status_code=302)
    
    business = session.get(Business, business_id)
    if not business:
        return {"success": False, "message": "Business not found"}
    
    try:
        # Обновляем данные
        business.business_name = business_name
        business.contact_person = contact_person
        business.email = email
        business.phone = phone
        business.address = address
        business.city = city
        business.country = country
        business.business_type = business_type
        business.description = description
        business.notes = notes
        business.updated_at = datetime.utcnow()
        
        session.add(business)
        session.commit()
        
        return {"success": True, "message": "Business updated successfully"}
    except Exception as e:
        session.rollback()
        return {"success": False, "message": f"Error updating business: {str(e)}"}

@app.get("/.well-known/appspecific/com.chrome.devtools.json")
async def chrome_devtools():
    """Обработка запроса от Chrome DevTools"""
    return {"message": "Chrome DevTools endpoint"}

@app.post("/admin/restart-system")
async def admin_restart_system(request: Request):
    """Перезапуск системы"""
    admin = get_current_admin(request)
    if not admin:
        return RedirectResponse(url="/admin/login", status_code=302)
    
    try:
        # Здесь можно добавить логику очистки кеша, перезапуска сервисов и т.д.
        # Пока просто возвращаем успех
        return {"success": True, "message": "Sistem je uspešno restartovan!"}
    except Exception as e:
        return {"success": False, "message": f"Greška pri restartovanju: {str(e)}"}

@app.post("/admin/businesses/{business_id}/reset-password")
async def reset_password(business_id: int, request: Request, session: Session = Depends(get_session)):
    """Сбрасывает пароль бизнеса и отправляет новый на email"""
    admin = get_current_admin(request)
    if not admin:
        return RedirectResponse(url="/admin/login", status_code=302)
    
    try:
        success = auth_reset_business_password(session, business_id)
        if success:
            return {"success": True, "message": "Пароль успешно сброшен и отправлен на email"}
        else:
            return {"success": False, "message": "Бизнес не найден"}
    except Exception as e:
        return {"success": False, "message": f"Ошибка: {str(e)}"}

@app.post("/admin/check-expired")
async def admin_check_expired(request: Request, session: Session = Depends(get_session)):
    """Ручная проверка истечения сроков доступа (для тестирования)"""
    admin = get_current_admin(request)
    if not admin:
        return JSONResponse({"success": False, "error": "Unauthorized"}, status_code=401)
    
    try:
        frozen_count = check_and_freeze_expired_businesses(session)
        return JSONResponse({
            "success": True, 
            "message": f"Проверка завершена. Заморожено бизнесов: {frozen_count}",
            "frozen_count": frozen_count
        })
    except Exception as e:
        return JSONResponse({"success": False, "error": str(e)}, status_code=500)

@app.post("/admin/check-upcoming-expirations")
async def admin_check_upcoming_expirations(request: Request, session: Session = Depends(get_session)):
    """Ручная проверка уведомлений о скором истечении сроков (для тестирования)"""
    admin = get_current_admin(request)
    if not admin:
        return JSONResponse({"success": False, "error": "Unauthorized"}, status_code=401)
    
    try:
        from app.auth import check_upcoming_expirations
        notification_count = check_upcoming_expirations(session)
        return JSONResponse({
            "success": True, 
            "message": f"Проверка уведомлений завершена. Отправлено уведомлений: {notification_count}",
            "notification_count": notification_count
        })
    except Exception as e:
        return JSONResponse({"success": False, "error": str(e)}, status_code=500)

@app.post("/admin/businesses/{business_id}/unfreeze")
async def admin_unfreeze_business(
    business_id: int,
    request: Request,
    new_access_days: int = Form(30),
    session: Session = Depends(get_session)
):
    """Размораживает бизнес и устанавливает новый срок доступа"""
    admin = get_current_admin(request)
    if not admin:
        return JSONResponse({"success": False, "error": "Unauthorized"}, status_code=401)
    
    try:
        # Проверяем, что бизнес существует и заморожен
        business = session.get(Business, business_id)
        if not business:
            return JSONResponse({"success": False, "error": "Biznis nije pronađen"}, status_code=404)
        
        if business.status != BusinessStatus.EXPIRED:
            return JSONResponse({"success": False, "error": "Biznis nije zamrznut"}, status_code=400)
        
        # Размораживаем бизнес
        success = unfreeze_business(session, business_id, new_access_days)
        
        if success:
            # Отправляем уведомления
            send_unfreeze_notification(
                business.email,
                business.business_name,
                new_access_days,
                admin_email="admin@lovacrm.com"
            )
            
            # Выводим информацию в консоль
            print("=" * 60)
            print("✅ BIZNIS RAZMRZNUT!")
            print(f"📧 Email: {business.email}")
            print(f"🏢 Naziv: {business.business_name}")
            print(f"⏰ Novi rok pristupa: {new_access_days} dana")
            print("=" * 60)
            
            return JSONResponse({
                "success": True, 
                "message": f"Biznis je uspešno razmrznut. Novi rok pristupa: {new_access_days} dana"
            })
        else:
            return JSONResponse({"success": False, "error": "Greška pri razmrznavanju"}, status_code=500)
            
    except Exception as e:
        return JSONResponse({"success": False, "error": str(e)}, status_code=500)

@app.post("/admin/businesses/suspend")
async def admin_suspend_business(
    request: Request,
    session: Session = Depends(get_session)
):
    """Приостанавливает бизнес"""
    admin = get_current_admin(request)
    if not admin:
        return JSONResponse({"success": False, "error": "Unauthorized"}, status_code=401)
    
    try:
        # Получаем данные из JSON
        data = await request.json()
        business_id = data.get("business_id")
        
        if not business_id:
            return JSONResponse({"success": False, "error": "Business ID is required"}, status_code=400)
        
        # Проверяем, что бизнес существует и активен
        business = session.get(Business, business_id)
        if not business:
            return JSONResponse({"success": False, "error": "Biznis nije pronađen"}, status_code=404)
        
        if business.status != BusinessStatus.ACTIVE:
            return JSONResponse({"success": False, "error": "Biznis nije aktivan"}, status_code=400)
        
        # Приостанавливаем бизнес
        success = suspend_business(session, business_id)
        
        if success:
            # Отправляем уведомления
            send_suspend_notification(
                business.email,
                business.business_name,
                admin_email="admin@lovacrm.com"
            )
            
            # Выводим информацию в консоль
            print("=" * 60)
            print("⚠️ BIZNIS SUSPENDOVAN!")
            print(f"📧 Email: {business.email}")
            print(f"🏢 Naziv: {business.business_name}")
            print("=" * 60)
            
            return JSONResponse({
                "success": True, 
                "message": "Biznis je uspešno suspendovan"
            })
        else:
            return JSONResponse({"success": False, "error": "Greška pri suspendovanju"}, status_code=500)
            
    except Exception as e:
        return JSONResponse({"success": False, "error": str(e)}, status_code=500)

@app.get("/admin/businesses/{business_id}/contacts")
async def admin_get_business_contacts(
    business_id: int,
    request: Request,
    session: Session = Depends(get_session)
):
    """Получить список клиентов бизнеса для админки"""
    admin = get_current_admin(request)
    if not admin:
        return JSONResponse({"success": False, "error": "Unauthorized"}, status_code=401)
    
    try:
        # Проверяем, что бизнес существует
        business = session.get(Business, business_id)
        if not business:
            return JSONResponse({"success": False, "error": "Biznis nije pronađen"}, status_code=404)
        
        # Получаем всех клиентов бизнеса
        contacts = session.exec(select(Contact).where(Contact.business_id == business_id)).all()
        
        # Получаем статистику по резервациям для каждого клиента
        contacts_data = []
        for contact in contacts:
            # Подсчитываем количество резерваций
            bookings_count = len(session.exec(
                select(Booking).where(Booking.contact_id == contact.id)
            ).all())
            
            contacts_data.append({
                "id": contact.id,
                "first_name": contact.first_name,
                "last_name": contact.last_name,
                "email": contact.email,
                "phone": contact.phone,
                "bookings_count": bookings_count,
                "created_at": contact.created_at.isoformat() if contact.created_at else None
            })
        
        return JSONResponse({
            "success": True,
            "contacts": contacts_data,
            "total": len(contacts_data)
        })
        
    except Exception as e:
        return JSONResponse({"success": False, "error": str(e)}, status_code=500)

@app.delete("/admin/contacts/{contact_id}")
async def admin_delete_contact(
    contact_id: int,
    request: Request,
    session: Session = Depends(get_session)
):
    """Удалить клиента и все его резервации (каскадное удаление)"""
    admin = get_current_admin(request)
    if not admin:
        return JSONResponse({"success": False, "error": "Unauthorized"}, status_code=401)
    
    try:
        # Получаем клиента
        contact = session.get(Contact, contact_id)
        if not contact:
            return JSONResponse({"success": False, "error": "Klijent nije pronađen"}, status_code=404)
        
        # Получаем все резервации клиента
        bookings = session.exec(
            select(Booking).where(Booking.contact_id == contact_id)
        ).all()
        
        bookings_count = len(bookings)
        
        # Удаляем все резервации
        for booking in bookings:
            session.delete(booking)
        
        # Удаляем самого клиента
        session.delete(contact)
        
        # Сохраняем изменения
        session.commit()
        
        print(f"🗑️ Klijent obrisan: {contact.first_name} {contact.last_name or ''} (ID: {contact_id})")
        print(f"   Obrisano rezervacija: {bookings_count}")
        
        return JSONResponse({
            "success": True,
            "message": f"Klijent i {bookings_count} rezervacija su uspešno obrisani",
            "deleted_bookings": bookings_count
        })
        
    except Exception as e:
        session.rollback()
        print(f"❌ Greška pri brisanju klijenta: {str(e)}")
        return JSONResponse({"success": False, "error": str(e)}, status_code=500)

@app.post("/admin/businesses/{business_id}/unsuspend")
async def admin_unsuspend_business(
    business_id: int,
    request: Request,
    session: Session = Depends(get_session)
):
    """Возобновляет приостановленный бизнес"""
    admin = get_current_admin(request)
    if not admin:
        return JSONResponse({"success": False, "error": "Unauthorized"}, status_code=401)
    
    try:
        # Проверяем, что бизнес существует и приостановлен
        business = session.get(Business, business_id)
        if not business:
            return JSONResponse({"success": False, "error": "Biznis nije pronađen"}, status_code=404)
        
        if business.status != BusinessStatus.SUSPENDED:
            return JSONResponse({"success": False, "error": "Biznis nije suspendovan"}, status_code=400)
        
        # Активируем бизнес с доступом на 30 дней по умолчанию
        from app.auth import activate_business
        admin_id = admin.get("id") if isinstance(admin, dict) else admin.id
        success = activate_business(session, business_id, access_days=30, assigned_admin_id=admin_id)
        
        if success:
            # Обновляем информацию о бизнесе
            session.refresh(business)
            
            # Отправляем уведомление о возобновлении
            try:
                from app.email_service import send_notification_email
                subject = "✅ Biznis je aktiviran - LovaCRM"
                message = f"""
                Zdravo, {business.business_name}!
                
                ✅ DOBRA VEST: Vaš biznis je ponovo aktiviran!
                
                Detalji:
                📧 Email: {business.email}
                🏢 Naziv biznisa: {business.business_name}
                📅 Pristup do: {business.access_end_date.strftime('%Y-%m-%d %H:%M') if business.access_end_date else 'N/A'}
                
                Možete se ponovo prijaviti na sistem i koristiti sve funkcije.
                
                Sa poštovanjem,
                Tim LovaCRM
                """
                send_notification_email(
                    to_email=business.email,
                    subject=subject,
                    message=message,
                    notification_type="success"
                )
            except Exception as email_error:
                print(f"❌ Greška pri slanju email-a: {str(email_error)}")
            
            # Выводим информацию в консоль
            print("=" * 60)
            print("✅ BIZNIS AKTIVIRAN!")
            print(f"📧 Email: {business.email}")
            print(f"🏢 Naziv: {business.business_name}")
            print(f"📅 Pristup do: {business.access_end_date.strftime('%Y-%m-%d %H:%M') if business.access_end_date else 'N/A'}")
            print("=" * 60)
            
            return JSONResponse({
                "success": True, 
                "message": "Biznis je uspešno aktiviran"
            })
        else:
            return JSONResponse({"success": False, "error": "Greška pri aktivaciji"}, status_code=500)
            
    except Exception as e:
        print(f"❌ Error in unsuspend: {str(e)}")
        return JSONResponse({"success": False, "error": str(e)}, status_code=500)

# API маршруты для тегов и редактирования клиентов
@app.get("/api/tags/all")
async def get_all_tags(session: Session = Depends(get_session)):
    """Получает все существующие теги"""
    try:
        # Получаем все теги из всех клиентов
        contacts = session.exec(select(Contact)).all()
        all_tags = set()
        
        for contact in contacts:
            if contact.preferences and isinstance(contact.preferences, dict):
                tags = contact.preferences.get('tags', [])
                if isinstance(tags, list):
                    all_tags.update(tags)
        
        return {"success": True, "tags": list(all_tags)}
    except Exception as e:
        return {"success": False, "message": f"Error getting tags: {str(e)}"}

@app.post("/clients/{contact_id}/add-tag")
async def add_tag_to_client(
    contact_id: int, 
    request: Request, 
    session: Session = Depends(get_session)
):
    """Добавляет тег к клиенту"""
    user = get_current_user(request)
    if not user:
        return {"success": False, "message": "Not authenticated"}
    
    business_id = user.get("business_id")
    if not business_id:
        return {"success": False, "message": "No business ID"}
    
    try:
        # Получаем данные из JSON
        data = await request.json()
        print(f"DEBUG: Add tag received data: {data}")
        tag = data.get("tag", "").strip()
        print(f"DEBUG: Extracted tag: '{tag}'")
        
        if not tag:
            return {"success": False, "message": "Tag is required"}
        
        # Находим клиента
        contact = session.get(Contact, contact_id)
        if not contact or contact.business_id != business_id:
            return {"success": False, "message": "Contact not found"}
        
        # Получаем существующие теги
        preferences = contact.preferences or {}
        print(f"DEBUG: Current preferences: {preferences}")
        tags = preferences.get('tags', [])
        print(f"DEBUG: Current tags: {tags}")
        
        # Добавляем новый тег, если его еще нет
        if tag not in tags:
            tags.append(tag)
            print(f"DEBUG: Updated tags: {tags}")
            preferences['tags'] = tags
            print(f"DEBUG: Updated preferences: {preferences}")
            
            # Используем прямой SQL запрос для обновления JSON поля
            import json
            preferences_json = json.dumps(preferences, ensure_ascii=False)
            print(f"DEBUG: JSON to save: {preferences_json}")
            
            # Выполняем SQL UPDATE напрямую
            from sqlalchemy import text
            result = session.execute(
                text("UPDATE contact SET preferences = :preferences, updated_at = :updated_at WHERE id = :contact_id"),
                {
                    "preferences": preferences_json,
                    "updated_at": datetime.utcnow(),
                    "contact_id": contact_id
                }
            )
            session.commit()
            
            # Проверяем, что сохранилось в базе данных
            session.refresh(contact)
            print(f"DEBUG: After commit and refresh - contact.preferences: {contact.preferences}")
            
            print(f"DEBUG: Tag '{tag}' added successfully to contact {contact_id}")
            print(f"DEBUG: Final preferences: {contact.preferences}")
            
            return {"success": True, "message": "Tag added successfully"}
        else:
            return {"success": False, "message": "Tag already exists"}
            
    except Exception as e:
        session.rollback()
        return {"success": False, "message": f"Error adding tag: {str(e)}"}

@app.post("/api/contacts/{contact_id}/update")
async def update_contact(
    contact_id: int,
    request: Request,
    session: Session = Depends(get_session)
):
    """Обновляет данные клиента"""
    # Проверяем подписку
    subscription_check = check_subscription_in_api(request, session)
    if subscription_check:
        return subscription_check
    
    user = get_current_user(request)
    if not user:
        return {"success": False, "message": "Not authenticated"}
    
    business_id = user.get("business_id")
    if not business_id:
        return {"success": False, "message": "No business ID"}
    
    try:
        # Получаем данные из JSON
        data = await request.json()
        print(f"DEBUG: Received data: {data}")
        
        # Находим клиента
        contact = session.get(Contact, contact_id)
        if not contact or contact.business_id != business_id:
            return {"success": False, "message": "Contact not found"}
        
        # Обновляем поля
        if 'first_name' in data:
            contact.first_name = data['first_name']
        if 'last_name' in data:
            contact.last_name = data['last_name']
        if 'phone' in data:
            contact.phone = data['phone']
        if 'email' in data:
            contact.email = data['email']
        if 'instagram_handle' in data:
            contact.instagram_handle = data['instagram_handle']
        if 'nickname' in data:
            contact.nickname = data['nickname']
        if 'gender' in data:
            contact.gender = data['gender']
        if 'city' in data:
            contact.city = data['city']
        if 'birth_date' in data:
            if data['birth_date']:
                try:
                    # Конвертируем строку в объект date
                    contact.birth_date = datetime.strptime(data['birth_date'], '%Y-%m-%d').date()
                except ValueError:
                    return {"success": False, "message": "Invalid date format. Expected YYYY-MM-DD"}
            else:
                contact.birth_date = None
        if 'preferences' in data:
            contact.preferences = data['preferences']
        
        # Обработка отдельных полей preferences
        if 'preferences_text' in data:
            if not contact.preferences:
                contact.preferences = {}
            # Сохраняем существующие значения
            existing_preferences = contact.preferences.copy()
            existing_preferences['preferences_text'] = data['preferences_text']
            contact.preferences = existing_preferences
            print(f"DEBUG: Updated preferences_text: {data['preferences_text']}")
        
        if 'communication_method' in data:
            if not contact.preferences:
                contact.preferences = {}
            # Сохраняем существующие значения
            existing_preferences = contact.preferences.copy()
            existing_preferences['communication_method'] = data['communication_method']
            contact.preferences = existing_preferences
            print(f"DEBUG: Updated communication_method: {data['communication_method']}")
        
        if 'promoter_name' in data:
            if not contact.preferences:
                contact.preferences = {}
            # Сохраняем существующие значения
            existing_preferences = contact.preferences.copy()
            existing_preferences['promoter_name'] = data['promoter_name']
            contact.preferences = existing_preferences
            print(f"DEBUG: Updated promoter_name: {data['promoter_name']}")
        
        if 'rating' in data:
            contact.rating = data['rating']
        
        contact.updated_at = datetime.utcnow()
        
        print(f"DEBUG: Final preferences: {contact.preferences}")
        
        session.add(contact)
        session.commit()
        
        return {"success": True, "message": "Contact updated successfully"}
        
    except Exception as e:
        session.rollback()
        return {"success": False, "message": f"Error updating contact: {str(e)}"}

@app.get("/api/contacts/{contact_id}/get-preferences")
async def get_contact_preferences(
    contact_id: int,
    request: Request,
    session: Session = Depends(get_session)
):
    """Получает preferences клиента"""
    user = get_current_user(request)
    if not user:
        return {"success": False, "message": "Not authenticated"}
    
    business_id = user.get("business_id")
    if not business_id:
        return {"success": False, "message": "No business ID"}
    
    try:
        contact = session.get(Contact, contact_id)
        if not contact or contact.business_id != business_id:
            return {"success": False, "message": "Contact not found"}
        
        return {"success": True, "preferences": contact.preferences or {}}
        
    except Exception as e:
        return {"success": False, "message": f"Error getting preferences: {str(e)}"}

@app.get("/api/contacts/find")
async def find_contact_by_name_and_phone(
    name: str,
    phone: str,
    request: Request,
    session: Session = Depends(get_session)
):
    """Находит клиента по имени и телефону"""
    user = get_current_user(request)
    if not user:
        return {"success": False, "message": "Not authenticated"}
    
    business_id = user.get("business_id")
    if not business_id:
        return {"success": False, "message": "No business ID"}
    
    try:
        print(f"DEBUG: Searching for contact with name: '{name}', phone: '{phone}', business_id: {business_id}")
        
        # Ищем клиента по имени и телефону
        contact = session.query(Contact).filter(
            Contact.business_id == business_id,
            Contact.first_name.ilike(f"%{name}%"),
            Contact.phone == phone
        ).first()
        
        if contact:
            print(f"DEBUG: Contact found with ID: {contact.id}")
            return {"success": True, "contact_id": contact.id}
        else:
            print(f"DEBUG: Contact not found")
            return {"success": False, "message": "Contact not found"}
            
    except Exception as e:
        return {"success": False, "message": f"Error finding contact: {str(e)}"}

@app.post("/api/contacts/create")
async def create_contact(
    request: Request,
    session: Session = Depends(get_session)
):
    """Создает нового клиента"""
    # Проверяем подписку
    subscription_check = check_subscription_in_api(request, session)
    if subscription_check:
        return subscription_check
    
    user = get_current_user(request)
    if not user:
        return {"success": False, "message": "Not authenticated"}
    
    business_id = user.get("business_id")
    if not business_id:
        return {"success": False, "message": "No business ID"}
    
    try:
        # Получаем данные из JSON
        data = await request.json()
        print(f"DEBUG: Creating contact with data: {data}")
        
        # Извлекаем данные
        first_name = data.get("first_name", "").strip()
        phone = data.get("phone", "").strip()
        
        if not first_name or not phone:
            return {"success": False, "message": "First name and phone are required"}
        
        # Создаем нового клиента
        contact = Contact(
            first_name=first_name,
            phone=phone,
            business_id=business_id,
            created_at=datetime.utcnow()
        )
        
        session.add(contact)
        session.commit()
        session.refresh(contact)
        
        
        print(f"DEBUG: Contact created successfully with ID: {contact.id}")
        return {"success": True, "contact_id": contact.id}
        
    except Exception as e:
        session.rollback()
        return {"success": False, "message": f"Error creating contact: {str(e)}"}

@app.post("/api/bookings/new")
async def create_new_booking(
    request: Request,
    session: Session = Depends(get_session)
):
    """Создает новую резервацию"""
    # Проверяем подписку
    subscription_check = check_subscription_in_api(request, session)
    if subscription_check:
        return subscription_check
    
    user = get_current_user(request)
    if not user:
        return {"success": False, "message": "Not authenticated"}
    
    business_id = user.get("business_id")
    if not business_id:
        return {"success": False, "message": "No business ID"}
    
    try:
        # Получаем данные из JSON
        data = await request.json()
        print(f"DEBUG: Received booking data: {data}")
        
        # Извлекаем данные
        contact_id = data.get("contact_id")
        status = data.get("status", "dogovoreno")
        party_size = data.get("party_size", 1)
        table_type = data.get("table_type", "")
        date_str = data.get("date")
        special_case_note = data.get("special_case_note") or data.get("specialOccasion") or ""
        time_from = data.get("time_from", "")
        time_to = data.get("time_to", "")
        comment = data.get("comment", "")
        males_count = data.get("males_count")
        females_count = data.get("females_count")
        initial_check_rsd = data.get("initial_check_rsd")
        final_check_rsd = data.get("final_check_rsd")
        
        # Проверяем обязательные поля
        if not contact_id:
            return {"success": False, "message": "Contact ID is required"}
        if not date_str:
            return {"success": False, "message": "Date is required"}
        if not time_from:
            return {"success": False, "message": "Time is required"}
        
        # Проверяем, что клиент принадлежит текущему бизнесу
        contact = session.get(Contact, contact_id)
        if not contact or contact.business_id != business_id:
            return {"success": False, "message": "Contact not found"}
        
        # Парсим дату
        try:
            booking_date = datetime.strptime(date_str, "%Y-%m-%d").date()
        except ValueError:
            return {"success": False, "message": "Invalid date format. Expected YYYY-MM-DD"}
        
        # Парсим время
        try:
            time_from_obj = datetime.strptime(time_from, "%H:%M").time()
        except ValueError:
            return {"success": False, "message": "Invalid time format. Expected HH:MM"}
        
        # Парсим время окончания (если указано)
        time_to_obj = None
        if time_to:
            try:
                time_to_obj = datetime.strptime(time_to, "%H:%M").time()
            except ValueError:
                return {"success": False, "message": "Invalid time_to format. Expected HH:MM"}
        
        # Парсим дату окончания для ночных резерваций
        end_date_obj = None
        end_date_str = data.get("end_date")
        if end_date_str:
            try:
                end_date_obj = datetime.strptime(end_date_str, "%Y-%m-%d").date()
            except ValueError:
                return {"success": False, "message": "Invalid end_date format. Expected YYYY-MM-DD"}
        
        # Создаем новую резервацию
        booking = Booking(
            contact_id=contact_id,
            status=status,
            party_size=party_size,
            table_type=table_type,
            date=booking_date,
            time_from=time_from_obj,
            time_to=time_to_obj,
            end_date=end_date_obj,
            special_case_note=special_case_note,
            comment=comment,
            males_count=males_count if males_count is not None else None,
            females_count=females_count if females_count is not None else None,
            initial_check_rsd=initial_check_rsd if initial_check_rsd is not None else None,
            final_check_rsd=final_check_rsd if final_check_rsd is not None else None,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow()
        )
        
        session.add(booking)
        session.commit()
        session.refresh(booking)
        
        
        print(f"DEBUG: Booking created successfully with ID: {booking.id}")
        return {"success": True, "message": "Booking created successfully", "booking_id": booking.id}
        
    except Exception as e:
        session.rollback()
        return {"success": False, "message": f"Error creating booking: {str(e)}"}

@app.get("/api/bookings/{booking_id}")
async def get_booking(booking_id: int, request: Request, session: Session = Depends(get_session)):
    user = get_current_user(request)
    if not user:
        return {"success": False, "error": "Unauthorized"}

    booking = session.get(Booking, booking_id)
    if not booking:
        return {"success": False, "error": "Booking not found"}

    contact = session.get(Contact, booking.contact_id)

    def fmt_time(t):
        return t.strftime("%H:%M") if t else None

    return {
        "success": True,
        "booking": {
            "id": booking.id,
            "date": booking.date.isoformat() if booking.date else None,
            "time_from": fmt_time(booking.time_from),
            "time_to": None,
            "party_size": booking.party_size,
            "table_type": booking.table_type,
            "status": booking.status,
            "special_case_note": booking.special_case_note,
            "comment": booking.comment,
            "males_count": booking.males_count,
            "females_count": booking.females_count,
            "initial_check_rsd": booking.initial_check_rsd,
            "final_check_rsd": booking.final_check_rsd,
            "contact": {
                "id": contact.id if contact else None,
                "first_name": contact.first_name if contact else None,
                "last_name": contact.last_name if contact else None,
                "phone": contact.phone if contact else None,
            },
        },
    }

@app.post("/api/bookings/{booking_id}/update")
async def update_booking_api(
    booking_id: int,
    request: Request,
    session: Session = Depends(get_session),
):
    # Проверяем подписку
    subscription_check = check_subscription_in_api(request, session)
    if subscription_check:
        return subscription_check
    
    user = get_current_user(request)
    if not user:
        return {"success": False, "error": "Unauthorized"}

    booking = session.get(Booking, booking_id)
    if not booking:
        return {"success": False, "error": "Booking not found"}

    try:
        data = await request.json()
        print(f"DEBUG: Update booking {booking_id} with data: {data}")
        
        if "date" in data and data["date"]:
            try:
                booking.date = datetime.strptime(data["date"], "%Y-%m-%d").date()
            except ValueError:
                return {"success": False, "error": "Invalid date format. Expected YYYY-MM-DD"}
        if "time_from" in data and data["time_from"]:
            try:
                booking.time_from = datetime.strptime(data["time_from"], "%H:%M").time()
            except ValueError:
                return {"success": False, "error": "Invalid time format. Expected HH:MM"}
        if "party_size" in data:
            try:
                booking.party_size = int(data["party_size"]) if data["party_size"] is not None else None
            except (TypeError, ValueError):
                return {"success": False, "error": "Invalid party_size"}
        if "table_type" in data:
            booking.table_type = data["table_type"] or None
        if "special_case_note" in data or "occasion" in data or "specialOccasion" in data:
            booking.special_case_note = data.get("special_case_note") or data.get("occasion") or data.get("specialOccasion") or None
        if "comment" in data:
            booking.comment = data["comment"] or None
        if "status" in data and data["status"]:
            booking.status = data["status"]
        if "males_count" in data:
            booking.males_count = int(data["males_count"]) if data["males_count"] is not None else None
        if "females_count" in data:
            booking.females_count = int(data["females_count"]) if data["females_count"] is not None else None
        if "initial_check_rsd" in data:
            booking.initial_check_rsd = float(data["initial_check_rsd"]) if data["initial_check_rsd"] is not None else None
        if "final_check_rsd" in data:
            booking.final_check_rsd = float(data["final_check_rsd"]) if data["final_check_rsd"] is not None else None

        booking.updated_at = datetime.utcnow()
        session.add(booking)
        session.commit()
        
        print(f"DEBUG: Booking {booking_id} updated successfully")
        return {"success": True}
    except Exception as e:
        session.rollback()
        return {"success": False, "error": str(e)}

@app.post("/bookings/{booking_id}/update-status")
async def update_booking_status(
    request: Request,
    booking_id: int,
    session: Session = Depends(get_session)
):
    user = get_current_user(request)
    if not user:
        return {"success": False, "error": "Unauthorized"}

    booking = session.get(Booking, booking_id)
    if not booking:
        return {"success": False, "error": "Booking not found"}

    try:
        body = await request.json()
        new_status = body.get("status")

        if not new_status:
            return {"success": False, "error": "Status is required"}

        booking.status = new_status
        booking.updated_at = _datetime.utcnow()
        session.add(booking)
        session.commit()

        return {"success": True}
    except Exception as e:
        session.rollback()
        return {"success": False, "error": str(e)}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)

