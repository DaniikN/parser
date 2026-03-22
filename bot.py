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
from selenium.common.exceptions import TimeoutException
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
import logging

# Принудительный вывод в консоль
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
)

# ===== ТОКЕН БОТА =====
TOKEN = os.getenv('BOT_TOKEN', '8611555727:AAHN6C0Bx7zu2RViyczSmc6YYyXD7skHWL8')
# ======================

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
    """Настройка Chrome для работы на Render"""
    print("🔄 Настройка Chrome драйвера...")
    sys.stdout.flush()
    
    options = webdriver.ChromeOptions()
    
    # Критические опции для сервера
    options.add_argument('--headless=new')
    options.add_argument('--no-sandbox')
    options.add_argument('--disable-dev-shm-usage')
    options.add_argument('--disable-gpu')
    options.add_argument('--disable-software-rasterizer')
    options.add_argument('--disable-blink-features=AutomationControlled')
    options.add_argument('--window-size=1920,1080')
    options.add_argument('--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36')
    
    # Убираем следы автоматизации
    options.add_experimental_option("excludeSwitches", ["enable-automation"])
    options.add_experimental_option('useAutomationExtension', False)
    
    try:
        print("📱 Создаю экземпляр Chrome...")
        sys.stdout.flush()
        
        driver = webdriver.Chrome(options=options)
        
        # Маскировка под реального пользователя
        driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
        
        print("✅ Chrome драйвер создан успешно!")
        sys.stdout.flush()
        return driver
        
    except Exception as e:
        print(f"❌ Ошибка создания драйвера: {e}")
        sys.stdout.flush()
        raise

def parser_worker():
    """Основная функция парсера"""
    global driver, is_running, stop_flag, stats
    
    print(f"\n{'='*60}")
    print(f"🚀 ЗАПУСК ПАРСЕРА")
    print(f"PID: {os.getpid()}")
    print(f"{'='*60}\n")
    sys.stdout.flush()
    
    try:
        # Создаем драйвер
        driver = setup_driver()
        
        # Проверяем работу Chrome
        print("🔍 Проверяю доступность Chrome...")
        driver.get("https://www.google.com")
        print(f"✅ Chrome работает, заголовок: {driver.title}")
        sys.stdout.flush()
        
        # Загружаем страницу Avito
        url = "https://www.avito.ru/all?q=%D1%80%D0%B5%D1%81%D0%B5%D0%BF%D1%88%D0%B5%D0%BD"
        print(f"🌐 Загружаю: {url}")
        driver.get(url)
        
        # Ждем загрузки
        time.sleep(5)
        print(f"📄 Заголовок страницы: {driver.title}")
        sys.stdout.flush()
        
        stats['start_time'] = time.time()
        cycle_number = 1
        
        while not stop_flag:
            print(f"\n{'#'*60}")
            print(f"ЦИКЛ #{cycle_number}")
            print(f"{'#'*60}")
            sys.stdout.flush()
            
            stats['current_cycle'] = cycle_number
            current_page = 1
            
            while not stop_flag:
                print(f"\n📄 Страница {current_page}")
                
                # Ждем появления объявлений
                try:
                    WebDriverWait(driver, 10).until(
                        EC.presence_of_element_located((By.CSS_SELECTOR, "[data-marker='item']"))
                    )
                except:
                    print("⚠️ Не дождался объявлений, пробую другие селекторы...")
                
                # Ищем объявления разными способами
                ads = []
                selectors = [
                    "[data-marker='item']",
                    "[data-marker='item-view']",
                    ".item__content"
                ]
                
                for selector in selectors:
                    ads = driver.find_elements(By.CSS_SELECTOR, selector)
                    if ads:
                        print(f"✅ Найдено {len(ads)} объявлений (селектор: {selector})")
                        break
                
                if not ads:
                    print("❌ Объявления не найдены")
                    # Делаем скриншот для отладки
                    try:
                        driver.save_screenshot('/tmp/avito_debug.png')
                        print("📸 Скриншот сохранен в /tmp/avito_debug.png")
                    except:
                        pass
                    break
                
                # Обрабатываем объявления
                for i, ad in enumerate(ads, 1):
                    if stop_flag:
                        break
                    
                    stats['total_ads_processed'] += 1
                    
                    # Получаем название
                    try:
                        title_elem = ad.find_element(By.CSS_SELECTOR, "[data-marker='item-title'], h3, a")
                        title = title_elem.text.strip()
                    except:
                        title = "Неизвестно"
                    
                    print(f"\n[{i}/{len(ads)}] {title[:60]}...")
                    
                    # Проверяем на пропуск
                    should_skip = False
                    for word in SKIP_WORDS:
                        if word.lower() in title.lower():
                            should_skip = True
                            break
                    
                    if should_skip:
                        stats['total_ads_skipped'] += 1
                        print(f"  ⏭ ПРОПУЩЕНО")
                    else:
                        # Получаем ссылку
                        try:
                            link_elem = ad.find_element(By.CSS_SELECTOR, "a")
                            ad_url = link_elem.get_attribute("href")
                            
                            if ad_url:
                                stats['total_ads_visited'] += 1
                                print(f"  🔗 ПОСЕЩАЮ")
                                
                                # Открываем в новой вкладке
                                driver.execute_script("window.open('');")
                                driver.switch_to.window(driver.window_handles[1])
                                
                                driver.get(ad_url)
                                time.sleep(random.randint(10, 15))
                                
                                # Закрываем вкладку
                                driver.close()
                                driver.switch_to.window(driver.window_handles[0])
                                
                                stats['total_wait_time'] += 15
                            else:
                                print(f"  ❌ НЕТ ССЫЛКИ")
                        except Exception as e:
                            print(f"  ❌ Ошибка: {e}")
                    
                    sys.stdout.flush()
                    
                    # Пауза между объявлениями
                    if not stop_flag and i < len(ads):
                        pause = random.randint(3, 5)
                        print(f"  ⏸ Пауза {pause} сек...")
                        time.sleep(pause)
                
                # Переход на следующую страницу
                try:
                    next_btn = driver.find_element(By.CSS_SELECTOR, "[data-marker='pagination-button/next']")
                    if next_btn.is_enabled():
                        print(f"\n➡ Переход на страницу {current_page + 1}")
                        next_btn.click()
                        time.sleep(3)
                        current_page += 1
                    else:
                        print("\n🏁 Конец списка")
                        break
                except:
                    print("\n🏁 Нет следующей страницы")
                    break
            
            if stop_flag:
                break
            
            # Обновляем страницу для нового цикла
            print(f"\n🔄 Обновляю главную страницу...")
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
            print("📱 Закрываю браузер...")
            driver.quit()
        is_running = False
        print("⏹ Парсер остановлен")
        sys.stdout.flush()

# Обработчики команд
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
            print("🚀 Запуск парсера по команде пользователя")
            sys.stdout.flush()
            
            stop_flag = False
            parser_thread = threading.Thread(target=parser_worker, daemon=True)
            parser_thread.start()
            is_running = True
            
            keyboard = [
                [InlineKeyboardButton(text="🚀 Запуск", callback_data="start_parser")],
                [InlineKeyboardButton(text="📊 Статус", callback_data="status")],
                [InlineKeyboardButton(text="⏹ Остановить", callback_data="stop_parser")]
            ]
            reply_markup = InlineKeyboardMarkup(inline_keyboard=keyboard)
            
            await callback.message.edit_text(
                "✅ Парсер запущен!\n\nНачинаю парсинг...\nСледите за логами в Render",
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
                f"📦 Цикл: **{stats['current_cycle']}**\n"
                f"📄 Страница: **{stats['current_page']}**\n\n"
                f"📈 **Обработано:**\n"
                f"• Всего: **{stats['total_ads_processed']}**\n"
                f"• Пропущено: **{stats['total_ads_skipped']}**\n"
                f"• Посещено: **{stats['total_ads_visited']}**\n"
                f"⏳ Время: **{stats['total_wait_time'] // 60} мин**"
            )
            
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
            print("⏹ Остановка парсера по команде пользователя")
            sys.stdout.flush()
            
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
                "⏹ Парсер остановлен",
                reply_markup=reply_markup
            )

async def main():
    print("🤖 Бот запускается...")
    await dp.start_polling(bot, skip_updates=True)

if __name__ == "__main__":
    print("="*60)
    print("ЗАПУСК БОТА НА RENDER")
    print("="*60)
    asyncio.run(main())
