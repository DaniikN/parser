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
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
import logging

# ===== ТОКЕН БОТА =====
TOKEN = os.getenv('BOT_TOKEN', '8611555727:AAHN6C0Bx7zu2RViyczSmc6YYyXD7skHWL8')
# ======================

# ===== ДАННЫЕ ДЛЯ ВХОДА =====
login = os.getenv('AVITO_LOGIN', '+79103368667')
pasword = os.getenv('AVITO_PASSWORD', 'nichipor2011')
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
logger = logging.getLogger(__name__)

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

last_message_ids = {}
# ==================================

def setup_driver():
    options = webdriver.ChromeOptions()
    
    options.add_argument('--headless')
    options.add_argument('--no-sandbox')
    options.add_argument('--disable-dev-shm-usage')
    options.add_argument('--disable-gpu')
    options.add_argument('--window-size=1920,1080')
    options.add_argument('--disable-blink-features=AutomationControlled')
    options.add_experimental_option("excludeSwitches", ["enable-automation"])
    options.add_experimental_option('useAutomationExtension', False)
    
    user_agents = [
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36',
        'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
    ]
    options.add_argument(f'user-agent={random.choice(user_agents)}')
    
    driver = webdriver.Chrome(options=options)
    driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
    return driver

def human_scroll(driver):
    try:
        scroll_amount = random.randint(300, 700)
        driver.execute_script(f"window.scrollBy(0, {scroll_amount});")
        time.sleep(random.uniform(0.5, 1.5))
        driver.execute_script(f"window.scrollBy(0, {-scroll_amount//2});")
        time.sleep(random.uniform(0.5, 1.5))
    except:
        pass

def refresh_main_page(driver):
    print(f"\n  → Обновляю главную страницу...")
    time.sleep(random.uniform(1, 3))
    refresh_methods = [lambda: driver.refresh(), lambda: driver.get(driver.current_url)]
    random.choice(refresh_methods)()
    time.sleep(random.uniform(3, 6))
    human_scroll(driver)

def should_skip_ad(title):
    title_lower = title.lower()
    for word in SKIP_WORDS:
        if word.lower() in title_lower:
            return True
    return False

def get_all_ads(driver):
    try:
        human_scroll(driver)
        WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.CSS_SELECTOR, "[data-marker='item']")))
        ads = driver.find_elements(By.CSS_SELECTOR, "[data-marker='item']")
        print(f"Найдено объявлений: {len(ads)}")
        return ads
    except TimeoutException:
        print("Не удалось загрузить объявления")
        return []

def get_ad_title(ad_element):
    try:
        selectors = [".//div[@data-marker='item-title']", ".//h3", ".//a//strong"]
        for selector in selectors:
            try:
                title_element = ad_element.find_element(By.XPATH, selector)
                title = title_element.text.strip()
                if title:
                    return title
            except:
                continue
        return "Название не найдено"
    except:
        return "Ошибка"

def get_ad_link(ad_element):
    try:
        link_element = ad_element.find_element(By.XPATH, ".//a")
        return link_element.get_attribute("href")
    except:
        return None

def visit_ad(driver, url, ad_number, title):
    """Упрощенная версия - без скроллинга, только ожидание"""
    wait_time = random.randint(20, 30)
    print(f"\n  → Захожу на объявление #{ad_number}: {title[:50]}...")
    print(f"  → Буду смотреть {wait_time} секунд")
    
    try:
        # Открываем в новой вкладке
        driver.execute_script("window.open('');")
        driver.switch_to.window(driver.window_handles[1])
        
        # Загружаем страницу
        driver.get(url)
        
        # Просто ждем
        for i in range(wait_time, 0, -1):
            if i % 5 == 0 or i <= 3:
                print(f"     Осталось {i} сек")
            time.sleep(1)
        
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
    global driver, is_running, stop_flag, stats
    
    print(f"\n{'='*60}")
    print(f"ЗАПУСК ПАРСЕРА")
    print(f"{'='*60}\n")
    
    try:
        driver = setup_driver()
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
                
                try:
                    driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
                    time.sleep(random.uniform(1, 2))
                    next_button = driver.find_element(By.CSS_SELECTOR, "[data-marker='pagination-button/next']")
                    if next_button.is_enabled():
                        print(f"\n→ Переход на страницу {current_page + 1}")
                        next_button.click()
                        time.sleep(random.randint(3, 7))
                        current_page += 1
                    else:
                        print("\n→ Конец списка")
                        break
                except:
                    print("\n→ Нет следующей страницы")
                    break
            
            if stop_flag:
                break
            
            cycle_time = time.time() - cycle_start_time
            print(f"\n{'='*60}")
            print(f"ИТОГИ ЦИКЛА №{cycle_number}:")
            print(f"ОБРАБОТАНО: {ads_processed}")
            print(f"ПРОПУЩЕНО: {ads_skipped}")
            print(f"ПОСЕЩЕНО: {ads_visited}")
            print(f"ВРЕМЯ: {int(cycle_time//60)} мин {int(cycle_time%60)} сек")
            
            pause_time = random.randint(20, 30)
            print(f"\nПауза {pause_time} сек перед обновлением...")
            
            for i in range(pause_time, 0, -1):
                if stop_flag:
                    break
                if i % 10 == 0 or i == pause_time:
                    print(f"До обновления: {i} сек")
                time.sleep(1)
            
            if stop_flag:
                break
            
            refresh_main_page(driver)
            time.sleep(random.randint(5, 10))
            cycle_number += 1
            
    except Exception as e:
        print(f"Ошибка: {e}")
    finally:
        if driver:
            driver.quit()
        is_running = False
        print("Парсер остановлен")

# ===== ОБРАБОТЧИКИ КОМАНД =====

async def edit_or_send(message, text, reply_markup=None, parse_mode=None):
    chat_id = message.chat.id
    last_msg_id = last_message_ids.get(chat_id)
    
    if last_msg_id:
        try:
            return await bot.edit_message_text(
                text=text, chat_id=chat_id, message_id=last_msg_id,
                reply_markup=reply_markup, parse_mode=parse_mode
            )
        except:
            pass
    
    new_msg = await message.answer(text, reply_markup=reply_markup, parse_mode=parse_mode)
    last_message_ids[chat_id] = new_msg.message_id
    return new_msg

@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    keyboard = [
        [InlineKeyboardButton(text="🚀 Запуск", callback_data="start_parser")],
        [InlineKeyboardButton(text="📊 Статус", callback_data="status")],
        [InlineKeyboardButton(text="⏹ Остановить", callback_data="stop_parser")]
    ]
    reply_markup = InlineKeyboardMarkup(inline_keyboard=keyboard)
    await edit_or_send(message, '🤖 Бот для парсинга Avito\n\nВыберите действие:', reply_markup)

@dp.callback_query()
async def process_callback(callback: types.CallbackQuery):
    global parser_thread, is_running, stop_flag, stats
    
    await callback.answer()
    
    if callback.data == "start_parser":
        if is_running:
            await edit_or_send(callback.message, "❌ Парсер уже запущен!", callback.message.reply_markup)
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
            await edit_or_send(callback.message, "✅ Парсер запущен!\n\nНачинаю парсинг...", reply_markup)
    
    elif callback.data == "status":
        if not is_running:
            keyboard = [
                [InlineKeyboardButton(text="🚀 Запуск", callback_data="start_parser")],
                [InlineKeyboardButton(text="📊 Статус", callback_data="status")],
                [InlineKeyboardButton(text="⏹ Остановить", callback_data="stop_parser")]
            ]
            reply_markup = InlineKeyboardMarkup(inline_keyboard=keyboard)
            await edit_or_send(callback.message, "❌ Парсер не запущен", reply_markup)
        else:
            runtime = 0
            if stats['start_time']:
                runtime = int(time.time() - stats['start_time'])
                runtime_str = f"{runtime//3600}ч {(runtime%3600)//60}м {runtime%60}с"
            else:
                runtime_str = "0ч 0м 0с"
            
            status_text = (
                f"📊 **СТАТИСТИКА ПАРСЕРА**\n\n"
                f"🔄 Статус: **Активен**\n"
                f"⏱ Время работы: **{runtime_str}**\n"
                f"📦 Текущий цикл: **{stats['current_cycle']}**\n"
                f"📄 Текущая страница: **{stats['current_page']}**\n\n"
                f"📈 **Обработано:**\n"
                f"• Всего: **{stats['total_ads_processed']}**\n"
                f"• Пропущено: **{stats['total_ads_skipped']}**\n"
                f"• Посещено: **{stats['total_ads_visited']}**\n"
                f"⏳ Время: **{stats['total_wait_time'] // 60} мин {stats['total_wait_time'] % 60} сек**"
            )
            
            keyboard = [
                [InlineKeyboardButton(text="🚀 Запуск", callback_data="start_parser")],
                [InlineKeyboardButton(text="📊 Статус", callback_data="status")],
                [InlineKeyboardButton(text="⏹ Остановить", callback_data="stop_parser")]
            ]
            reply_markup = InlineKeyboardMarkup(inline_keyboard=keyboard)
            await edit_or_send(callback.message, status_text, reply_markup, parse_mode='Markdown')
    
    elif callback.data == "stop_parser":
        if not is_running:
            keyboard = [
                [InlineKeyboardButton(text="🚀 Запуск", callback_data="start_parser")],
                [InlineKeyboardButton(text="📊 Статус", callback_data="status")],
                [InlineKeyboardButton(text="⏹ Остановить", callback_data="stop_parser")]
            ]
            reply_markup = InlineKeyboardMarkup(inline_keyboard=keyboard)
            await edit_or_send(callback.message, "❌ Парсер не запущен", reply_markup)
        else:
            stop_flag = True
            is_running = False
            
            stats['total_ads_processed'] = 0
            stats['total_ads_skipped'] = 0
            stats['total_ads_visited'] = 0
            stats['total_wait_time'] = 0
            stats['start_time'] = None
            stats['current_cycle'] = 0
            stats['current_page'] = 0
            
            keyboard = [
                [InlineKeyboardButton(text="🚀 Запуск", callback_data="start_parser")],
                [InlineKeyboardButton(text="📊 Статус", callback_data="status")],
                [InlineKeyboardButton(text="⏹ Остановить", callback_data="stop_parser")]
            ]
            reply_markup = InlineKeyboardMarkup(inline_keyboard=keyboard)
            await edit_or_send(callback.message, "⏹ Парсер остановлен!\n\nСтатистика сброшена.", reply_markup)

async def main():
    logger.info("Бот запущен...")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
