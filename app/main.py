from fastapi import FastAPI, Request, Form, Depends
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.sessions import SessionMiddleware
from starlette.templating import Jinja2Templates
from app.config import settings
from app.db import create_db_and_tables
from app.db import get_session
from sqlmodel import select, update
from sqlmodel import Session
from app.models import Contact, Booking, BookingStatus
from datetime import date as _date, datetime as _datetime, time as _time
import json

app = FastAPI(title=settings.app_name)
app.add_middleware(SessionMiddleware, secret_key=settings.secret_key, session_cookie=settings.session_cookie_name)

app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")


def get_current_user(request: Request):
    return request.session.get("user")


@app.on_event("startup")
def on_startup() -> None:
    create_db_and_tables()


@app.get("/", response_class=HTMLResponse)
async def root(request: Request):
    user = get_current_user(request)
    if not user:
        return RedirectResponse(url="/login", status_code=302)
    return RedirectResponse(url="/dashboard", status_code=302)


@app.get("/login", response_class=HTMLResponse)
async def login_page(request: Request):
    return templates.TemplateResponse("login.html", {"request": request, "title": "Login"})


@app.post("/login")
async def login(request: Request, username: str = Form(...), password: str = Form(...)):
    if username == settings.single_username and password == settings.single_password:
        request.session["user"] = {"username": username}
        return RedirectResponse(url="/dashboard", status_code=302)
    return templates.TemplateResponse("login.html", {"request": request, "title": "Login", "error": "Invalid credentials"}, status_code=400)


@app.get("/register", response_class=HTMLResponse)
async def register_page(request: Request):
    return templates.TemplateResponse("register.html", {"request": request, "title": "Registracija"})


@app.post("/register")
async def register(
    request: Request,
    name: str = Form(...),
    email: str = Form(None),
    phone: str = Form(None),
    password: str = Form(...),
    confirm_password: str = Form(...),
    address: str = Form(None),
    language: str = Form(None),
    currency: str = Form(None)
):
    # Проверяем совпадение паролей
    if password != confirm_password:
        return templates.TemplateResponse("register.html", {
            "request": request,
            "title": "Registracija",
            "error": "Lozinke se ne poklapaju"
        }, status_code=400)
    
    # Здесь можно добавить логику обработки регистрации
    # Пока просто перенаправляем на страницу входа
    return RedirectResponse(url="/login?message=registration_success", status_code=302)


@app.get("/logout")
async def logout(request: Request):
    request.session.clear()
    return RedirectResponse(url="/login", status_code=302)


@app.get("/dashboard", response_class=HTMLResponse)
async def dashboard(request: Request, session: Session = Depends(get_session)):
    user = get_current_user(request)
    if not user:
        return RedirectResponse(url="/login", status_code=302)
    
    # Получаем контакты и статистику как в clients
    contacts = session.exec(select(Contact).order_by(Contact.created_at.desc())).all()
    
    # Load all bookings needed for stats per contact
    all_bookings = session.exec(select(Booking)).all()
    # Precompute grouped stats
    bookings_by_contact = {}
    for b in all_bookings:
        bookings_by_contact.setdefault(b.contact_id, []).append(b)
    client_stats = {}
    month_names = {
        1: "Januar", 2: "Februar", 3: "Mart", 4: "April", 5: "Maj", 6: "Jun",
        7: "Jul", 8: "Avgust", 9: "Septembar", 10: "Oktobar", 11: "Novembar", 12: "Decembar"
    }
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
            if b.status in (BookingStatus.POTVRDJENO, "potvrđeno", "potvrdjeno"):
                visits_confirmed += 1
            if b.spend_eur is not None:
                spends.append(b.spend_eur)
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
    
    # Создаем ответ с заголовками для предотвращения кэширования
    response = templates.TemplateResponse("dashboard.html", {
        "request": request, 
        "title": "CRM", 
        "user": user,
        "contacts": contacts,
        "client_stats": client_stats
    })
    
    # Добавляем заголовки для предотвращения кэширования
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Pragma"] = "no-cache"
    response.headers["Expires"] = "0"
    
    return response


@app.get("/booking", response_class=HTMLResponse)
async def booking_page(request: Request, session: Session = Depends(get_session)):
    user = get_current_user(request)
    if not user:
        return RedirectResponse(url="/login", status_code=302)
    # Получаем дату из query, по умолчанию сегодня
    query_params = dict(request.query_params)
    date_str = query_params.get("date")
    try:
        selected_date = _datetime.strptime(date_str, "%Y-%m-%d").date() if date_str else _date.today()
    except Exception:
        selected_date = _date.today()
    bookings = session.exec(select(Booking).where(Booking.date == selected_date).order_by(Booking.time_from)).all()
    # Для отображения имени клиента загрузим карту id->Contact
    contact_ids = {b.contact_id for b in bookings}
    contacts_map = {}
    if contact_ids:
        contacts = session.exec(select(Contact).where(Contact.id.in_(contact_ids))).all()
        contacts_map = {c.id: c for c in contacts}
    
    # Получаем контакты и статистику для поиска как в dashboard
    all_contacts = session.exec(select(Contact).order_by(Contact.created_at.desc())).all()
    
    # Load all bookings needed for stats per contact
    all_bookings = session.exec(select(Booking)).all()
    # Precompute grouped stats
    bookings_by_contact = {}
    for b in all_bookings:
        bookings_by_contact.setdefault(b.contact_id, []).append(b)
    client_stats = {}
    month_names = {
        1: "Januar", 2: "Februar", 3: "Mart", 4: "April", 5: "Maj", 6: "Jun",
        7: "Jul", 8: "Avgust", 9: "Septembar", 10: "Oktobar", 11: "Novembar", 12: "Decembar"
    }
    for c in all_contacts:
        lst = bookings_by_contact.get(c.id, [])
        last_visit = None
        last_booking_status = None
        visits_confirmed = 0
        spends = []
        for b in lst:
            if last_visit is None or (b.date, b.time_from) > (last_visit[0], last_visit[1] if last_visit[1] else b.time_from):
                last_visit = (b.date, b.time_from)
                last_booking_status = b.status
            if b.status in (BookingStatus.POTVRDJENO, "potvrđeno", "potvrdjeno"):
                visits_confirmed += 1
            if b.spend_eur is not None:
                spends.append(b.spend_eur)
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
    
    return templates.TemplateResponse(
        "booking.html",
        {
            "request": request,
            "title": "Booking",
            "user": user,
            "bookings": bookings,
            "contacts_map": contacts_map,
            "selected_date": selected_date,
            "contacts": all_contacts,
            "client_stats": client_stats
        },
    )


@app.get("/clients", response_class=HTMLResponse)
async def clients_page(request: Request, session: Session = Depends(get_session)):
    user = get_current_user(request)
    if not user:
        return RedirectResponse(url="/login", status_code=302)
    contacts = session.exec(select(Contact).order_by(Contact.created_at.desc())).all()
    
    # Debug: проверим, есть ли теги у клиентов
    for contact in contacts:
        if contact.preferences and contact.preferences.get('tags'):
            print(f"Client {contact.id} ({contact.first_name}) has tags: {contact.preferences.get('tags')}")
    # Load all bookings needed for stats per contact
    all_bookings = session.exec(select(Booking)).all()
    # Precompute grouped stats
    bookings_by_contact = {}
    for b in all_bookings:
        bookings_by_contact.setdefault(b.contact_id, []).append(b)
    stats = {}
    month_names = {
        1: "Januar", 2: "Februar", 3: "Mart", 4: "April", 5: "Maj", 6: "Jun",
        7: "Jul", 8: "Avgust", 9: "Septembar", 10: "Oktobar", 11: "Novembar", 12: "Decembar"
    }
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
            if b.status in (BookingStatus.POTVRDJENO, "potvrđeno", "potvrdjeno"):
                visits_confirmed += 1
            if b.spend_eur is not None:
                spends.append(b.spend_eur)
        avg_spend = (sum(spends) / len(spends)) if spends else None
        last_visit_str = None
        if last_visit is not None:
            d, t = last_visit
            month_name = month_names.get(d.month, str(d.month))
            last_visit_str = f"{d.day}. {month_name} {d.year} | {t.strftime('%H:%M')}"
        stats[c.id] = {
            "last_visit": last_visit[0].isoformat() if last_visit else None,
            "last_visit_str": last_visit_str,
            "last_booking_status": last_booking_status,
            "visits_confirmed": visits_confirmed,
            "avg_spend": avg_spend,
        }
    
    # Создаем ответ с заголовками для предотвращения кэширования
    response = templates.TemplateResponse("clients.html", {
        "request": request, 
        "title": "Klijenti", 
        "user": user, 
        "contacts": contacts, 
        "client_stats": stats
    })
    
    # Добавляем заголовки для предотвращения кэширования
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Pragma"] = "no-cache"
    response.headers["Expires"] = "0"
    
    return response


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
    
    # Находим максимальный номер клиента среди всех клиентов с именем "Klijent №X"
    contacts = session.exec(select(Contact).where(Contact.first_name.like("Klijent №%"))).all()
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
    contact = session.get(Contact, contact_id)
    if not contact:
        return RedirectResponse(url="/clients", status_code=302)
    
    # Логируем данные контакта для отладки
    print(f"Loading contact {contact_id}:")
    print(f"  First name: {contact.first_name}")
    print(f"  Last name: {contact.last_name}")
    print(f"  Email: {contact.email}")
    print(f"  Gender: {contact.gender}")
    print(f"  Preferences: {contact.preferences}")
    print(f"  Updated at: {contact.updated_at}")
    
    bookings = session.exec(select(Booking).where(Booking.contact_id == contact_id).order_by(Booking.date.desc(), Booking.time_from.desc())).all()
    visits_count = len(bookings)
    total_spent = sum([b.spend_eur or 0 for b in bookings if b.spend_eur])
    rating = contact.rating or 0
    
    # Получаем всех клиентов для поиска
    all_contacts = session.exec(select(Contact).order_by(Contact.created_at.desc())).all()
    all_bookings = session.exec(select(Booking)).all()
    
    # Группируем резервации по клиентам
    bookings_by_contact = {}
    for b in all_bookings:
        bookings_by_contact.setdefault(b.contact_id, []).append(b)
    
    # Статистика для всех клиентов
    month_names = {
        1: "Januar", 2: "Februar", 3: "Mart", 4: "April", 5: "Maj", 6: "Jun",
        7: "Jul", 8: "Avgust", 9: "Septembar", 10: "Oktobar", 11: "Novembar", 12: "Decembar"
    }
    all_client_stats = {}
    for c in all_contacts:
        lst = bookings_by_contact.get(c.id, [])
        last_visit = None
        last_booking_status = None
        visits_confirmed = 0
        spends = []
        for b in lst:
            if last_visit is None or (b.date, b.time_from) > (last_visit[0], last_visit[1] if last_visit[1] else b.time_from):
                last_visit = (b.date, b.time_from)
                last_booking_status = b.status
            if b.status in (BookingStatus.POTVRDJENO, "potvrđeno", "potvrdjeno"):
                visits_confirmed += 1
            if b.spend_eur is not None:
                spends.append(b.spend_eur)
        avg_spend = (sum(spends) / len(spends)) if spends else None
        last_visit_str = None
        if last_visit is not None:
            d, t = last_visit
            month_name = month_names.get(d.month, str(d.month))
            last_visit_str = f"{d.day}. {month_name} {d.year} | {t.strftime('%H:%M')}"
        all_client_stats[c.id] = {
            "last_visit": last_visit[0].isoformat() if last_visit else None,
            "last_visit_str": last_visit_str,
            "last_booking_status": last_booking_status,
            "visits_confirmed": visits_confirmed,
            "avg_spend": avg_spend,
        }
    
    return templates.TemplateResponse(
        "client_detail.html",
        {
            "request": request,
            "title": f"Klijent {contact.first_name}",
            "user": user,
            "contact": contact,
            "bookings": bookings,
            "visits_count": visits_count,
            "total_spent": total_spent,
            "rating": rating,
            "all_contacts": all_contacts,
            "all_client_stats": all_client_stats,
        },
    )


@app.get("/clients/{contact_id}/edit", response_class=HTMLResponse)
async def client_edit_form(request: Request, contact_id: int, session: Session = Depends(get_session)):
    user = get_current_user(request)
    if not user:
        return RedirectResponse(url="/login", status_code=302)
    contact = session.get(Contact, contact_id)
    if not contact:
        return RedirectResponse(url="/clients", status_code=302)
    return templates.TemplateResponse(
        "client_edit.html",
        {"request": request, "title": "Uredi klijenta", "user": user, "contact": contact},
    )


@app.post("/clients/{contact_id}/edit")
async def client_edit(
    request: Request,
    contact_id: int,
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
    contact = session.get(Contact, contact_id)
    if not contact:
        return RedirectResponse(url="/clients", status_code=302)
    contact.first_name = first_name
    contact.last_name = last_name
    contact.phone = phone
    contact.email = email
    contact.instagram_handle = instagram_handle
    contact.nickname = nickname
    contact.gender = gender
    contact.city = city
    if birth_date:
        try:
            contact.birth_date = _datetime.strptime(birth_date, "%Y-%m-%d").date()
        except Exception:
            pass
    # preferences JSON
    prefs = contact.preferences or {}
    if communication_method is not None:
        prefs["communication_method"] = communication_method or None
    if promoter_name is not None:
        prefs["promoter_name"] = promoter_name or None
    if preferences_text is not None:
        prefs["preferences_text"] = preferences_text or None
    prefs["is_regular"] = True if is_regular else False
    prefs["knows_owner"] = True if knows_owner else False
    contact.preferences = prefs
    if rating is not None and rating != "":
        try:
            contact.rating = int(rating)
        except Exception:
            pass
    contact.updated_at = _datetime.utcnow()
    session.add(contact)
    session.commit()
    session.refresh(contact)
    return RedirectResponse(url=f"/clients/{contact.id}", status_code=302)


@app.get("/map", response_class=HTMLResponse)
async def map_page(request: Request, session: Session = Depends(get_session)):
    user = get_current_user(request)
    if not user:
        return RedirectResponse(url="/login", status_code=302)
    
    # Получаем контакты и статистику для поиска как в dashboard
    all_contacts = session.exec(select(Contact).order_by(Contact.created_at.desc())).all()
    
    # Load all bookings needed for stats per contact
    all_bookings = session.exec(select(Booking)).all()
    # Precompute grouped stats
    bookings_by_contact = {}
    for b in all_bookings:
        bookings_by_contact.setdefault(b.contact_id, []).append(b)
    client_stats = {}
    month_names = {
        1: "Januar", 2: "Februar", 3: "Mart", 4: "April", 5: "Maj", 6: "Jun",
        7: "Jul", 8: "Avgust", 9: "Septembar", 10: "Oktobar", 11: "Novembar", 12: "Decembar"
    }
    for c in all_contacts:
        lst = bookings_by_contact.get(c.id, [])
        last_visit = None
        last_booking_status = None
        visits_confirmed = 0
        spends = []
        for b in lst:
            if last_visit is None or (b.date, b.time_from) > (last_visit[0], last_visit[1] if last_visit[1] else b.time_from):
                last_visit = (b.date, b.time_from)
                last_booking_status = b.status
            if b.status in (BookingStatus.POTVRDJENO, "potvrđeno", "potvrdjeno"):
                visits_confirmed += 1
            if b.spend_eur is not None:
                spends.append(b.spend_eur)
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
    
    return templates.TemplateResponse("map.html", {
        "request": request, 
        "title": "Mapa", 
        "user": user,
        "contacts": all_contacts,
        "client_stats": client_stats
    })


@app.get("/marketing", response_class=HTMLResponse)
async def marketing_page(request: Request, session: Session = Depends(get_session)):
    user = get_current_user(request)
    if not user:
        return RedirectResponse(url="/login", status_code=302)
    
    # Получаем контакты и статистику для поиска как в dashboard
    all_contacts = session.exec(select(Contact).order_by(Contact.created_at.desc())).all()
    
    # Load all bookings needed for stats per contact
    all_bookings = session.exec(select(Booking)).all()
    # Precompute grouped stats
    bookings_by_contact = {}
    for b in all_bookings:
        bookings_by_contact.setdefault(b.contact_id, []).append(b)
    client_stats = {}
    month_names = {
        1: "Januar", 2: "Februar", 3: "Mart", 4: "April", 5: "Maj", 6: "Jun",
        7: "Jul", 8: "Avgust", 9: "Septembar", 10: "Oktobar", 11: "Novembar", 12: "Decembar"
    }
    for c in all_contacts:
        lst = bookings_by_contact.get(c.id, [])
        last_visit = None
        last_booking_status = None
        visits_confirmed = 0
        spends = []
        for b in lst:
            if last_visit is None or (b.date, b.time_from) > (last_visit[0], last_visit[1] if last_visit[1] else b.time_from):
                last_visit = (b.date, b.time_from)
                last_booking_status = b.status
            if b.status in (BookingStatus.POTVRDJENO, "potvrđeno", "potvrdjeno"):
                visits_confirmed += 1
            if b.spend_eur is not None:
                spends.append(b.spend_eur)
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
    
    return templates.TemplateResponse("marketing.html", {
        "request": request, 
        "title": "Marketing", 
        "user": user,
        "contacts": all_contacts,
        "client_stats": client_stats
    })


@app.get("/booking/new", response_class=HTMLResponse)
async def booking_new_form(request: Request, session: Session = Depends(get_session)):
    user = get_current_user(request)
    if not user:
        return RedirectResponse(url="/login", status_code=302)
    contacts = session.exec(select(Contact).order_by(Contact.first_name)).all()
    statuses = [
        (BookingStatus.DOGOVORENO, "dogovoreno"),
        (BookingStatus.POTVRDJENO, "potvrdjeno"),
        (BookingStatus.OTKAZANO, "otkazano"),
        (BookingStatus.WAITLIST, "waitlist"),
        (BookingStatus.DOSAO, "dosao"),
    ]
    return templates.TemplateResponse(
        "booking_form.html",
        {"request": request, "title": "Nova rezervacija", "user": user, "contacts": contacts, "statuses": statuses},
    )


@app.post("/booking/new")
async def booking_create(
    request: Request,
    contact_id: int = Form(...),
    date: str = Form(...),
    time_from: str = Form(...),
    party_size: int = Form(None),
    status: str = Form(BookingStatus.DOGOVORENO),
    table_type: str = Form(None),
    spend_eur: float = Form(None),
    special_case_note: str = Form(None),
    comment: str = Form(None),
    session: Session = Depends(get_session),
):
    user = get_current_user(request)
    if not user:
        return RedirectResponse(url="/login", status_code=302)
    try:
        booking_date = _datetime.strptime(date, "%Y-%m-%d").date()
    except Exception:
        booking_date = _date.today()
    try:
        t = _datetime.strptime(time_from, "%H:%M").time()
    except Exception:
        t = _time(0, 0)
    b = Booking(
        contact_id=contact_id,
        date=booking_date,
        time_from=t,
        party_size=party_size,
        status=status,
        table_type=table_type,
        spend_eur=spend_eur,
        special_case_note=special_case_note,
        comment=comment,
    )
    session.add(b)
    session.commit()
    return RedirectResponse(url=f"/booking?date={booking_date.isoformat()}", status_code=302)


@app.post("/clients/{contact_id}/add-tag")
async def add_tag_to_client(
    request: Request,
    contact_id: int,
    session: Session = Depends(get_session)
):
    user = get_current_user(request)
    if not user:
        return JSONResponse({"success": False, "error": "Unauthorized"}, status_code=401)
    
    contact = session.get(Contact, contact_id)
    if not contact:
        return JSONResponse({"success": False, "error": "Contact not found"}, status_code=404)
    
    try:
        body = await request.json()
        tag = body.get("tag", "").strip()
        
        if not tag:
            return JSONResponse({"success": False, "error": "Tag is required"}, status_code=400)
        
        # Получаем существующие теги
        preferences = contact.preferences or {}
        tags = preferences.get("tags", [])
        
        print(f"Client {contact_id} current preferences: {preferences}")
        print(f"Current tags: {tags}")
        
        # Добавляем новый тег, если его еще нет
        if tag not in tags:
            tags.append(tag)
            preferences["tags"] = tags
            
            # Используем SQL UPDATE для обновления JSON поля
            from sqlalchemy import text
            session.execute(
                text("UPDATE contact SET preferences = :preferences, updated_at = :updated_at WHERE id = :contact_id"),
                {
                    "preferences": json.dumps(preferences),
                    "updated_at": _datetime.utcnow(),
                    "contact_id": contact_id
                }
            )
            session.commit()
            
            print(f"Added tag '{tag}' to client {contact_id}. New preferences: {preferences}")
            
            # Проверим, что тег действительно сохранился
            updated_contact = session.get(Contact, contact_id)
            print(f"Verification - client {contact_id} preferences after save: {updated_contact.preferences}")
        else:
            print(f"Tag '{tag}' already exists for client {contact_id}")
        
        return JSONResponse({"success": True, "tag": tag})
        
    except Exception as e:
        return JSONResponse({"success": False, "error": str(e)}, status_code=500)


@app.post("/clients/{contact_id}/update-field")
async def update_client_field(
    request: Request,
    contact_id: int,
    session: Session = Depends(get_session)
):
    user = get_current_user(request)
    if not user:
        return JSONResponse({"success": False, "error": "Unauthorized"}, status_code=401)
    
    contact = session.get(Contact, contact_id)
    if not contact:
        return JSONResponse({"success": False, "error": "Contact not found"}, status_code=404)
    
    try:
        body = await request.json()
        field = body.get("field")
        value = body.get("value", "").strip()
        
        print(f"Updating field: {field} with value: {value} for contact: {contact_id}")
        
        if not field:
            return JSONResponse({"success": False, "error": "Field is required"}, status_code=400)
        
        # Update the field
        if field == "name":
            # Split name into first and last name
            name_parts = value.strip().split(' ', 1)
            contact.first_name = name_parts[0] if name_parts[0] else None
            contact.last_name = name_parts[1] if len(name_parts) > 1 and name_parts[1] else None
        elif field == "phone":
            contact.phone = value if value else None
        elif field == "email":
            contact.email = value if value else None
        elif field == "birth_date":
            if value:
                try:
                    contact.birth_date = _datetime.strptime(value, "%Y-%m-%d").date()
                except ValueError:
                    return JSONResponse({"success": False, "error": "Invalid date format"}, status_code=400)
            else:
                contact.birth_date = None
        elif field == "gender":
            contact.gender = value if value else None
        elif field == "city":
            contact.city = value if value else None
        elif field == "instagram_handle":
            contact.instagram_handle = value if value else None
        elif field in ["preferences_text", "communication_method", "promoter_name"]:
            # These are in preferences JSON
            preferences = contact.preferences or {}
            print(f"Current preferences: {preferences}")
            preferences[field] = value if value else None
            print(f"Updated preferences: {preferences}")
            
            # Use SQLAlchemy update directly for JSON field
            from sqlalchemy import text
            update_stmt = text("""
                UPDATE contact 
                SET preferences = :preferences, updated_at = :updated_at 
                WHERE id = :contact_id
            """)
            session.execute(update_stmt, {
                "preferences": json.dumps(preferences),
                "updated_at": _datetime.utcnow(),
                "contact_id": contact_id
            })
            print(f"Updated preferences via SQL: {preferences}")
        
        contact.updated_at = _datetime.utcnow()
        session.add(contact)
        session.commit()
        session.refresh(contact)
        
        # Verify the update
        if field in ["preferences_text", "communication_method", "promoter_name"]:
            print(f"Final preferences after commit: {contact.preferences}")
        
        return JSONResponse({"success": True})
        
    except Exception as e:
        return JSONResponse({"success": False, "error": str(e)}, status_code=500)


@app.post("/bookings/{booking_id}/update-status")
async def update_booking_status(
    request: Request,
    booking_id: int,
    session: Session = Depends(get_session)
):
    user = get_current_user(request)
    if not user:
        return JSONResponse({"success": False, "error": "Unauthorized"}, status_code=401)
    
    booking = session.get(Booking, booking_id)
    if not booking:
        return JSONResponse({"success": False, "error": "Booking not found"}, status_code=404)
    
    try:
        body = await request.json()
        new_status = body.get("status")
        
        if not new_status:
            return JSONResponse({"success": False, "error": "Status is required"}, status_code=400)
        
        # Update the booking status
        booking.status = new_status
        booking.updated_at = _datetime.utcnow()
        session.add(booking)
        session.commit()
        
        return JSONResponse({"success": True})
        
    except Exception as e:
        return JSONResponse({"success": False, "error": str(e)}, status_code=500)

# API endpoints for contact management
@app.get("/api/contacts/find")
async def find_contact(
    request: Request,
    name: str,
    phone: str = None,
    session: Session = Depends(get_session)
):
    user = get_current_user(request)
    if not user:
        return JSONResponse({"success": False, "error": "Unauthorized"}, status_code=401)
    
    try:
        # Try to find contact by name and phone
        if phone:
            contact = session.exec(
                select(Contact).where(
                    Contact.first_name == name,
                    Contact.phone == phone
                )
            ).first()
        else:
            contact = session.exec(
                select(Contact).where(Contact.first_name == name)
            ).first()
        
        if contact:
            return JSONResponse({
                "success": True,
                "contact_id": contact.id,
                "contact": {
                    "first_name": contact.first_name,
                    "last_name": contact.last_name,
                    "phone": contact.phone
                }
            })
        else:
            return JSONResponse({
                "success": True,
                "contact_id": None
            })
            
    except Exception as e:
        return JSONResponse({"success": False, "error": str(e)}, status_code=500)

@app.post("/api/contacts/create")
async def create_contact_api(
    request: Request,
    session: Session = Depends(get_session)
):
    user = get_current_user(request)
    if not user:
        return JSONResponse({"success": False, "error": "Unauthorized"}, status_code=401)
    
    try:
        body = await request.json()
        first_name = body.get("first_name")
        phone = body.get("phone")
        
        if not first_name:
            return JSONResponse({"success": False, "error": "Name is required"}, status_code=400)
        
        # Create new contact
        contact = Contact(
            first_name=first_name,
            last_name=None,
            phone=phone,
            email=None,
            instagram_handle=None,
            nickname=None,
            gender=None,
            city=None,
            birth_date=None,
            preferences=None,
            created_at=_datetime.utcnow(),
            updated_at=_datetime.utcnow()
        )
        
        session.add(contact)
        session.commit()
        session.refresh(contact)
        
        return JSONResponse({
            "success": True,
            "contact_id": contact.id,
            "contact": {
                "first_name": contact.first_name,
                "last_name": contact.last_name,
                "phone": contact.phone
            }
        })
        
    except Exception as e:
        return JSONResponse({"success": False, "error": str(e)}, status_code=500)


@app.get("/api/bookings/{booking_id}")
async def get_booking(
    request: Request,
    booking_id: int,
    session: Session = Depends(get_session)
):
    user = get_current_user(request)
    if not user:
        return JSONResponse({"success": False, "error": "Unauthorized"}, status_code=401)
    
    try:
        booking = session.get(Booking, booking_id)
        if not booking:
            return JSONResponse({"success": False, "error": "Booking not found"}, status_code=404)
        
        # Get contact information
        contact = session.get(Contact, booking.contact_id)
        
        return JSONResponse({
            "success": True,
            "booking": {
                "id": booking.id,
                "contact_id": booking.contact_id,
                "date": booking.date.isoformat() if booking.date else None,
                "time_from": booking.time_from.strftime('%H:%M') if booking.time_from else None,
                "time_to": None,  # This field doesn't exist in the model
                "party_size": booking.party_size,
                "table_type": booking.table_type,
                "occasion": booking.special_case_note,  # Map special_case_note to occasion
                "comment": booking.comment,
                "status": booking.status,
                "contact": {
                    "first_name": contact.first_name if contact else None,
                    "last_name": contact.last_name if contact else None,
                    "phone": contact.phone if contact else None
                } if contact else None
            }
        })
        
    except Exception as e:
        print(f"Error in get_booking: {str(e)}")
        import traceback
        traceback.print_exc()
        return JSONResponse({"success": False, "error": str(e)}, status_code=500)


@app.post("/api/bookings/{booking_id}/update")
async def update_booking(
    request: Request,
    booking_id: int,
    session: Session = Depends(get_session)
):
    user = get_current_user(request)
    if not user:
        return JSONResponse({"success": False, "error": "Unauthorized"}, status_code=401)
    
    try:
        booking = session.get(Booking, booking_id)
        if not booking:
            return JSONResponse({"success": False, "error": "Booking not found"}, status_code=404)
        
        # Get form data
        form_data = await request.form()
        
        # Update booking fields
        if form_data.get("date"):
            booking.date = _date.fromisoformat(form_data.get("date"))
        if form_data.get("time_from"):
            booking.time_from = _time.fromisoformat(form_data.get("time_from"))
        # time_to field doesn't exist in the model, skip it
        if form_data.get("party_size"):
            booking.party_size = int(form_data.get("party_size"))
        if form_data.get("table_type"):
            booking.table_type = form_data.get("table_type")
        if form_data.get("occasion"):
            booking.special_case_note = form_data.get("occasion")  # Map occasion to special_case_note
        if form_data.get("comment"):
            booking.comment = form_data.get("comment")
        if form_data.get("status"):
            booking.status = form_data.get("status")
        
        booking.updated_at = _datetime.utcnow()
        
        session.add(booking)
        session.commit()
        session.refresh(booking)
        
        return JSONResponse({"success": True})
        
    except Exception as e:
        return JSONResponse({"success": False, "error": str(e)}, status_code=500)


@app.post("/api/bookings/new")
async def create_new_booking(request: Request, session: Session = Depends(get_session)):
    try:
        data = await request.json()
        
        # Получаем данные из запроса
        contact_id = data.get('contact_id')
        status = data.get('status')
        party_size = data.get('party_size')
        table_type = data.get('table_type')
        date = data.get('date')
        special_case_note = data.get('special_case_note')
        time_from = data.get('time_from')
        comment = data.get('comment')
        
        # Проверяем обязательные поля
        if not contact_id or not status or not party_size or not date:
            return JSONResponse({"success": False, "error": "Missing required fields"}, status_code=400)
        
        # Парсим дату
        try:
            booking_date = _datetime.strptime(date, "%Y-%m-%d").date()
        except ValueError:
            return JSONResponse({"success": False, "error": "Invalid date format"}, status_code=400)
        
        # Парсим время
        time_from_obj = None
        if time_from:
            try:
                time_from_obj = _datetime.strptime(time_from, "%H:%M").time()
            except ValueError:
                return JSONResponse({"success": False, "error": "Invalid time_from format"}, status_code=400)
        
        # Создаем новую резервацию
        booking = Booking(
            contact_id=contact_id,
            status=status,
            party_size=party_size,
            table_type=table_type,
            date=booking_date,
            special_case_note=special_case_note,
            time_from=time_from_obj,
            comment=comment,
            created_at=_datetime.utcnow(),
            updated_at=_datetime.utcnow()
        )
        
        session.add(booking)
        session.commit()
        session.refresh(booking)
        
        return JSONResponse({"success": True, "booking_id": booking.id})
        
    except Exception as e:
        return JSONResponse({"success": False, "error": str(e)}, status_code=500)

@app.get("/api/tags/all")
async def get_all_tags(request: Request, session: Session = Depends(get_session)):
    user = get_current_user(request)
    if not user:
        return JSONResponse({"success": False, "error": "Unauthorized"}, status_code=401)
    
    try:
        # Получаем всех клиентов с их тегами
        contacts = session.exec(select(Contact)).all()
        
        # Собираем все уникальные теги
        all_tags = set()
        for contact in contacts:
            if contact.preferences and contact.preferences.get('tags'):
                for tag in contact.preferences.get('tags', []):
                    if tag and tag.strip():
                        all_tags.add(tag.strip())
        
        # Преобразуем в список и сортируем
        tags_list = sorted(list(all_tags))
        
        return JSONResponse({
            "success": True,
            "tags": tags_list
        })
        
    except Exception as e:
        return JSONResponse({"success": False, "error": str(e)}, status_code=500)


@app.post("/api/contacts/{contact_id}/update")
async def update_contact_field(contact_id: int, request: Request, session: Session = Depends(get_session)):
    try:
        data = await request.json()
        field = data.get('field')
        value = data.get('value')
        
        contact = session.get(Contact, contact_id)
        if not contact:
            return JSONResponse({"success": False, "error": "Contact not found"}, status_code=404)
        
        # Обновляем поле
        if field == 'first_name':
            contact.first_name = value
        elif field == 'last_name':
            contact.last_name = value
        elif field == 'phone':
            contact.phone = value
        elif field == 'email':
            contact.email = value
        elif field == 'birth_date':
            if value:
                try:
                    contact.birth_date = _datetime.strptime(value, "%Y-%m-%d").date()
                except ValueError:
                    return JSONResponse({"success": False, "error": "Invalid date format"}, status_code=400)
            else:
                contact.birth_date = None
        elif field == 'gender':
            contact.gender = value
        elif field == 'city':
            contact.city = value
        elif field == 'instagram_handle':
            contact.instagram_handle = value
        elif field in ['preferences_text', 'communication_method', 'promoter_name']:
            # Обновляем preferences - создаем новый словарь для отслеживания изменений
            preferences = contact.preferences or {}
            preferences = dict(preferences)  # Создаем копию
            preferences[field] = value
            contact.preferences = preferences
        
        # Добавляем контакт в сессию для всех полей
        session.add(contact)
        session.commit()
        session.refresh(contact)
        
        # Логируем обновленные данные для отладки
        print(f"Updated contact {contact_id}:")
        print(f"  {field} = {value}")
        print(f"  Full contact data: {contact.first_name}, {contact.last_name}, {contact.email}, {contact.gender}")
        print(f"  Preferences: {contact.preferences}")
        
        return JSONResponse({"success": True})
        
    except Exception as e:
        return JSONResponse({"success": False, "error": str(e)}, status_code=500)


@app.get("/settings", response_class=HTMLResponse)
async def settings_page(request: Request, session: Session = Depends(get_session)):
    user = get_current_user(request)
    if not user:
        return RedirectResponse(url="/login", status_code=302)
    
    # Получаем контакты и статистику для поиска как в dashboard
    all_contacts = session.exec(select(Contact).order_by(Contact.created_at.desc())).all()
    
    # Load all bookings needed for stats per contact
    all_bookings = session.exec(select(Booking)).all()
    # Precompute grouped stats
    bookings_by_contact = {}
    for b in all_bookings:
        bookings_by_contact.setdefault(b.contact_id, []).append(b)
    client_stats = {}
    month_names = {
        1: "Januar", 2: "Februar", 3: "Mart", 4: "April", 5: "Maj", 6: "Jun",
        7: "Jul", 8: "Avgust", 9: "Septembar", 10: "Oktobar", 11: "Novembar", 12: "Decembar"
    }
    for c in all_contacts:
        lst = bookings_by_contact.get(c.id, [])
        last_visit = None
        last_booking_status = None
        visits_confirmed = 0
        spends = []
        for b in lst:
            if last_visit is None or (b.date, b.time_from) > (last_visit[0], last_visit[1] if last_visit[1] else b.time_from):
                last_visit = (b.date, b.time_from)
                last_booking_status = b.status
            if b.status in (BookingStatus.POTVRDJENO, "potvrđeno", "potvrdjeno"):
                visits_confirmed += 1
            if b.spend_eur is not None:
                spends.append(b.spend_eur)
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
    
    return templates.TemplateResponse("settings.html", {
        "request": request, 
        "title": "Podešavanja", 
        "user": user,
        "contacts": all_contacts,
        "client_stats": client_stats
    })
