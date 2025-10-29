// Оптимизация лендинга LovaCRM

document.addEventListener('DOMContentLoaded', function() {
            // Предзагружаем критические изображения
            const criticalImages = [
                '/static/images/logo_login.svg.png',
                '/static/images/fon_for_land.JPEG',
                '/static/images/dashboard%20pk.PNG',
                '/static/images/dashboard%20mob.PNG',
                '/static/images/func.PNG',
                '/static/images/func%20mob.PNG',
                '/static/images/mapa%20pk.png',
                '/static/images/mapa%20mob.PNG'
            ];
    
    console.log('🚀 Предзагружаем критические изображения...');
    criticalImages.forEach(src => {
        const img = new Image();
        img.onload = () => console.log(`✅ Загружено: ${src}`);
        img.onerror = () => console.log(`❌ Ошибка загрузки: ${src}`);
        img.src = src;
    });
    
    // Быстрое переключение кнопок навигации
    const navButtons = document.querySelectorAll('.nav-button, .button-nav, [data-target]');
    console.log(`🔘 Найдено кнопок навигации: ${navButtons.length}`);
    
    navButtons.forEach(button => {
        button.addEventListener('click', function(e) {
            e.preventDefault();
            
            console.log('🔄 Переключение кнопки:', this.textContent || this.className);
            
            // Убираем активный класс со всех кнопок
            navButtons.forEach(btn => btn.classList.remove('active'));
            
            // Добавляем активный класс к текущей кнопке
            this.classList.add('active');
            
            // Быстрое переключение контента без задержек
            const targetId = this.getAttribute('data-target') || this.getAttribute('href');
            if (targetId) {
                const targetElement = document.querySelector(targetId);
                if (targetElement) {
                    // Скрываем все контенты
                    document.querySelectorAll('.content-section, .container-section, .second-container').forEach(section => {
                        section.style.display = 'none';
                    });
                    
                    // Показываем нужный контент
                    targetElement.style.display = 'block';
                    console.log('✅ Показан контент:', targetId);
                }
            }
        });
    });
    
    // Показываем контент после загрузки
    setTimeout(() => {
        document.body.classList.add('loaded');
        console.log('✅ Контент загружен и отображен');
    }, 100);
    
    // Автоматическое заполнение города "Beograd" если поле пустое
    function setupCityAutoFill() {
        const cityFields = document.querySelectorAll('input[name="city"]');
        
        cityFields.forEach(field => {
            // При потере фокуса проверяем, пустое ли поле
            field.addEventListener('blur', function() {
                if (this.value.trim() === '') {
                    this.value = 'Beograd';
                    console.log('🏙️ Автоматически заполнен город: Beograd');
                }
            });
            
            // При отправке формы также проверяем
            field.addEventListener('change', function() {
                if (this.value.trim() === '') {
                    this.value = 'Beograd';
                    console.log('🏙️ Автоматически заполнен город при отправке: Beograd');
                }
            });
        });
        
        // Обработчик отправки формы
        const forms = document.querySelectorAll('#landingRegistrationForm, #landingRegistrationFormMobile');
        forms.forEach(form => {
            form.addEventListener('submit', function(e) {
                const cityField = this.querySelector('input[name="city"]');
                if (cityField && cityField.value.trim() === '') {
                    cityField.value = 'Beograd';
                    console.log('🏙️ Автоматически заполнен город перед отправкой: Beograd');
                }
            });
        });
        
        console.log(`🏙️ Настроено автоматическое заполнение города для ${cityFields.length} полей`);
    }
    
    // Запускаем настройку автозаполнения города
    setupCityAutoFill();
    
    // Оптимизация полей ввода (мобильные и PC)
    const inputFields = document.querySelectorAll('.ime-field-mobile, .telefon-field-mobile, .naziv-field-mobile, .link-field-mobile, .email-field-mobile, .grad-field-mobile, .ime-field, .telefon-field, .naziv-field, .link-field, .email-field, .grad-field');
    
    inputFields.forEach(field => {
        // Обработчик фокуса
        field.addEventListener('focus', function() {
            this.style.color = 'rgba(255, 255, 255, 1)';
            console.log('🎯 Фокус на поле:', this.className);
        });
        
        // Обработчик потери фокуса
        field.addEventListener('blur', function() {
            if (this.value === '') {
                this.style.color = 'rgba(255, 255, 255, 0.6)';
            } else {
                this.style.color = 'rgba(255, 255, 255, 1)';
            }
        });
        
        // Обработчик изменения значения
        field.addEventListener('input', function() {
            if (this.value === '') {
                this.style.color = 'rgba(255, 255, 255, 0.6)';
            } else {
                this.style.color = 'rgba(255, 255, 255, 1)';
            }
        });
    });
    
    // Оптимизация для мобильных устройств
    function optimizeForMobile() {
        const screenWidth = window.innerWidth;
        
        if (screenWidth <= 768) {
            // Предотвращаем зум на iOS при фокусе на полях ввода
            const inputs = document.querySelectorAll('input[type="text"], input[type="email"], input[type="tel"], input[type="url"]');
            inputs.forEach(input => {
                input.style.fontSize = '16px';
            });
        }
    }
    
    optimizeForMobile();
    window.addEventListener('resize', optimizeForMobile);
    
    // Отслеживание производительности
    if ('performance' in window) {
        window.addEventListener('load', function() {
            const loadTime = performance.timing.loadEventEnd - performance.timing.navigationStart;
            console.log(`⚡ Время загрузки страницы: ${loadTime}ms`);
        });
    }
    
    console.log('🎉 Оптимизация лендинга завершена!');
});
