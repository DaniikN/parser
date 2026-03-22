import asyncio
import time
import random
import threading
import os
import sys
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, WebDriverException
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
import logging

# Принудительно выводим все сообщения в консоль
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
)

# ===== ТОКЕН БОТА =====
TOKEN = os.getenv('BOT_TOKEN', '8611555727:AAHN6C0Bx7zu2RViyczSmc6YYyXD7skHWL8')
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

bot = Bot(token=TOKEN)
dp = Dispatcher()

parser_thread = None
is_running = False
driver = None
stop_flag = False

stats = {
    'total_ads_processed': 0,
    'total_ads_skipped': 0,
    'total_ads_visited': 0,
    'total_wait_time': 0,
    'start_time': None,
    'current_cycle': 0,
    'current_page': 0
}

def setup_driver():
    """Настройка драйвера для работы на Render"""
    print("🔄 Настройка Chrome драйвера...")
    
    options = webdriver.ChromeOptions()
    
    # Критические опции для работы на сервере
    options.add_argument('--headless=new')  # Используем новый headless режим
    options.add_argument('--no-sandbox')
    options.add_argument('--disable-dev-shm-usage')
    options.add_argument('--disable-gpu')
    options.add_argument('--disable-software-rasterizer')
    options.add_argument('--disable-blink-features=AutomationControlled')
    options.add_argument('--window-size=1920,1080')
    
    # Убираем автоматизацию
    options.add_experimental_option("excludeSwitches", ["enable-automation"])
    options.add_experimental_option('useAutomationExtension', False)
    
    # User-Agent
    options.add_argument('user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36')
    
    try:
        print("📱 Создаю экземпляр Chrome...")
        driver = webdriver.Chrome(options=options)
        
        # Убираем флаг webdriver
        driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
        
        print("✅ Chrome драйвер успешно создан")
        return driver
    except Exception as e:
        print(f"❌ Ошибка при создании драйвера: {e}")
        raise

def human_scroll(driver):
    try:
        scroll_amount = random.randint(300, 700)
        driver.execute_script(f"window.scrollBy(0, {scroll_amount});")
        time.sleep(random.uniform(0.5, 1.5))
    except:
        pass

def should_skip_ad(title):
    title_lower = title.lower()
    for word in SKIP_WORDS:
        if word.lower() in title_lower:
            return True
    return False

def get_ad_title(ad_element):
    try:
        selectors = [
            ".//div[@data-marker='item-title']",
            ".//h3",
            ".//a//strong"
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
    try:
        link_element = ad_element.find_element(By.XPATH, ".//a")
        return link_element.get_attribute("href")
    except:
        return None

def visit_ad(driver, url, ad_number, title):
    """Заходит на страницу объявления"""
    wait_time = random.randint(15, 20)  # Уменьшил время для Render
    print(f"\n  → Захожу на объявление #{ad_number}")
    
    try:
        # Открываем в новой вкладке
        driver.execute_script("window.open('');")
        driver.switch_to.window(driver.window_handles[1])
        
        driver.get(url)
        time.sleep(random.uniform(2, 4))
        
        # Простой скролл
        for _ in range(3):
            driver.execute_script(f"window.scrollBy(0, {random.randint(200, 500)});")
            time.sleep(random.uniform(1, 2))
        
        print(f"  → Просмотр объявления ({wait_time} сек)")
        time.sleep(wait_time)
        
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
    print(f"PID процесса: {os.getpid()}")
    print(f"{'='*60}\n")
    sys.stdout.flush()
    
    try:
        print("🔧 Инициализация драйвера...")
        driver = setup_driver()
        
        # Проверяем, что драйвер работает
        print(f"✅ Драйвер создан, версия: {driver.capabilities['browserVersion']}")
        
        # Открываем страницу
        url = "https://www.avito.ru/all?q=%D1%80%D0%B5%D1%81%D0%B5%D0%BF%D1%88%D0%B5%D0%BD"
        print(f"🌐 Загружаю страницу: {url}")
        driver.get(url)
        
        # Ждем загрузки
        print("⏳ Ожидаю загрузки страницы...")
        time.sleep(5)
        
        # Проверяем заголовок страницы
        print(f"📄 Заголовок страницы: {driver.title}")
        
        # Проверяем наличие объявлений
        print("🔍 Ищу объявления...")
        
        # Пробуем разные селекторы для поиска объявлений
        selectors_to_try = [
            "[data-marker='item']",
            "[data-marker='item-view']",
            ".item__content",
            "[class*='item']"
        ]
        
        found_ads = False
        for selector in selectors_to_try:
            try:
                ads = driver.find_elements(By.CSS_SELECTOR, selector)
                print(f"  Селектор '{selector}': найдено {len(ads)} элементов")
                if len(ads) > 0:
                    found_ads = True
                    break
            except Exception as e:
                print(f"  Ошибка при поиске '{selector}': {e}")
        
        if not found_ads:
            print("⚠️ НЕ УДАЛОСЬ НАЙТИ ОБЪЯВЛЕНИЯ!")
            print("📸 Сохраняю скриншот страницы для отладки...")
            try:
                driver.save_screenshot('/tmp/avito_debug.png')
                print("✅ Скриншот сохранен в /tmp/avito_debug.png")
            except:
                print("❌ Не удалось сохранить скриншот")
            
            print(f"📄 HTML страницы (первые 500 символов):")
            print(driver.page_source[:500])
            sys.stdout.flush()
            return
        
        stats['start_time'] = time.time()
        cycle_number = 1
        
        while not stop_flag:
            print(f"\n{'#'*60}")
            print(f"ЦИКЛ №{cycle_number}")
            print(f"{'#'*60}")
            sys.stdout.flush()
            
            stats['current_cycle'] = cycle_number
            current_page = 1
            
            while not stop_flag:
                print(f"\nСтраница {current_page}")
                
                # Получаем объявления
                ads = driver.find_elements(By.CSS_SELECTOR, "[data-marker='item']")
                if not ads:
                    ads = driver.find_elements(By.CSS_SELECTOR, "[data-marker='item-view']")
                
                print(f"Найдено объявлений: {len(ads)}")
                
                if not ads:
                    print("Объявления не найдены, выхожу")
                    break
                
                for i, ad in enumerate(ads, 1):
                    if stop_flag:
                        break
                    
                    stats['total_ads_processed'] += 1
                    
                    title = get_ad_title(ad)
                    print(f"\n[{i}/{len(ads)}] {title[:60]}...")
                    
                    if should_skip_ad(title):
                        stats['total_ads_skipped'] += 1
                        print(f"  → ПРОПУЩЕНО")
                    else:
                        ad_url = get_ad_link(ad)
                        if ad_url:
                            stats['total_ads_visited'] += 1
                            print(f"  → ПОСЕЩАЮ")
                            wait_time = random.randint(15, 20)
                            stats['total_wait_time'] += wait_time
                            visit_ad(driver, ad_url, stats['total_ads_visited'], title)
                        else:
                            print(f"  → НЕТ ССЫЛКИ")
                    
                    sys.stdout.flush()
                    time.sleep(random.randint(3, 5))
                
                # Переход на следующую страницу
                try:
                    next_button = driver.find_element(By.CSS_SELECTOR, "[data-marker='pagination-button/next']")
                    if next_button.is_enabled():
                        print(f"\n→ Переход на следующую страницу...")
                        next_button.click()
                        time.sleep(3)
                        current_page += 1
                    else:
                        break
                except:
                    break
            
            # Обновление страницы
            print(f"\n→ Обновление главной страницы...")
            driver.refresh()
            time.sleep(5)
            cycle_number += 1
            
    except Exception as e:
        print(f"❌ КРИТИЧЕСКАЯ ОШИБКА: {e}")
        import traceback
        traceback.print_exc()
        sys.stdout.flush()
    finally:
        if driver:
            print(f"\n📱 Закрываю браузер...")
            driver.quit()
        is_running = False
        print("⏹ Парсер остановлен")
        sys.stdout.flush()

# Обработчики команд (оставляем как было)
@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    keyboard = [
        [InlineKeyboardButton(text="🚀 Запуск", callback_data="start_parser")],
        [InlineKeyboardButton(text="📊 Статус", callback_data="status")],
        [InlineKeyboardButton(text="⏹ Остановить", callback_data="stop_parser")]
    ]
    reply_markup = InlineKeyboardMarkup(inline_keyboard=keyboard)
    
    await message.answer(
        '🤖 Бот для парсинга Avito\n\nВыберите действие:',
        reply_markup=reply_markup
    )

@dp.callback_query()
async def process_callback(callback: types.CallbackQuery):
    global parser_thread, is_running, stop_flag, stats
    
    await callback.answer()
    
    if callback.data == "start_parser":
        if is_running:
            await callback.message.edit_text("❌ Парсер уже запущен!")
        else:
            print("🚀 Пользователь запустил парсер")
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
                "✅ Парсер успешно запущен!\n\nНачинаю парсинг объявлений...",
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
            print("⏹ Пользователь остановил парсер")
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
    print("🤖 Бот запускается...")
    print(f"Bot token: {TOKEN[:10]}...")
    await dp.start_polling(bot, skip_updates=True)

if __name__ == "__main__":
    print("="*60)
    print("ЗАПУСК БОТА НА RENDER")
    print("="*60)
    asyncio.run(main())
