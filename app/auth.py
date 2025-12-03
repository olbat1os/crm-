import hashlib
import secrets
import string
from datetime import datetime, timedelta
from typing import Optional, List
from sqlmodel import Session, select
from app.models import Admin, AdminRole, Business, BusinessStatus
from app.config import settings


def hash_password(password: str) -> str:
    """Хеширует пароль"""
    return hashlib.sha256(password.encode()).hexdigest()


def verify_password(password: str, hashed_password: str) -> bool:
    """Проверяет пароль"""
    return hash_password(password) == hashed_password


def create_default_admins(session: Session):
    """Создает дефолтных админов при первом запуске"""
    # Проверяем, есть ли уже админы
    existing_admins = session.exec(select(Admin)).all()
    if existing_admins:
        return
    
    # Создаем супер-админа
    super_admin = Admin(
        username=settings.super_admin_username,
        password_hash=hash_password(settings.super_admin_password),
        email=settings.super_admin_email,
        full_name="Super Administrator",
        role=AdminRole.SUPER_ADMIN,
        is_active=True
    )
    session.add(super_admin)
    
    # Создаем обычного админа
    admin = Admin(
        username=settings.admin_username,
        password_hash=hash_password(settings.admin_password),
        email=settings.admin_email,
        full_name="Administrator",
        role=AdminRole.ADMIN,
        is_active=True
    )
    session.add(admin)
    
    session.commit()


def authenticate_admin(session: Session, username: str, password: str) -> Optional[Admin]:
    """Аутентификация админа"""
    admin = session.exec(select(Admin).where(Admin.username == username)).first()
    if admin and verify_password(password, admin.password_hash) and admin.is_active:
        return admin
    return None


def get_admin_by_id(session: Session, admin_id: int) -> Optional[Admin]:
    """Получить админа по ID"""
    return session.get(Admin, admin_id)


def create_business(
    session: Session,
    business_name: str,
    contact_person: str,
    email: str,
    phone: str,
    address: Optional[str] = None,
    city: Optional[str] = None,
    country: Optional[str] = None,
    business_type: Optional[str] = None,
    description: Optional[str] = None,
    assigned_admin_id: Optional[int] = None
) -> Business:
    """Создать новый бизнес"""
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
        status=BusinessStatus.PENDING,
        assigned_admin_id=assigned_admin_id
    )
    session.add(business)
    session.commit()
    session.refresh(business)
    return business


def activate_business(
    session: Session,
    business_id: int,
    access_days: int = 7,
    assigned_admin_id: Optional[int] = None
) -> bool:
    """Активировать бизнес на определенный период"""
    business = session.get(Business, business_id)
    if not business:
        return False
    
    now = datetime.utcnow()
    business.status = BusinessStatus.ACTIVE
    business.access_start_date = now
    business.access_end_date = now + timedelta(days=access_days)
    business.trial_days = access_days
    if assigned_admin_id:
        business.assigned_admin_id = assigned_admin_id
    
    session.add(business)
    session.commit()
    return True


def activate_business_with_minutes(
    session: Session,
    business_id: int,
    access_minutes: int,
    assigned_admin_id: Optional[int] = None
) -> bool:
    """Активировать бизнес на определенное количество минут"""
    business = session.get(Business, business_id)
    if not business:
        return False
    
    now = datetime.utcnow()
    business.status = BusinessStatus.ACTIVE
    business.access_start_date = now
    business.access_end_date = now + timedelta(minutes=access_minutes)
    business.trial_days = access_minutes // (24 * 60)  # Конвертируем в дни для отображения
    if assigned_admin_id:
        business.assigned_admin_id = assigned_admin_id
    
    session.add(business)
    session.commit()
    return True


def deactivate_business(session: Session, business_id: int) -> bool:
    """Деактивировать бизнес"""
    business = session.get(Business, business_id)
    if not business:
        return False
    
    business.status = BusinessStatus.SUSPENDED
    session.add(business)
    session.commit()
    return True


def get_businesses_by_admin(session: Session, admin_id: int) -> List[Business]:
    """Получить все бизнесы, назначенные админу"""
    return session.exec(select(Business).where(Business.assigned_admin_id == admin_id)).all()


def get_all_businesses(session: Session) -> List[Business]:
    """Получить все бизнесы (только для супер-админа)"""
    return session.exec(select(Business).order_by(Business.created_at.desc())).all()


def check_business_access(business: Business) -> bool:
    """Проверить, активен ли доступ к бизнесу"""
    if business.status != BusinessStatus.ACTIVE:
        return False
    
    if business.access_end_date and business.access_end_date < datetime.utcnow():
        return False
    
    return True


def get_pending_businesses(session: Session) -> List[Business]:
    """Получить все бизнесы со статусом PENDING"""
    return session.exec(select(Business).where(Business.status == BusinessStatus.PENDING).order_by(Business.created_at.desc())).all()


def get_current_admin(request):
    """Получает текущего админа из сессии"""
    return request.session.get("admin")


def require_admin(request):
    """Требует, чтобы пользователь был админом"""
    admin = get_current_admin(request)
    if not admin:
        from fastapi import HTTPException
        raise HTTPException(status_code=401, detail="Admin authentication required")
    return admin


def require_super_admin(request):
    """Требует, чтобы пользователь был супер-админом"""
    admin = get_current_admin(request)
    if not admin or admin.get("role") != AdminRole.SUPER_ADMIN:
        from fastapi import HTTPException
        raise HTTPException(status_code=403, detail="Super admin access required")
    return admin


def generate_random_password(length: int = 12) -> str:
    """Генерирует случайный пароль"""
    # Используем буквы, цифры и некоторые спецсимволы
    alphabet = string.ascii_letters + string.digits + "!@#$%^&*"
    password = ''.join(secrets.choice(alphabet) for i in range(length))
    return password


def generate_2fa_code() -> str:
    """Генерирует 6-значный код для двухфакторной аутентификации"""
    return ''.join(secrets.choice(string.digits) for i in range(6))


def send_2fa_code(admin_email: str, code: str, admin_name: str) -> bool:
    """Отправляет код двухфакторной аутентификации супер-админу"""
    try:
        from app.email_service import send_notification_email
        
        subject = "🔐 Kod potvrde prijave - LovaCRM Admin"
        message = f"""
        Zdravo, {admin_name}!
        
        🔐 KOD POTVRDE PRIJAVE
        
        Vaš kod za prijavu u admin panel LovaCRM:
        
        {code}
        
        ⏰ Kod je važeći u narednih 5 minuta.
        
        Ako ovo niste bili vi, odmah promenite lozinku!
        
        Sa poštovanjem,
        Tim LovaCRM
        """
        
        # Красивый вывод в консоль
        print("\n" + "=" * 60)
        print("🔐 2FA KOD POSLAT")
        print("=" * 60)
        print(f"📨 Za: {admin_email}")
        print(f"👤 Admin: {admin_name}")
        print(f"📋 Tema: {subject}")
        print("📄 Poruka:")
        print("-" * 40)
        print(message.strip())
        print("-" * 40)
        print("=" * 60)
        print()
        
        # Всегда шлём супер-админу (по требованию)
        from app.config import settings as _settings
        target_email = _settings.super_admin_email or admin_email
        result = send_notification_email(
            to_email=target_email,
            subject=subject,
            message=message,
            notification_type="info"
        )
        
        if result:
            print("✅ 2FA kod uspešno poslat!")
        else:
            print("❌ Greška pri slanju 2FA koda")
        
        return result
    except Exception as e:
        print(f"❌ Greška pri slanju 2FA koda: {str(e)}")
        return False


def set_business_password(session: Session, business_id: int, password: Optional[str] = None) -> str:
    """Устанавливает пароль для бизнеса. Если пароль не указан, генерирует случайный"""
    business = session.get(Business, business_id)
    if not business:
        raise ValueError(f"Business with id {business_id} not found")
    
    # Генерируем пароль, если не передан
    if not password:
        password = generate_random_password()
    
    # Хешируем и сохраняем
    business.password_hash = hash_password(password)
    business.updated_at = datetime.utcnow()
    session.add(business)
    session.commit()
    
    return password  # Возвращаем нехешированный пароль для отправки по email


def send_password_email(business_email: str, business_name: str, password: str, is_reset: bool = False) -> bool:
    """Отправляет пароль на email бизнеса"""
    
    subject = "Сброс пароля LovaCRM" if is_reset else "Ваш пароль для LovaCRM"
    message = f"""
    Здравствуйте, {business_name}!
    
    {'Ваш пароль был сброшен.' if is_reset else 'Добро пожаловать в LovaCRM!'}
    
    Ваши данные для входа:
    Email: {business_email}
    Пароль: {password}
    
    Войти в систему: http://localhost:8000/login
    
    Пожалуйста, сохраните этот пароль в безопасном месте.
    
    С уважением,
    Команда LovaCRM
    """
    
    # Красивый вывод в консоль
    print("\n" + "=" * 60)
    print("📧 EMAIL УВЕДОМЛЕНИЕ")
    print("=" * 60)
    print(f"📨 Кому: {business_email}")
    print(f"📋 Тема: {subject}")
    print("📄 Сообщение:")
    print("-" * 40)
    print(message.strip())
    print("-" * 40)
    print("=" * 60)
    print()
    
    # Отправляем реальное письмо
    try:
        from app.email_service import send_notification_email
        email_sent = send_notification_email(
            to_email=business_email,
            subject=subject,
            message=message,
            notification_type="success" if not is_reset else "info"
        )
        
        if email_sent:
            print("✅ Письмо успешно отправлено!")
        else:
            print("❌ Ошибка отправки письма")
            
    except Exception as e:
        print(f"❌ Ошибка при отправке email: {str(e)}")
    
    return True


def reset_business_password(session: Session, business_id: int) -> bool:
    """Сбрасывает пароль бизнеса и отправляет новый на email"""
    business = session.get(Business, business_id)
    if not business:
        return False
    
    # Генерируем новый пароль
    new_password = set_business_password(session, business_id)
    
    # Отправляем на email
    send_password_email(business.email, business.business_name, new_password, is_reset=True)
    
    # Выводим дополнительную информацию в консоль
    print("=" * 60)
    print("🔄 ПАРОЛЬ СБРОШЕН!")
    print(f"📧 Email: {business.email}")
    print(f"🏢 Название: {business.business_name}")
    print(f"🔑 Новый пароль: {new_password}")
    print("=" * 60)
    
    return True


def check_business_expiry(session: Session, business_id: int) -> dict:
    """Проверяет, истек ли срок доступа бизнеса"""
    business = session.get(Business, business_id)
    if not business:
        return {"expired": False, "message": "Business not found"}
    
    now = datetime.utcnow()
    
    if business.status != BusinessStatus.ACTIVE:
        return {"expired": False, "message": "Business not active"}
    
    if business.access_end_date and now > business.access_end_date:
        return {
            "expired": True, 
            "message": "Access period has expired",
            "expired_date": business.access_end_date,
            "days_overdue": (now - business.access_end_date).days
        }
    
    return {"expired": False, "message": "Access is valid"}


def freeze_expired_business(session: Session, business_id: int) -> bool:
    """Замораживает бизнес с истекшим сроком доступа"""
    business = session.get(Business, business_id)
    if not business:
        return False
    
    business.status = BusinessStatus.EXPIRED
    business.updated_at = datetime.utcnow()
    session.add(business)
    session.commit()
    return True


def send_expiry_notification(business_email: str, business_name: str, admin_email: str = None) -> bool:
    """Отправляет уведомление об истечении срока доступа"""
    
    # Уведомление клиенту
    client_subject = "⚠️ Istekao je rok pristupa LovaCRM"
    client_message = """
    Zdravo! 👋


    
    ⚠️ Vaš pristup nalogu LovaCRM je istekao.
    
    Vaš profil je trenutno privremeno pauziran.



    Ako želite da nastavite sa korišćenjem sistema ili da aktivirate komercijalnu verziju, kontaktirajte nas:

    📧 mihalytix@gmail.com

    📞 +381 65 8695 660



    Rado ćemo vam pomoći da obnovite pristup i pokažemo nove funkcionalnosti koje smo dodali.


    
    Sa poštovanjem,

    Tim LovaCRM
    """
    
    # Уведомление админу
    admin_subject = "🚨 Istekao je rok pristupa biznisa"
    admin_message = f"""
    Administratoru LovaCRM
    
    🚨 PAŽNJA: Istekao je rok pristupa za biznis!
    
    Detalji:
    📧 Email klijenta: {business_email}
    🏢 Naziv biznisa: {business_name}
    ⏰ Datum isteka: {datetime.utcnow().strftime('%Y-%m-%d %H:%M')}
    
    Nalog je automatski zamrznut.
    Potrebno je produženje pristupa.
    
    Sa poštovanjem,
    Sistem LovaCRM
    """
    
    # Выводим уведомления в консоль
    print("\n" + "=" * 70)
    print("🚨 OBAVEŠTENJE O ISTEKU ROKA")
    print("=" * 70)
    
    # Уведомление клиенту
    print("📧 OBAVEŠTENJE KLIJENTU:")
    print("-" * 50)
    print(f"📨 Za: {business_email}")
    print(f"📋 Tema: {client_subject}")
    print("📄 Poruka:")
    print(client_message.strip())
    print("-" * 50)
    
    # Уведомление админу
    if admin_email:
        print("📧 OBAVEŠTENJE ADMINU:")
        print("-" * 50)
        print(f"📨 Za: {admin_email}")
        print(f"📋 Tema: {admin_subject}")
        print("📄 Poruka:")
        print(admin_message.strip())
        print("-" * 50)
    
    print("=" * 70)
    print()
    
    # Отправляем реальные письма
    try:
        from app.email_service import send_notification_email
        
        # Отправляем клиенту
        client_sent = send_notification_email(
            to_email=business_email,
            subject=client_subject,
            message=client_message,
            notification_type="error"
        )
        
        # Отправляем админу
        admin_sent = False
        if admin_email:
            admin_sent = send_notification_email(
                to_email=admin_email,
                subject=admin_subject,
                message=admin_message,
                notification_type="error"
            )
        
        if client_sent:
            print("✅ Письмо клиенту отправлено!")
        else:
            print("❌ Ошибка отправки письма клиенту")
            
        if admin_sent:
            print("✅ Письмо админу отправлено!")
        elif admin_email:
            print("❌ Ошибка отправки письма админу")
            
    except Exception as e:
        print(f"❌ Ошибка при отправке email: {str(e)}")
    
    return True


def send_upcoming_expiry_notification_client(email: str, business_name: str, expiry_date: datetime) -> bool:
    """Отправляет уведомление клиенту о скором истечении срока"""
    try:
        from app.email_service import send_notification_email
        
        subject = "⚠️ Vaš probni period se završava za 3 dana - LovaCRM"
        message = f"""
Zdravo, {business_name}!

Vaš probni period na LovaCRM sistemu se završava za 3 dana.

📅 Datum isteka: {expiry_date.strftime('%d.%m.%Y %H:%M')}

Da biste nastavili korišćenje sistema nakon isteka probnog perioda, molimo kontaktirajte našu podršku.

🔗 Link za prijavu: https://lovacrm.com/login

Sa poštovanjem,
Tim LovaCRM
"""
        
        return send_notification_email(email, subject, message)
        
    except Exception as e:
        print(f"❌ Greška pri slanju upozorenja klijentu {email}: {e}")
        return False


def send_upcoming_expiry_notification_admin(business_name: str, business_email: str, expiry_date: datetime) -> bool:
    """Отправляет уведомление админу о скором истечении срока у клиента"""
    try:
        from app.email_service import send_notification_email
        from app.config import settings
        
        subject = f"⚠️ Upozorenje: {business_name} - probni period se završava za 3 dana"
        message = f"""
Zdravo, Admin!

Biznis {business_name} ima probni period koji se završava za 3 dana.

📊 Detalji:
🏢 Naziv biznisa: {business_name}
📧 Email: {business_email}
📅 Datum isteka: {expiry_date.strftime('%d.%m.%Y %H:%M')}

Preporučuje se kontaktirati klijenta za produženje pristupa.

Sa poštovanjem,
LovaCRM Sistem
"""
        
        return send_notification_email(settings.admin_email, subject, message)
        
    except Exception as e:
        print(f"❌ Greška pri slanju upozorenja adminu za {business_name}: {e}")
        return False


def check_upcoming_expirations(session: Session) -> int:
    """Проверяет бизнесы, у которых скоро истечет срок (за 3 дня) и отправляет уведомления"""
    now = datetime.utcnow()
    three_days_later = now + timedelta(days=3)
    
    # Находим бизнесы, у которых срок истекает в ближайшие 3 дня
    upcoming_expirations = session.exec(
        select(Business).where(
            Business.status == BusinessStatus.ACTIVE,
            Business.access_end_date > now,
            Business.access_end_date <= three_days_later
        )
    ).all()
    
    notification_count = 0
    
    for business in upcoming_expirations:
        # Проверяем, не отправляли ли мы уже уведомление
        if not hasattr(business, 'expiry_notification_sent') or not business.expiry_notification_sent:
            # Отправляем уведомление клиенту
            send_upcoming_expiry_notification_client(business.email, business.business_name, business.access_end_date)
            
            # Отправляем уведомление админу
            send_upcoming_expiry_notification_admin(business.business_name, business.email, business.access_end_date)
            
            # Помечаем, что уведомление отправлено
            business.expiry_notification_sent = True
            session.add(business)
            session.commit()
            
            notification_count += 1
            print(f"📧 Poslano upozorenje za {business.business_name} ({business.email})")
    
    if notification_count > 0:
        print(f"📧 Ukupno poslano upozorenja: {notification_count}")
    
    return notification_count


def check_and_freeze_expired_businesses(session: Session) -> int:
    """Проверяет все активные бизнесы и замораживает истекшие (только вручную)"""
    now = datetime.utcnow()
    
    # Сначала проверяем бизнесы, у которых скоро истечет срок (за 3 часа)
    check_upcoming_expirations(session)
    
    # НЕ замораживаем автоматически - только проверяем и уведомляем
    expired_businesses = session.exec(
        select(Business).where(
            Business.status == BusinessStatus.ACTIVE,
            Business.access_end_date < now
        )
    ).all()
    
    if expired_businesses:
        print(f"⚠️ Найдено {len(expired_businesses)} бизнесов с истекшим сроком (не замораживаем автоматически)")
        for business in expired_businesses:
            print(f"   - {business.business_name} ({business.email})")
    
    return 0  # Не замораживаем автоматически


def unfreeze_business(session: Session, business_id: int, new_access_days: int = 30) -> bool:
    """Размораживает бизнес и устанавливает новый срок доступа"""
    business = session.get(Business, business_id)
    if not business:
        return False
    
    now = datetime.utcnow()
    business.status = BusinessStatus.ACTIVE
    business.access_start_date = now
    business.access_end_date = now + timedelta(days=new_access_days)
    business.updated_at = now
    session.add(business)
    session.commit()
    return True


def extend_business_access(session: Session, business_id: int, new_access_days: int = 30) -> bool:
    """Продлевает срок доступа для активного бизнеса"""
    business = session.get(Business, business_id)
    if not business:
        return False
    
    now = datetime.utcnow()
    # Если срок уже истек, устанавливаем новую дату от текущего момента
    if business.access_end_date and business.access_end_date < now:
        business.access_start_date = now
        business.access_end_date = now + timedelta(days=new_access_days)
    else:
        # Если срок еще не истек, продлеваем от текущей даты окончания
        if business.access_end_date:
            business.access_end_date = business.access_end_date + timedelta(days=new_access_days)
        else:
            business.access_end_date = now + timedelta(days=new_access_days)
            business.access_start_date = now
    
    business.updated_at = now
    session.add(business)
    session.commit()
    return True


def send_unfreeze_notification(business_email: str, business_name: str, new_access_days: int, admin_email: str = None) -> bool:
    """Отправляет уведомление о размораживании аккаунта"""
    
    # Уведомление клиенту
    client_subject = "✅ Vaš nalog je aktiviran - LovaCRM"
    client_message = f"""
    Zdravo, {business_name}!
    
    ✅ DOBRA VEST: Vaš nalog LovaCRM je ponovo aktiviran!
    
    Vaš nalog je razmrznut i možete nastaviti sa radom.
    Novi rok pristupa: {new_access_days} dana.
    
    Možete se prijaviti na: http://localhost:8000/login
    
    Hvala vam na strpljenju!
    
    Sa poštovanjem,
    Tim LovaCRM
    """
    
    # Уведомление админу (без информации о том, кто разморозил)
    admin_subject = "✅ Biznis je razmrznut"
    admin_message = f"""
    Administratoru LovaCRM
    
    ✅ POTVRDA: Biznis je uspešno razmrznut!
    
    Detalji:
    📧 Email klijenta: {business_email}
    🏢 Naziv biznisa: {business_name}
    ⏰ Novi rok pristupa: {new_access_days} dana
    📅 Datum aktivacije: {datetime.utcnow().strftime('%Y-%m-%d %H:%M')}
    
    Biznis je ponovo aktivan.
    
    Sa poštovanjem,
    Sistem LovaCRM
    """
    
    # Выводим уведомления в консоль
    print("\n" + "=" * 70)
    print("✅ OBAVEŠTENJE O RAZMRZAVANJU")
    print("=" * 70)
    
    # Уведомление клиенту
    print("📧 OBAVEŠTENJE KLIJENTU:")
    print("-" * 50)
    print(f"📨 Za: {business_email}")
    print(f"📋 Tema: {client_subject}")
    print("📄 Poruka:")
    print(client_message.strip())
    print("-" * 50)
    
    # Уведомление админу
    if admin_email:
        print("📧 OBAVEŠTENJE ADMINU:")
        print("-" * 50)
        print(f"📨 Za: {admin_email}")
        print(f"📋 Tema: {admin_subject}")
        print("📄 Poruka:")
        print(admin_message.strip())
        print("-" * 50)
    
    print("=" * 70)
    print()
    
    # Отправляем реальные письма
    try:
        from app.email_service import send_notification_email
        
        # Отправляем клиенту
        client_sent = send_notification_email(
            to_email=business_email,
            subject=client_subject,
            message=client_message,
            notification_type="success"
        )
        
        # Отправляем админу
        admin_sent = False
        if admin_email:
            admin_sent = send_notification_email(
                to_email=admin_email,
                subject=admin_subject,
                message=admin_message,
                notification_type="success"
            )
        
        if client_sent:
            print("✅ Письмо клиенту отправлено!")
        else:
            print("❌ Ошибка отправки письма клиенту")
            
        if admin_sent:
            print("✅ Письмо админу отправлено!")
        elif admin_email:
            print("❌ Ошибка отправки письма админу")
            
    except Exception as e:
        print(f"❌ Ошибка при отправке email: {str(e)}")
    
    return True
def suspend_business(session: Session, business_id: int) -> bool:
    """Приостанавливает бизнес"""
    business = session.get(Business, business_id)
    if not business:
        return False
    
    business.status = BusinessStatus.SUSPENDED
    business.updated_at = datetime.utcnow()
    session.add(business)
    session.commit()
    return True


def send_suspend_notification(business_email: str, business_name: str, admin_email: str = None) -> bool:
    """Отправляет уведомление о приостановке бизнеса"""
    
    # Уведомление клиенту
    client_subject = "⚠️ Vaš nalog je privremeno suspendovan - LovaCRM"
    client_message = f"""
    Zdravo, {business_name}!
    
    ⚠️ PAŽNJA: Vaš nalog LovaCRM je privremeno suspendovan.
    
    Vaš nalog je privremeno zaustavljen. Za nastavak rada 
    obratite se administratoru sistema.
    
    Ako imate pitanja, kontaktirajte nas.
    
    Sa poštovanjem,
    Tim LovaCRM
    """
    
    # Уведомление админу (без информации о том, кто приостановил)
    admin_subject = "⚠️ Biznis je suspendovan"
    admin_message = f"""
    Administratoru LovaCRM
    
    ⚠️ POTVRDA: Biznis je suspendovan!
    
    Detalji:
    📧 Email klijenta: {business_email}
    🏢 Naziv biznisa: {business_name}
    📅 Datum suspendovanja: {datetime.utcnow().strftime('%Y-%m-%d %H:%M')}
    
    Biznis je privremeno zaustavljen.
    
    Sa poštovanjem,
    Sistem LovaCRM
    """
    
    # Выводим уведомления в консоль
    print("\n" + "=" * 70)
    print("⚠️ OBAVEŠTENJE O SUSPENDOVANJU")
    print("=" * 70)
    
    # Уведомление клиенту
    print("📧 OBAVEŠTENJE KLIJENTU:")
    print("-" * 50)
    print(f"📨 Za: {business_email}")
    print(f"📋 Tema: {client_subject}")
    print("📄 Poruka:")
    print(client_message.strip())
    print("-" * 50)
    
    # Уведомление админу
    if admin_email:
        print("📧 OBAVEŠTENJE ADMINU:")
        print("-" * 50)
        print(f"📨 Za: {admin_email}")
        print(f"📋 Tema: {admin_subject}")
        print("📄 Poruka:")
        print(admin_message.strip())
        print("-" * 50)
    
    print("=" * 70)
    print()
    
    # Отправляем реальные письма
    try:
        from app.email_service import send_notification_email
        
        # Отправляем клиенту
        client_sent = send_notification_email(
            to_email=business_email,
            subject=client_subject,
            message=client_message,
            notification_type="warning"
        )
        
        # Отправляем админу
        admin_sent = False
        if admin_email:
            admin_sent = send_notification_email(
                to_email=admin_email,
                subject=admin_subject,
                message=admin_message,
                notification_type="warning"
            )
        
        if client_sent:
            print("✅ Письмо клиенту отправлено!")
        else:
            print("❌ Ошибка отправки письма клиенту")
            
        if admin_sent:
            print("✅ Письмо админу отправлено!")
        elif admin_email:
            print("❌ Ошибка отправки письма админу")
            
    except Exception as e:
        print(f"❌ Ошибка при отправке email: {str(e)}")
    
    return True

