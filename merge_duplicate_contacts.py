#!/usr/bin/env python3
"""
Скрипт для объединения дубликатов контактов в базе данных.
Объединяет контакты с одинаковыми номерами телефонов или email адресами.

Использование:
    python merge_duplicate_contacts.py [--dry-run] [--business-id BUSINESS_ID]

Параметры:
    --dry-run: Только показать, что будет сделано, без реального объединения
    --business-id: Объединить дубликаты только для указанного бизнеса (по умолчанию для всех)
"""

import sys
import argparse
from typing import List, Dict, Set, Optional
from collections import defaultdict
from sqlalchemy import func, and_, or_
from sqlalchemy.orm import Session

# Добавляем путь к приложению
sys.path.insert(0, '.')

from app.db import engine, create_db_and_tables
from app.models import Contact, Booking, ReactivationListContact, ReactivationOffer


def calculate_contact_completeness(contact: Contact) -> int:
    """Подсчитывает 'полноту' контакта - количество заполненных полей"""
    score = 0
    
    # Основные поля (более важные)
    if contact.first_name:
        score += 2
    if contact.last_name:
        score += 2
    if contact.phone:
        score += 2
    if contact.email:
        score += 2
    
    # Дополнительные поля
    if contact.birth_date:
        score += 1
    if contact.gender:
        score += 1
    if contact.city:
        score += 1
    if contact.instagram_handle:
        score += 1
    if contact.nickname:
        score += 1
    
    # Preferences и tags
    if contact.preferences:
        score += 1
        if isinstance(contact.preferences, dict):
            if contact.preferences.get('tags'):
                score += len(contact.preferences.get('tags', []))
            if contact.preferences.get('preferences_text'):
                score += 1
            if contact.preferences.get('communication_method'):
                score += 1
    
    # Custom fields
    if contact.custom_fields:
        score += len([k for k, v in contact.custom_fields.items() if v])
    
    # Статистика (показывает активность)
    if contact.total_bookings and contact.total_bookings > 0:
        score += 1
    if contact.total_spent_eur and contact.total_spent_eur > 0:
        score += 1
    
    return score


def merge_preferences(main_prefs: Optional[dict], duplicate_prefs: Optional[dict]) -> Optional[dict]:
    """Объединяет preferences двух контактов, особенно tags"""
    if not duplicate_prefs:
        return main_prefs
    if not main_prefs:
        return duplicate_prefs.copy()
    
    merged = main_prefs.copy()
    
    # Объединяем tags
    main_tags = set()
    if isinstance(main_prefs.get('tags'), list):
        main_tags = set(main_prefs.get('tags', []))
    
    duplicate_tags = set()
    if isinstance(duplicate_prefs.get('tags'), list):
        duplicate_tags = set(duplicate_prefs.get('tags', []))
    
    # Также проверяем вложенную структуру (на случай старого формата)
    if isinstance(duplicate_prefs.get('preferences'), dict):
        if isinstance(duplicate_prefs['preferences'].get('tags'), list):
            duplicate_tags.update(duplicate_prefs['preferences']['tags'])
    
    all_tags = main_tags | duplicate_tags
    if all_tags:
        merged['tags'] = sorted(list(all_tags))
    
    # Объединяем другие поля preferences, если их нет в основном
    for key, value in duplicate_prefs.items():
        if key not in merged and value:
            merged[key] = value
    
    return merged


def merge_contact_data(main_contact: Contact, duplicate_contact: Contact) -> None:
    """Объединяет данные дубликата в основной контакт"""
    # Объединяем имя, если в основном пустое
    if not main_contact.first_name and duplicate_contact.first_name:
        main_contact.first_name = duplicate_contact.first_name
    if not main_contact.last_name and duplicate_contact.last_name:
        main_contact.last_name = duplicate_contact.last_name
    
    # Объединяем email, если в основном пустое
    if not main_contact.email and duplicate_contact.email:
        main_contact.email = duplicate_contact.email
    
    # Объединяем телефон, если в основном пустое
    if not main_contact.phone and duplicate_contact.phone:
        main_contact.phone = duplicate_contact.phone
    
    # Объединяем другие поля, если в основном пустые
    if not main_contact.birth_date and duplicate_contact.birth_date:
        main_contact.birth_date = duplicate_contact.birth_date
    if not main_contact.gender and duplicate_contact.gender:
        main_contact.gender = duplicate_contact.gender
    if not main_contact.city and duplicate_contact.city:
        main_contact.city = duplicate_contact.city
    if not main_contact.instagram_handle and duplicate_contact.instagram_handle:
        main_contact.instagram_handle = duplicate_contact.instagram_handle
    if not main_contact.nickname and duplicate_contact.nickname:
        main_contact.nickname = duplicate_contact.nickname
    
    # Объединяем preferences
    main_contact.preferences = merge_preferences(main_contact.preferences, duplicate_contact.preferences)
    
    # Объединяем custom_fields
    if duplicate_contact.custom_fields:
        if not main_contact.custom_fields:
            main_contact.custom_fields = duplicate_contact.custom_fields.copy()
        else:
            merged_custom = main_contact.custom_fields.copy()
            for key, value in duplicate_contact.custom_fields.items():
                if key not in merged_custom and value:
                    merged_custom[key] = value
            main_contact.custom_fields = merged_custom


def merge_contacts(
    session: Session,
    main_contact: Contact,
    duplicate_contacts: List[Contact],
    dry_run: bool = False
) -> Dict:
    """Объединяет дубликаты контактов в основной контакт"""
    duplicate_ids = [c.id for c in duplicate_contacts]
    stats = {
        'bookings_moved': 0,
        'reactivation_lists_moved': 0,
        'reactivation_offers_moved': 0,
        'contacts_deleted': 0
    }
    
    print(f"  Объединяем {len(duplicate_contacts)} дубликатов в контакт ID {main_contact.id} ({main_contact.first_name} {main_contact.last_name or ''})")
    
    # Объединяем данные контактов
    for dup in duplicate_contacts:
        merge_contact_data(main_contact, dup)
    
    # Переносим резервации
    bookings = session.query(Booking).filter(Booking.contact_id.in_(duplicate_ids)).all()
    if bookings:
        stats['bookings_moved'] = len(bookings)
        print(f"    Переносим {len(bookings)} резерваций")
        if not dry_run:
            for booking in bookings:
                booking.contact_id = main_contact.id
    
    # Переносим связи с ReactivationList
    reactivation_lists = session.query(ReactivationListContact).filter(
        ReactivationListContact.contact_id.in_(duplicate_ids)
    ).all()
    if reactivation_lists:
        # Группируем по reactivation_list_id, чтобы избежать дубликатов
        lists_to_keep = {}
        for rlc in reactivation_lists:
            key = (rlc.reactivation_list_id, main_contact.id)
            if key not in lists_to_keep:
                # Проверяем, нет ли уже такой связи
                existing = session.query(ReactivationListContact).filter(
                    and_(
                        ReactivationListContact.reactivation_list_id == rlc.reactivation_list_id,
                        ReactivationListContact.contact_id == main_contact.id
                    )
                ).first()
                if not existing:
                    lists_to_keep[key] = rlc
                    if not dry_run:
                        rlc.contact_id = main_contact.id
                    stats['reactivation_lists_moved'] += 1
                else:
                    # Связь уже существует, удаляем дубликат
                    if not dry_run:
                        session.delete(rlc)
            else:
                # Дубликат связи, удаляем
                if not dry_run:
                    session.delete(rlc)
        print(f"    Переносим {stats['reactivation_lists_moved']} связей с акциями")
    
    # Переносим ReactivationOffer
    offers = session.query(ReactivationOffer).filter(ReactivationOffer.contact_id.in_(duplicate_ids)).all()
    if offers:
        stats['reactivation_offers_moved'] = len(offers)
        print(f"    Переносим {len(offers)} предложений по акциям")
        if not dry_run:
            for offer in offers:
                offer.contact_id = main_contact.id
    
    # Обновляем статистику основного контакта
    if not dry_run:
        main_contact.total_bookings = session.query(Booking).filter(
            Booking.contact_id == main_contact.id
        ).count()
        
        # Пересчитываем total_spent_eur
        total_spent = session.query(func.sum(Booking.spend_eur)).filter(
            Booking.contact_id == main_contact.id,
            Booking.spend_eur.isnot(None)
        ).scalar() or 0.0
        main_contact.total_spent_eur = float(total_spent)
    
    # Удаляем дубликаты
    stats['contacts_deleted'] = len(duplicate_contacts)
    if not dry_run:
        for contact in duplicate_contacts:
            session.delete(contact)
    
    return stats


def find_duplicates_by_phone(session: Session, business_id: Optional[int] = None) -> Dict[str, List[Contact]]:
    """Находит дубликаты контактов по номеру телефона"""
    query = session.query(Contact).filter(
        Contact.phone.isnot(None),
        Contact.phone != ''
    )
    if business_id:
        query = query.filter(Contact.business_id == business_id)
    
    contacts = query.all()
    
    # Группируем по телефону (нормализуем: убираем пробелы, дефисы и т.д.)
    phone_groups = defaultdict(list)
    for contact in contacts:
        if contact.phone:
            # Нормализуем телефон: убираем пробелы, дефисы, скобки, оставляем только цифры и +
            phone = ''.join(c for c in contact.phone if c.isdigit() or c == '+')
            if phone:
                phone_groups[phone].append(contact)
    
    # Оставляем только группы с дубликатами
    duplicates = {phone: contacts for phone, contacts in phone_groups.items() if len(contacts) > 1}
    
    return duplicates


def find_duplicates_by_email(session: Session, business_id: Optional[int] = None) -> Dict[str, List[Contact]]:
    """Находит дубликаты контактов по email"""
    query = session.query(Contact).filter(
        Contact.email.isnot(None),
        Contact.email != ''
    )
    if business_id:
        query = query.filter(Contact.business_id == business_id)
    
    contacts = query.all()
    
    # Группируем по email (без учета регистра)
    email_groups = defaultdict(list)
    for contact in contacts:
        if contact.email:
            email = contact.email.strip().lower()
            if email:
                email_groups[email].append(contact)
    
    # Оставляем только группы с дубликатами
    duplicates = {email: contacts for email, contacts in email_groups.items() if len(contacts) > 1}
    
    return duplicates


def merge_all_duplicates(session: Session, business_id: Optional[int] = None, dry_run: bool = False) -> Dict:
    """Объединяет все дубликаты контактов"""
    total_stats = {
        'phone_duplicates_found': 0,
        'email_duplicates_found': 0,
        'phone_groups_merged': 0,
        'email_groups_merged': 0,
        'total_contacts_deleted': 0,
        'total_bookings_moved': 0,
        'total_reactivation_lists_moved': 0,
        'total_reactivation_offers_moved': 0
    }
    
    print("=" * 80)
    print("Поиск дубликатов по номеру телефона...")
    print("=" * 80)
    
    # Находим дубликаты по телефону
    phone_duplicates = find_duplicates_by_phone(session, business_id)
    total_stats['phone_duplicates_found'] = sum(len(contacts) - 1 for contacts in phone_duplicates.values())
    total_stats['phone_groups_merged'] = len(phone_duplicates)
    
    print(f"Найдено {len(phone_duplicates)} групп дубликатов по телефону ({total_stats['phone_duplicates_found']} дубликатов)")
    
    # Объединяем дубликаты по телефону
    for phone, contacts in phone_duplicates.items():
        # Сортируем по полноте информации (самый полный первый), затем по дате создания
        contacts_sorted = sorted(
            contacts, 
            key=lambda c: (calculate_contact_completeness(c), c.created_at), 
            reverse=True
        )
        main_contact = contacts_sorted[0]
        duplicate_contacts = contacts_sorted[1:]
        
        main_completeness = calculate_contact_completeness(main_contact)
        print(f"\nТелефон: {phone}")
        print(f"  Основной контакт ID {main_contact.id} (полнота: {main_completeness} баллов)")
        stats = merge_contacts(session, main_contact, duplicate_contacts, dry_run)
        
        total_stats['total_contacts_deleted'] += stats['contacts_deleted']
        total_stats['total_bookings_moved'] += stats['bookings_moved']
        total_stats['total_reactivation_lists_moved'] += stats['reactivation_lists_moved']
        total_stats['total_reactivation_offers_moved'] += stats['reactivation_offers_moved']
    
    # Коммитим изменения после объединения по телефону
    if not dry_run:
        session.commit()
        print("\n✅ Изменения по телефону сохранены")
    
    print("\n" + "=" * 80)
    print("Поиск дубликатов по email...")
    print("=" * 80)
    
    # Находим дубликаты по email
    email_duplicates = find_duplicates_by_email(session, business_id)
    total_stats['email_duplicates_found'] = sum(len(contacts) - 1 for contacts in email_duplicates.values())
    total_stats['email_groups_merged'] = len(email_duplicates)
    
    print(f"Найдено {len(email_duplicates)} групп дубликатов по email ({total_stats['email_duplicates_found']} дубликатов)")
    
    # Объединяем дубликаты по email
    for email, contacts in email_duplicates.items():
        # Сортируем по полноте информации (самый полный первый), затем по дате создания
        contacts_sorted = sorted(
            contacts, 
            key=lambda c: (calculate_contact_completeness(c), c.created_at), 
            reverse=True
        )
        main_contact = contacts_sorted[0]
        duplicate_contacts = contacts_sorted[1:]
        
        main_completeness = calculate_contact_completeness(main_contact)
        print(f"\nEmail: {email}")
        print(f"  Основной контакт ID {main_contact.id} (полнота: {main_completeness} баллов)")
        stats = merge_contacts(session, main_contact, duplicate_contacts, dry_run)
        
        total_stats['total_contacts_deleted'] += stats['contacts_deleted']
        total_stats['total_bookings_moved'] += stats['bookings_moved']
        total_stats['total_reactivation_lists_moved'] += stats['reactivation_lists_moved']
        total_stats['total_reactivation_offers_moved'] += stats['reactivation_offers_moved']
    
    # Коммитим изменения после объединения по email
    if not dry_run:
        session.commit()
        print("\n✅ Изменения по email сохранены")
    
    return total_stats


def main():
    parser = argparse.ArgumentParser(description='Объединяет дубликаты контактов в базе данных')
    parser.add_argument('--dry-run', action='store_true', help='Только показать, что будет сделано, без реального объединения')
    parser.add_argument('--business-id', type=int, help='Объединить дубликаты только для указанного бизнеса')
    
    args = parser.parse_args()
    
    print("=" * 80)
    print("СКРИПТ ОБЪЕДИНЕНИЯ ДУБЛИКАТОВ КОНТАКТОВ")
    print("=" * 80)
    
    if args.dry_run:
        print("\n⚠️  РЕЖИМ ТЕСТОВОГО ЗАПУСКА - изменения не будут сохранены")
    else:
        print("\n⚠️  ВНИМАНИЕ: Скрипт изменит базу данных!")
        response = input("Продолжить? (yes/no): ")
        if response.lower() != 'yes':
            print("Отменено.")
            return
    
    if args.business_id:
        print(f"\nОбрабатываем только бизнес ID: {args.business_id}")
    else:
        print("\nОбрабатываем все бизнесы")
    
    # Создаем таблицы, если их нет
    create_db_and_tables()
    
    # Открываем сессию
    with Session(engine) as session:
        try:
            stats = merge_all_duplicates(session, args.business_id, args.dry_run)
            
            print("\n" + "=" * 80)
            print("РЕЗУЛЬТАТЫ")
            print("=" * 80)
            print(f"Дубликатов по телефону найдено: {stats['phone_duplicates_found']}")
            print(f"Групп по телефону объединено: {stats['phone_groups_merged']}")
            print(f"Дубликатов по email найдено: {stats['email_duplicates_found']}")
            print(f"Групп по email объединено: {stats['email_groups_merged']}")
            print(f"Всего контактов удалено: {stats['total_contacts_deleted']}")
            print(f"Всего резерваций перенесено: {stats['total_bookings_moved']}")
            print(f"Всего связей с акциями перенесено: {stats['total_reactivation_lists_moved']}")
            print(f"Всего предложений по акциям перенесено: {stats['total_reactivation_offers_moved']}")
            
            if args.dry_run:
                print("\n⚠️  Это был тестовый запуск. Для реального объединения запустите без --dry-run")
            else:
                print("\n✅ Объединение завершено успешно!")
                
        except Exception as e:
            session.rollback()
            print(f"\n❌ Ошибка: {e}")
            import traceback
            traceback.print_exc()
            sys.exit(1)


if __name__ == '__main__':
    main()

