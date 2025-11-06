"""
Email sending module for LovaCRM
"""

import smtplib
import ssl
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import Optional
import os

class EmailConfig:
    """Конфигурация для отправки email"""
    
    def __init__(self):
        self.enabled = os.getenv("EMAIL_ENABLED", "false").lower() == "true"
        self.smtp_server = os.getenv("EMAIL_SMTP_SERVER", "smtp.gmail.com")
        self.smtp_port = int(os.getenv("EMAIL_SMTP_PORT", "587"))
        self.username = os.getenv("EMAIL_USERNAME", "")
        self.password = os.getenv("EMAIL_PASSWORD", "")
        self.from_name = os.getenv("EMAIL_FROM_NAME", "LovaCRM")
        self.from_address = os.getenv("EMAIL_FROM_ADDRESS", "noreply@lovacrm.com")
        self.admin_email = os.getenv("ADMIN_EMAIL", "admin@lovacrm.com")

# Глобальная конфигурация
email_config = EmailConfig()

def send_email(
    to_email: str,
    subject: str,
    message: str,
    is_html: bool = False
) -> bool:
    """
    Отправляет email
    
    Args:
        to_email: Email получателя
        subject: Тема письма
        message: Содержимое письма
        is_html: True если сообщение в HTML формате
    
    Returns:
        True если письмо отправлено успешно, False в противном случае
    """
    
    if not email_config.enabled:
        print("=" * 80)
        print(f"📧 EMAIL (КОНСОЛЬ): {to_email}")
        print(f"📋 ТЕМА: {subject}")
        print("-" * 80)
        print(f"📝 СОДЕРЖИМОЕ:")
        print(message)
        print("=" * 80)
        return True
    
    if not email_config.username or not email_config.password:
        print(f"❌ EMAIL НЕ НАСТРОЕН: отсутствуют учетные данные")
        return False
    
    try:
        # Создаем сообщение
        msg = MIMEMultipart()
        msg['From'] = f"{email_config.from_name} <{email_config.from_address}>"
        msg['To'] = to_email
        msg['Subject'] = subject
        
        # Добавляем содержимое
        if is_html:
            msg.attach(MIMEText(message, 'html', 'utf-8'))
        else:
            msg.attach(MIMEText(message, 'plain', 'utf-8'))
        
        # Создаем SSL контекст
        context = ssl.create_default_context()
        
        # Подключаемся к серверу и отправляем
        if email_config.smtp_port == 465:
            # SSL подключение для порта 465
            with smtplib.SMTP_SSL(email_config.smtp_server, email_config.smtp_port, context=context) as server:
                server.login(email_config.username, email_config.password)
                text = msg.as_string()
                server.sendmail(email_config.from_address, to_email, text)
        else:
            # TLS подключение для порта 587
            with smtplib.SMTP(email_config.smtp_server, email_config.smtp_port) as server:
                server.starttls(context=context)
                server.login(email_config.username, email_config.password)
                text = msg.as_string()
                server.sendmail(email_config.from_address, to_email, text)
        
        print(f"✅ EMAIL ОТПРАВЛЕН: {to_email} - {subject}")
        
        # ДОПОЛНИТЕЛЬНО ВЫВОДИМ В КОНСОЛЬ ДЛЯ АДМИНА
        print("=" * 80)
        print(f"📧 ДУБЛИРОВАНИЕ В КОНСОЛЬ: {to_email}")
        print(f"📋 ТЕМА: {subject}")
        print("-" * 80)
        print(f"📝 СОДЕРЖИМОЕ:")
        print(message)
        print("=" * 80)
        
        return True
        
    except Exception as e:
        print(f"❌ ОШИБКА ОТПРАВКИ EMAIL: {str(e)}")
        print(f"📧 Получатель: {to_email}")
        print(f"📋 Тема: {subject}")
        return False

def send_notification_email(
    to_email: str,
    subject: str,
    message: str,
    notification_type: str = "info"
) -> bool:
    """
    Отправляет уведомление с красивым форматированием
    
    Args:
        to_email: Email получателя
        subject: Тема письма
        message: Содержимое письма
        notification_type: Тип уведомления (info, warning, success, error)
    
    Returns:
        True если письмо отправлено успешно
    """
    
    # Определяем цвет и иконку в зависимости от типа
    colors = {
        "info": "#3498db",
        "warning": "#f39c12", 
        "success": "#27ae60",
        "error": "#e74c3c"
    }
    
    icons = {
        "info": "ℹ️",
        "warning": "⚠️",
        "success": "✅", 
        "error": "❌"
    }
    
    color = colors.get(notification_type, colors["info"])
    icon = icons.get(notification_type, icons["info"])
    
    # Создаем HTML сообщение
    html_message = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="UTF-8">
        <style>
            body {{
                font-family: Arial, sans-serif;
                line-height: 1.6;
                color: #333;
                max-width: 600px;
                margin: 0 auto;
                padding: 20px;
            }}
            .header {{
                background-color: {color};
                color: white;
                padding: 20px;
                text-align: center;
                border-radius: 8px 8px 0 0;
            }}
            .content {{
                background-color: #f8f9fa;
                padding: 30px;
                border-radius: 0 0 8px 8px;
                border: 1px solid #dee2e6;
            }}
            .footer {{
                text-align: center;
                margin-top: 20px;
                color: #6c757d;
                font-size: 14px;
            }}
            .icon {{
                font-size: 24px;
                margin-right: 10px;
            }}
        </style>
    </head>
    <body>
        <div class="header">
            <span class="icon">{icon}</span>
            <strong>LovaCRM</strong>
        </div>
        <div class="content">
            {message.replace(chr(10), '<br>')}
        </div>
        <div class="footer">
            <p>Это автоматическое сообщение от системы LovaCRM</p>
            <p>Пожалуйста, не отвечайте на это письмо</p>
        </div>
    </body>
    </html>
    """
    
    return send_email(to_email, subject, html_message, is_html=True)

def test_email_connection() -> bool:
    """
    Тестирует подключение к email серверу
    
    Returns:
        True если подключение успешно
    """
    
    if not email_config.enabled:
        print("📧 EMAIL ОТКЛЮЧЕН - тест пропущен")
        return True
    
    try:
        context = ssl.create_default_context()
        
        if email_config.smtp_port == 465:
            # SSL подключение для порта 465
            with smtplib.SMTP_SSL(email_config.smtp_server, email_config.smtp_port, context=context) as server:
                server.login(email_config.username, email_config.password)
        else:
            # TLS подключение для порта 587
            with smtplib.SMTP(email_config.smtp_server, email_config.smtp_port) as server:
                server.starttls(context=context)
                server.login(email_config.username, email_config.password)
        
        print("✅ EMAIL ПОДКЛЮЧЕНИЕ УСПЕШНО")
        return True
        
    except Exception as e:
        print(f"❌ ОШИБКА ПОДКЛЮЧЕНИЯ К EMAIL: {str(e)}")
        return False

if __name__ == "__main__":
    # Тестируем подключение
    print("🧪 ТЕСТ EMAIL ПОДКЛЮЧЕНИЯ")
    print("=" * 40)
    
    if test_email_connection():
        print("✅ Email сервер доступен")
        
        # Отправляем тестовое письмо
        test_result = send_notification_email(
            to_email="test@example.com",
            subject="Тест LovaCRM",
            message="Это тестовое сообщение от системы LovaCRM",
            notification_type="info"
        )
        
        if test_result:
            print("✅ Тестовое письмо отправлено")
        else:
            print("❌ Ошибка отправки тестового письма")
    else:
        print("❌ Email сервер недоступен")
