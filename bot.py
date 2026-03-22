import asyncio
import time
import random
import threading
import os
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
import logging

# ===== ТОКЕН БОТА =====
TOKEN = '8550546011:AAHjO6rrtsCFGtyeznA-W8Wmo92bM1JuUr0'
# ======================

# ===== ДАННЫЕ ДЛЯ ВХОДА =====
login = '+79103368667'
pasword = 'nichipor2011'
# ============================

# ===== СПИСОК СЛОВ ДЛЯ ПРОПУСКА =====
SKIP_WORDS = [
    "Тэнтинель",
    "тентинель",
    "тэнтинель",
    "Tentinel",
    "tentinel",
    "Первый Контакт - Мебель от производителя"
]
# ======================================

# Настройка логирования
logging.basicConfig(level=logging.INFO)

# ===== ГЛОБАЛЬНЫЕ ПЕРЕМЕННЫЕ =====
bot = Bot(token=TOKEN)
dp = Dispatcher()

parser_thread = None
is_running = False
driver = None
stop_flag = False

# Статистика
stats = {
    'total_ads_processed': 0,
    'total_ads_skipped': 0,
    'total_ads_visited': 0,
    'total_wait_time': 0,
    'start_time': None,
    'current_cycle': 0,
    'current_page': 0
}
# ==================================

def setup_driver():
    """Настройка драйвера для headless режима на сервере"""
    options = Options()
    
    # Основные настройки для headless режима
    options.add_argument('--headless=new')  # Новый headless режим
    options.add_argument('--no-sandbox')
    options.add_argument('--disable-dev-shm-usage')
    options.add_argument('--disable-gpu')
    options.add_argument('--disable-blink-features=AutomationControlled')
    
    # Отключаем автоматизацию
    options.add_experimental_option("excludeSwitches", ["enable-automation"])
    options.add_experimental_option('useAutomationExtension', False)
    
    # Настройки для обхода детекта
    options.add_argument('--disable-web-security')
    options.add_argument('--disable-features=VizDisplayCompositor')
    options.add_argument('--disable-extensions')
    options.add_argument('--disable-setuid-sandbox')
    options.add_argument('--remote-debugging-port=9222')
    
    # Устанавливаем размер окна
    options.add_argument('--window-size=1920,1080')
    
    # Случайный user-agent
    user_agents = [
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36',
        'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
    ]
    options.add_argument(f'user-agent={random.choice(user_agents)}')
    
    # Путь к Chrome (на Render используется системный Chrome)
    chrome_path = os.environ.get('CHROME_PATH', '/usr/bin/google-chrome')
    
    try:
        service = Service()
        driver = webdriver.Chrome(service=service, options=options)
        
        # Убираем флаг webdriver
        driver.execute_cdp_cmd('Page.addScriptToEvaluateOnNewDocument', {
            'source': '''
                Object.defineProperty(navigator, 'webdriver', {
                    get: () => undefined
                });
                Object.defineProperty(navigator, 'plugins', {
                    get: () => [1, 2, 3, 4, 5]
                });
                Object.defineProperty(navigator, 'languages', {
                    get: () => ['ru-RU', 'ru']
                });
            '''
        })
        
        return driver
    except Exception as e:
        logging.error(f"Ошибка при создании драйвера: {e}")
        raise

def human_scroll(driver):
    """Скролл в headless режиме"""
    try:
        scroll_amount = random.randint(300, 700)
        driver.execute_script(f"window.scrollBy(0, {scroll_amount});")
        time.sleep(random.uniform(0.5, 1.5))
        driver.execute_script(f"window.scrollBy(0, {-scroll_amount//2});")
        time.sleep(random.uniform(0.5, 1.5))
    except:
        pass

def refresh_main_page(driver):
    """Обновляет главную страницу"""
    print(f"\n  → Обновляю главную страницу для получения новых объявлений...")
    
    time.sleep(random.uniform(1, 3))
    
    refresh_methods = [
        lambda: driver.refresh(),
        lambda: driver.get(driver.current_url),
        lambda: driver.execute_script("location.reload(true);")
    ]
    
    random.choice(refresh_methods)()
    time.sleep(random.uniform(3, 6))
    human_scroll(driver)
    print(f"  → Главная страница обновлена")

def should_skip_ad(title):
    """Проверяет, нужно ли пропустить объявление"""
    title_lower = title.lower()
    
    for word in SKIP_WORDS:
        if word.lower() in title_lower:
            return True
    return False

def get_all_ads(driver):
    """Получает все объявления на странице"""
    try:
        human_scroll(driver)
        
        WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "[data-marker='item']"))
        )
        
        ads = driver.find_elements(By.CSS_SELECTOR, "[data-marker='item']")
        print(f"Найдено объявлений на странице: {len(ads)}")
        return ads
    except TimeoutException:
        print("Не удалось загрузить объявления")
        return []

def get_ad_title(ad_element):
    """Получает название объявления"""
    try:
        selectors = [
            ".//div[@data-marker='item-title']",
            ".//h3",
            ".//a//strong",
            ".//a//p",
            ".//a[contains(@class, 'title')]",
            ".//div[contains(@class, 'title')]//span"
        ]
        
        for selector in selectors:
            try:
                title_element = ad_element.find_element(By.XPATH, selector)
                title = title_element.text.strip()
                if title:
                    return title
            except:
                continue
        
        links = ad_element.find_elements(By.XPATH, ".//a")
        for link in links:
            text = link.text.strip()
            if text and len(text) > 3:
                return text
                
        return "Название не найдено"
    except Exception as e:
        return f"Ошибка: {str(e)[:50]}"

def get_ad_link(ad_element):
    """Получает ссылку на объявление"""
    try:
        link_element = ad_element.find_element(By.XPATH, ".//a")
        return link_element.get_attribute("href")
    except:
        return None

def visit_ad(driver, url, ad_number, title):
    """Заходит на страницу объявления и скроллит (20-30 сек)"""
    wait_time = random.randint(20, 30)
    print(f"\n  → Захожу на объявление #{ad_number}: {title[:50]}...")
    print(f"  → Буду смотреть {wait_time} секунд")
    
    try:
        # Открываем в новой вкладке
        driver.execute_script("window.open('');")
        driver.switch_to.window(driver.window_handles[1])
        
        # Загружаем страницу
        driver.get(url)
        time.sleep(random.uniform(2, 4))
        
        # Получаем высоту страницы
        page_height = driver.execute_script("return document.body.scrollHeight")
        
        # Скроллим вниз
        current_scroll = 0
        scroll_step = random.randint(200, 400)
        scroll_time = int(wait_time * 0.4)
        
        start_scroll_time = time.time()
        
        while current_scroll < page_height - 500 and (time.time() - start_scroll_time) < scroll_time:
            current_scroll += scroll_step
            driver.execute_script(f"window.scrollTo({{top: {current_scroll}, behavior: 'smooth'}});")
            time.sleep(random.uniform(1.0, 2.0))
        
        # Возвращаемся наверх
        if time.time() - start_scroll_time < scroll_time:
            driver.execute_script("window.scrollTo({top: 0, behavior: 'smooth'});")
            time.sleep(random.uniform(2, 3))
        
        # Оставшееся время
        elapsed = time.time() - start_scroll_time
        remaining = max(0, wait_time - elapsed)
        
        if remaining > 2:
            print(f"  → Досматриваю объявление (осталось {int(remaining)} сек)...")
            time.sleep(remaining)
        
        print(f"  → Время на объявлении #{ad_number} закончилось")
        
        # Закрываем вкладку
        driver.close()
        driver.switch_to.window(driver.window_handles[0])
        
    except Exception as e:
        print(f"  → Ошибка: {e}")
        if len(driver.window_handles) > 1:
            driver.close()
        driver.switch_to.window(driver.window_handles[0])

def parser_worker():
    """Основная функция парсера"""
    global driver, is_running, stop_flag, stats
    
    print(f"\n{'='*60}")
    print(f"ЗАПУСК ПАРСЕРА")
    print(f"{'='*60}\n")
    
    try:
        driver = setup_driver()
        
        # Открываем страницу
        url = "https://www.avito.ru/all?q=%D1%80%D0%B5%D1%81%D0%B5%D0%BF%D1%88%D0%B5%D0%BD"
        print(f"Загружаю: {url}")
        driver.get(url)
        
        time.sleep(random.uniform(3, 6))
        human_scroll(driver)
        
        stats['start_time'] = time.time()
        cycle_number = 1
        
        while not stop_flag:
            print(f"\n{'#'*60}")
            print(f"ЦИКЛ №{cycle_number}")
            print(f"{'#'*60}")
            
            stats['current_cycle'] = cycle_number
            ads_processed = 0
            ads_skipped = 0
            ads_visited = 0
            current_page = 1
            cycle_start_time = time.time()
            
            while not stop_flag:
                print(f"\n{'='*60}")
                print(f"ЦИКЛ №{cycle_number} - СТРАНИЦА {current_page}")
                print(f"{'='*60}")
                
                stats['current_page'] = current_page
                time.sleep(random.uniform(1, 3))
                
                ads = get_all_ads(driver)
                
                if not ads:
                    print("Объявления не найдены")
                    break
                
                for i, ad in enumerate(ads, 1):
                    if stop_flag:
                        break
                        
                    ads_processed += 1
                    stats['total_ads_processed'] += 1
                    
                    print(f"\n[Цикл:{cycle_number} Страница:{current_page} Объявление:{i}]")
                    
                    title = get_ad_title(ad)
                    print(f"  Название: {title[:80]}...")
                    
                    ad_url = get_ad_link(ad)
                    
                    if should_skip_ad(title):
                        ads_skipped += 1
                        stats['total_ads_skipped'] += 1
                        print(f"  → ПРОПУЩЕНО")
                    else:
                        ads_visited += 1
                        stats['total_ads_visited'] += 1
                        print(f"  → ПОДХОДИТ")
                        
                        if ad_url:
                            wait_time = random.randint(20, 30)
                            stats['total_wait_time'] += wait_time
                            visit_ad(driver, ad_url, stats['total_ads_visited'], title)
                        else:
                            print(f"  → Нет ссылки")
                    
                    if stop_flag:
                        break
                    
                    pause = random.randint(5, 10)
                    print(f"  Пауза {pause} сек...")
                    time.sleep(pause)
                
                if stop_flag:
                    break
                
                # Переход на следующую страницу
                try:
                    driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
                    time.sleep(random.uniform(1, 2))
                    
                    next_button = driver.find_element(By.CSS_SELECTOR, "[data-marker='pagination-button/next']")
                    if next_button.is_enabled():
                        print(f"\n→ Переход на страницу {current_page + 1}...")
                        next_button.click()
                        time.sleep(random.randint(3, 7))
                        current_page += 1
                    else:
                        print("\n→ Достигнут конец списка")
                        break
                except Exception as e:
                    print(f"\n→ Ошибка перехода: {e}")
                    break
            
            if stop_flag:
                break
            
            # Статистика по циклу
            cycle_time = time.time() - cycle_start_time
            cycle_minutes = int(cycle_time // 60)
            cycle_seconds = int(cycle_time % 60)
            
            print(f"\n{'='*60}")
            print(f"ИТОГИ ЦИКЛА №{cycle_number}:")
            print(f"ОБРАБОТАНО: {ads_processed}")
            print(f"ПРОПУЩЕНО: {ads_skipped}")
            print(f"ПОСЕЩЕНО: {ads_visited}")
            print(f"ВРЕМЯ ЦИКЛА: {cycle_minutes} мин {cycle_seconds} сек")
            
            # Пауза перед обновлением
            pause_time = random.randint(20, 30)
            print(f"\nПауза {pause_time} секунд перед обновлением...")
            
            for i in range(pause_time, 0, -1):
                if stop_flag:
                    break
                if i % 10 == 0:
                    print(f"До обновления: {i} секунд")
                time.sleep(1)
            
            if stop_flag:
                break
            
            refresh_main_page(driver)
            
            extra_pause = random.randint(5, 10)
            print(f"\nДополнительная пауза {extra_pause} сек...")
            time.sleep(extra_pause)
            
            cycle_number += 1
            
    except Exception as e:
        print(f"Ошибка в парсере: {e}")
        logging.error(f"Parser error: {e}")
    finally:
        if driver:
            print(f"\nЗакрываю браузер...")
            driver.quit()
        is_running = False
        print("Парсер остановлен")

# ===== ОБРАБОТЧИКИ КОМАНД =====

@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    """Обработчик команды /start"""
    keyboard = [
        [InlineKeyboardButton(text="🚀 Запуск", callback_data="start_parser")],
        [InlineKeyboardButton(text="📊 Статус", callback_data="status")],
        [InlineKeyboardButton(text="⏹ Остановить", callback_data="stop_parser")]
    ]
    reply_markup = InlineKeyboardMarkup(inline_keyboard=keyboard)
    
    await message.answer(
        '🤖 Бот для парсинга Avito\n\n'
        'Выберите действие:',
        reply_markup=reply_markup
    )

@dp.callback_query()
async def process_callback(callback: types.CallbackQuery):
    """Обработчик нажатий на инлайн кнопки"""
    global parser_thread, is_running, stop_flag, stats
    
    await callback.answer()
    
    if callback.data == "start_parser":
        if is_running:
            await callback.message.edit_text("❌ Парсер уже запущен!")
        else:
            stop_flag = False
            parser_thread = threading.Thread(target=parser_worker)
            parser_thread.daemon = True
            parser_thread.start()
            is_running = True
            
            keyboard = [
                [InlineKeyboardButton(text="🚀 Запуск", callback_data="start_parser")],
                [InlineKeyboardButton(text="📊 Статус", callback_data="status")],
                [InlineKeyboardButton(text="⏹ Остановить", callback_data="stop_parser")]
            ]
            reply_markup = InlineKeyboardMarkup(inline_keyboard=keyboard)
            
            await callback.message.edit_text(
                "✅ Парсер успешно запущен!\n\n"
                "Начинаю парсинг объявлений...",
                reply_markup=reply_markup
            )
    
    elif callback.data == "status":
        if not is_running:
            keyboard = [
                [InlineKeyboardButton(text="🚀 Запуск", callback_data="start_parser")],
                [InlineKeyboardButton(text="📊 Статус", callback_data="status")],
                [InlineKeyboardButton(text="⏹ Остановить", callback_data="stop_parser")]
            ]
            reply_markup = InlineKeyboardMarkup(inline_keyboard=keyboard)
            
            await callback.message.edit_text(
                "❌ Парсер не запущен",
                reply_markup=reply_markup
            )
        else:
            runtime = 0
            if stats['start_time']:
                runtime = int(time.time() - stats['start_time'])
                hours = runtime // 3600
                minutes = (runtime % 3600) // 60
                seconds = runtime % 60
                runtime_str = f"{hours}ч {minutes}м {seconds}с"
            else:
                runtime_str = "0ч 0м 0с"
            
            status_text = (
                f"📊 **СТАТИСТИКА ПАРСЕРА**\n\n"
                f"🔄 Статус: **Активен**\n"
                f"⏱ Время работы: **{runtime_str}**\n"
                f"📦 Текущий цикл: **{stats['current_cycle']}**\n"
                f"📄 Текущая страница: **{stats['current_page']}**\n\n"
                f"📈 **Обработано:**\n"
                f"• Всего объявлений: **{stats['total_ads_processed']}**\n"
                f"• Пропущено: **{stats['total_ads_skipped']}**\n"
                f"• Посещено: **{stats['total_ads_visited']}**\n"
                f"⏳ Время на объявлениях: **{stats['total_wait_time'] // 60} мин {stats['total_wait_time'] % 60} сек**\n\n"
                f"📋 **Слова для пропуска:**\n"
            )
            
            for word in SKIP_WORDS:
                status_text += f"• `{word}`\n"
            
            keyboard = [
                [InlineKeyboardButton(text="🚀 Запуск", callback_data="start_parser")],
                [InlineKeyboardButton(text="📊 Статус", callback_data="status")],
                [InlineKeyboardButton(text="⏹ Остановить", callback_data="stop_parser")]
            ]
            reply_markup = InlineKeyboardMarkup(inline_keyboard=keyboard)
            
            await callback.message.edit_text(
                status_text,
                reply_markup=reply_markup,
                parse_mode='Markdown'
            )
    
    elif callback.data == "stop_parser":
        if not is_running:
            keyboard = [
                [InlineKeyboardButton(text="🚀 Запуск", callback_data="start_parser")],
                [InlineKeyboardButton(text="📊 Статус", callback_data="status")],
                [InlineKeyboardButton(text="⏹ Остановить", callback_data="stop_parser")]
            ]
            reply_markup = InlineKeyboardMarkup(inline_keyboard=keyboard)
            
            await callback.message.edit_text(
                "❌ Парсер не запущен",
                reply_markup=reply_markup
            )
        else:
            stop_flag = True
            is_running = False
            
            stats = {
                'total_ads_processed': 0,
                'total_ads_skipped': 0,
                'total_ads_visited': 0,
                'total_wait_time': 0,
                'start_time': None,
                'current_cycle': 0,
                'current_page': 0
            }
            
            keyboard = [
                [InlineKeyboardButton(text="🚀 Запуск", callback_data="start_parser")],
                [InlineKeyboardButton(text="📊 Статус", callback_data="status")],
                [InlineKeyboardButton(text="⏹ Остановить", callback_data="stop_parser")]
            ]
            reply_markup = InlineKeyboardMarkup(inline_keyboard=keyboard)
            
            await callback.message.edit_text(
                "⏹ Парсер остановлен!\n\nСтатистика сброшена.",
                reply_markup=reply_markup
            )

async def main():
    """Главная функция запуска бота"""
    await dp.start_polling(bot)

if __name__ == "__main__":
    print("Бот запущен...")
    asyncio.run(main())
