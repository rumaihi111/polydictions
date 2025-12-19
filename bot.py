import os
import json
import asyncio
import logging
import re
from datetime import datetime
from typing import Optional, Dict, List, Set
from pathlib import Path

import aiohttp
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import Message, BotCommand, MenuButtonCommands
from aiogram.enums import ParseMode
from aiogram.client.default import DefaultBotProperties
from dotenv import load_dotenv


# FSM States for waiting user input
class UserStates(StatesGroup):
    waiting_for_deal_link = State()
    waiting_for_watch_link = State()

# Import new features
from features import Watchlist, Categories, Alerts, NewsTracker
from payment_system import PaymentSystem
from agent import agent_manager

env_path = Path(__file__).parent / '.env'
load_dotenv(dotenv_path=env_path)

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

POLYMARKET_API = "https://gamma-api.polymarket.com"
USERS_FILE = "users.json"
SEEN_EVENTS_FILE = "seen_events.json"
KEYWORDS_FILE = "keywords.json"
PAUSED_USERS_FILE = "paused_users.json"
POSTED_EVENTS_FILE = "posted_events.json"
CHECK_INTERVAL = 60  # Check every 60 seconds (1 minute)
NEWS_CHECK_INTERVAL = 300  # Check watchlist news every 5 minutes

# Channel for broadcasting (loaded from config)
CHANNEL_ID = None
try:
    from config import CHANNEL_ID
except ImportError:
    pass

subscribed_users: Set[int] = set()
seen_events: Set[str] = set()
user_keywords: Dict[int, List[str]] = {}
paused_users: Set[int] = set()


class Storage:

    @staticmethod
    def load_users() -> Set[int]:
        if Path(USERS_FILE).exists():
            try:
                with open(USERS_FILE, 'r') as f:
                    data = json.load(f)
                    return set(data.get('users', []))
            except Exception as e:
                logger.error(f"Error loading users: {e}")
        return set()

    @staticmethod
    def save_users(users: Set[int]):
        try:
            with open(USERS_FILE, 'w') as f:
                json.dump({'users': list(users)}, f, indent=2)
            logger.info(f"Saved {len(users)} users")
        except Exception as e:
            logger.error(f"Error saving users: {e}")

    @staticmethod
    def load_seen_events() -> Set[str]:
        if Path(SEEN_EVENTS_FILE).exists():
            try:
                with open(SEEN_EVENTS_FILE, 'r') as f:
                    data = json.load(f)
                    return set(data.get('events', []))
            except Exception as e:
                logger.error(f"Error loading events: {e}")
        return set()

    @staticmethod
    def save_seen_events(events: Set[str]):
        try:
            with open(SEEN_EVENTS_FILE, 'w') as f:
                json.dump({'events': list(events)}, f, indent=2)
        except Exception as e:
            logger.error(f"Error saving events: {e}")

    @staticmethod
    def load_keywords() -> Dict[int, List[str]]:
        if Path(KEYWORDS_FILE).exists():
            try:
                with open(KEYWORDS_FILE, 'r') as f:
                    data = json.load(f)
                    # Convert string keys back to integers
                    return {int(k): v for k, v in data.items()}
            except Exception as e:
                logger.error(f"Error loading keywords: {e}")
        return {}

    @staticmethod
    def save_keywords(keywords: Dict[int, List[str]]):
        try:
            with open(KEYWORDS_FILE, 'w') as f:
                json.dump(keywords, f, indent=2)
            logger.info(f"Saved keywords for {len(keywords)} users")
        except Exception as e:
            logger.error(f"Error saving keywords: {e}")

    @staticmethod
    def load_paused_users() -> Set[int]:
        if Path(PAUSED_USERS_FILE).exists():
            try:
                with open(PAUSED_USERS_FILE, 'r') as f:
                    data = json.load(f)
                    return set(data.get('users', []))
            except Exception as e:
                logger.error(f"Error loading paused users: {e}")
        return set()

    @staticmethod
    def save_paused_users(users: Set[int]):
        try:
            with open(PAUSED_USERS_FILE, 'w') as f:
                json.dump({'users': list(users)}, f, indent=2)
            logger.info(f"Saved {len(users)} paused users")
        except Exception as e:
            logger.error(f"Error saving paused users: {e}")

    @staticmethod
    def load_posted_events() -> List[Dict]:
        """Load recently posted events for extension sync"""
        if Path(POSTED_EVENTS_FILE).exists():
            try:
                with open(POSTED_EVENTS_FILE, 'r') as f:
                    data = json.load(f)
                    return data.get('events', [])
            except Exception as e:
                logger.error(f"Error loading posted events: {e}")
        return []

    @staticmethod
    def save_posted_event(event_data: Dict):
        """Save posted event for extension sync (keep last 50)"""
        try:
            events = Storage.load_posted_events()

            # Add new event with timestamp
            posted_event = {
                'id': event_data.get('id'),
                'slug': event_data.get('slug'),
                'title': event_data.get('title'),
                'volume': event_data.get('volume'),
                'liquidity': event_data.get('liquidity'),
                'markets': event_data.get('markets', []),
                'posted_at': datetime.now().isoformat()
            }

            # Add to beginning (newest first)
            events.insert(0, posted_event)

            # Keep only last 50
            events = events[:50]

            with open(POSTED_EVENTS_FILE, 'w') as f:
                json.dump({'events': events}, f, indent=2)

            logger.info(f"Saved posted event: {event_data.get('title', 'N/A')[:50]}")
        except Exception as e:
            logger.error(f"Error saving posted event: {e}")


class PolymarketAPI:

    @staticmethod
    def matches_keywords(event_data: Dict, keywords: List[str]) -> bool:
        """
        Check if event matches any of the user's keywords.
        Supports:
        - Simple word matching (case-insensitive)
        - Phrase matching with quotes
        - OR logic (comma-separated keywords)

        Examples:
        - btc, eth -> matches events with 'btc' OR 'eth'
        - "united states", election -> matches events with phrase "united states" OR word "election"
        """
        if not keywords:
            return True  # No filters = show all events

        title = event_data.get('title', '').lower()

        # Also check market questions
        markets = event_data.get('markets', [])
        market_text = ' '.join([m.get('question', '').lower() for m in markets])

        # Combined searchable text
        searchable = f"{title} {market_text}"

        # Check each keyword (OR logic)
        for keyword in keywords:
            keyword = keyword.strip()
            if not keyword:
                continue

            # Check if it's a phrase (has quotes)
            if (keyword.startswith('"') and keyword.endswith('"')) or \
               (keyword.startswith("'") and keyword.endswith("'")):
                # Phrase matching - remove quotes
                phrase = keyword[1:-1].lower()
                if phrase in searchable:
                    return True
            else:
                # Simple word matching
                if keyword.lower() in searchable:
                    return True

        return False

    @staticmethod
    async def fetch_market_context(event_slug: str, market_question: str = None, retry: int = 0) -> Optional[str]:
        """
        Fetch Market Context from Polymarket API.
        This provides AI-generated context about the market/event.
        IMPORTANT: Must use event_slug in the prompt parameter, not market_question.
        """
        if not event_slug:
            logger.error("Cannot fetch Market Context: event_slug is empty")
            return None

        # The API only accepts event slugs, not market questions
        url = f"https://polymarket.com/api/grok/event-summary?prompt={event_slug}"

        # Create a timeout object with 120 seconds total timeout
        timeout = aiohttp.ClientTimeout(total=120)

        # Create SSL context that doesn't verify certificates (fixes Windows SSL issues)
        import ssl
        ssl_context = ssl.create_default_context()
        ssl_context.check_hostname = False
        ssl_context.verify_mode = ssl.CERT_NONE

        try:
            connector = aiohttp.TCPConnector(ssl=ssl_context)
            async with aiohttp.ClientSession(timeout=timeout, connector=connector) as session:
                logger.info(f"Fetching Market Context for: {event_slug} (attempt {retry + 1}/2)")
                async with session.post(
                    url,
                    headers={
                        'Content-Type': 'application/json',
                        'Accept': '*/*',
                        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
                    }
                ) as response:
                    logger.info(f"Market Context API status: {response.status}")
                    if response.status == 200:
                        text = await response.text()
                        logger.info(f"Received response of length: {len(text)} chars")
                        if text and len(text) > 50:
                            # Remove sources block if present
                            if '__SOURCES__' in text:
                                text = text.split('__SOURCES__')[0].strip()
                            logger.info(f"✓ Got Market Context (length: {len(text)} chars)")
                            return text
                        else:
                            logger.warning(f"Market Context response too short: {len(text)} chars")
                            logger.warning(f"Response: {text}")
                            # Retry if response is too short and we haven't retried yet
                            if retry < 1 and len(text) < 50:
                                logger.info("Retrying due to short response...")
                                await asyncio.sleep(2)
                                return await PolymarketAPI.fetch_market_context(event_slug, market_question, retry + 1)
                    elif response.status == 400:
                        logger.error(f"Bad Request (400) - Invalid event slug: {event_slug}")
                        error_text = await response.text()
                        logger.error(f"Error response: {error_text}")
                    else:
                        logger.warning(f"Market Context API returned status: {response.status}")
                        error_text = await response.text()
                        logger.warning(f"Error response: {error_text}")
                        # Retry on 5xx errors
                        if retry < 1 and response.status >= 500:
                            logger.info("Retrying due to server error...")
                            await asyncio.sleep(3)
                            return await PolymarketAPI.fetch_market_context(event_slug, market_question, retry + 1)
        except asyncio.TimeoutError:
            logger.error(f"Market Context request timed out after 120 seconds (attempt {retry + 1}/2)")
            # Retry once on timeout
            if retry < 1:
                logger.info("Retrying after timeout...")
                await asyncio.sleep(2)
                return await PolymarketAPI.fetch_market_context(event_slug, market_question, retry + 1)
        except aiohttp.ClientError as e:
            logger.error(f"Network error fetching Market Context: {e}")
        except Exception as e:
            logger.error(f"Error fetching Market Context: {e}")
            import traceback
            logger.error(traceback.format_exc())

        return None

    @staticmethod
    async def fetch_ai_analysis(event_slug: str, event_id: str = None) -> Optional[str]:
        """Fetch AI analysis from Polymarket Grok API (legacy method, now uses fetch_market_context)"""
        return await PolymarketAPI.fetch_market_context(event_slug)

    @staticmethod
    async def fetch_event_by_slug(slug: str) -> Optional[Dict]:
        url = f"{POLYMARKET_API}/events"
        params = {"slug": slug}

        import ssl
        ssl_context = ssl.create_default_context()
        ssl_context.check_hostname = False
        ssl_context.verify_mode = ssl.CERT_NONE

        try:
            connector = aiohttp.TCPConnector(ssl=ssl_context)
            async with aiohttp.ClientSession(connector=connector) as session:
                async with session.get(url, params=params, timeout=15) as response:
                    if response.status == 200:
                        events = await response.json()
                        if isinstance(events, list) and len(events) > 0:
                            return events[0]
                    else:
                        logger.error(f"Failed to fetch event: {response.status}")
        except Exception as e:
            logger.error(f"Error fetching event '{slug}': {e}")

        return None

    @staticmethod
    async def fetch_recent_events(limit: int = 20) -> List[Dict]:
        url = f"{POLYMARKET_API}/events"
        params = {
            "limit": limit,
            "offset": 0,
            "closed": "false",
            "active": "true",
            "order": "createdAt",
            "ascending": "false"
        }

        import ssl
        ssl_context = ssl.create_default_context()
        ssl_context.check_hostname = False
        ssl_context.verify_mode = ssl.CERT_NONE

        try:
            connector = aiohttp.TCPConnector(ssl=ssl_context)
            async with aiohttp.ClientSession(connector=connector) as session:
                async with session.get(url, params=params, timeout=15) as response:
                    if response.status == 200:
                        events = await response.json()
                        return events if isinstance(events, list) else []
                    else:
                        logger.error(f"Failed to fetch events: {response.status}")
        except Exception as e:
            logger.error(f"Error fetching events: {e}")

        return []

    @staticmethod
    def parse_polymarket_url(url: str) -> Optional[str]:
        pattern = r'polymarket\.com/event/([a-zA-Z0-9\-]+)'
        match = re.search(pattern, url)
        if match:
            return match.group(1)
        return None

    @staticmethod
    def format_money(value) -> str:
        try:
            num = float(value) if value else 0
            return f"${num:,.0f}"
        except:
            return "$0"

    @staticmethod
    def format_date(date_str: str) -> str:
        if not date_str:
            return "N/A"
        try:
            dt = datetime.fromisoformat(date_str.replace('Z', '+00:00'))
            return dt.strftime('%B %d, %Y at %H:%M UTC')
        except:
            return date_str

    @staticmethod
    def calculate_totals(markets: List[Dict]) -> tuple:
        total_liquidity = 0.0
        total_volume = 0.0
        for market in markets:
            try:
                liquidity = float(market.get('liquidityNum', market.get('liquidity', 0)) or 0)
                total_liquidity += liquidity
            except:
                pass

            try:
                volume = float(market.get('volumeNum', market.get('volume', 0)) or 0)
                total_volume += volume
            except:
                pass

        return total_liquidity, total_volume

    @staticmethod
    def format_event(event_data: Dict) -> str:
        try:
            title = event_data.get('title', 'Unknown Event')
            slug = event_data.get('slug', '')
            markets = event_data.get('markets', [])

            if not markets:
                return "No market data available"

            event_liquidity = event_data.get('liquidity')
            event_volume = event_data.get('volume')

            if event_liquidity is not None and event_volume is not None:
                total_liquidity = float(event_liquidity)
                total_volume = float(event_volume)
            else:
                total_liquidity, total_volume = PolymarketAPI.calculate_totals(markets)

            end_date = event_data.get('endDate')
            if not end_date and markets:
                end_date = markets[0].get('endDate') or markets[0].get('end_date_iso')

            formatted_date = PolymarketAPI.format_date(end_date)

            msg = []
            msg.append(f"🟠 <b>{title}</b>\n")
            msg.append(f"🔗 <b>Link:</b> https://polymarket.com/event/{slug}\n")
            msg.append(f"🟠 <b>Market stats:</b>")
            msg.append(f"<b>Closes:</b> {formatted_date}")
            msg.append(f"<b>Total Liquidity:</b> {PolymarketAPI.format_money(total_liquidity)}")
            msg.append(f"<b>Total Volume:</b> {PolymarketAPI.format_money(total_volume)}\n")

            if len(markets) == 1:
                market = markets[0]
                outcomes = market.get('outcomes', [])

                if outcomes and isinstance(outcomes, str):
                    try:
                        outcomes = json.loads(outcomes)
                    except:
                        outcomes = []

                outcome_prices = market.get('outcomePrices')
                if isinstance(outcome_prices, str):
                    try:
                        outcome_prices = json.loads(outcome_prices)
                    except:
                        outcome_prices = []

                if len(outcomes) == 2:
                    msg.append("🟠 <b>Current Odds:</b>")
                    for idx, outcome in enumerate(outcomes):
                        name = outcome.get('name', outcome) if isinstance(outcome, dict) else outcome
                        if outcome_prices and idx < len(outcome_prices):
                            price = float(outcome_prices[idx])
                            percentage = price * 100 if price <= 1 else price
                            msg.append(f"  • {name}: {percentage:.1f}%")
                else:
                    msg.append("🟠 <b>Options:</b>")
                    for idx, outcome in enumerate(outcomes):
                        name = outcome.get('name', outcome) if isinstance(outcome, dict) else outcome
                        if outcome_prices and idx < len(outcome_prices):
                            price = float(outcome_prices[idx])
                            percentage = price * 100 if price <= 1 else price
                            msg.append(f"  {idx + 1}. {name}: {percentage:.1f}%")
            else:
                # Filter markets with valid data
                valid_markets = []
                for market in markets:
                    market_outcomes = market.get('outcomes', [])
                    if isinstance(market_outcomes, str):
                        try:
                            market_outcomes = json.loads(market_outcomes)
                        except:
                            market_outcomes = []

                    market_prices = market.get('outcomePrices')
                    if isinstance(market_prices, str):
                        try:
                            market_prices = json.loads(market_prices)
                        except:
                            market_prices = []

                    # Only include markets with valid outcomes and prices
                    if market_outcomes and market_prices:
                        valid_markets.append(market)

                msg.append(f"🟠 <b>Markets ({len(valid_markets)}):</b>")
                for idx, market in enumerate(valid_markets, 1):
                    question = market.get('question', f'Market {idx}')
                    msg.append(f"  {idx}. {question}")

                    market_outcomes = market.get('outcomes', [])
                    if isinstance(market_outcomes, str):
                        try:
                            market_outcomes = json.loads(market_outcomes)
                        except:
                            market_outcomes = []

                    market_prices = market.get('outcomePrices')
                    if isinstance(market_prices, str):
                        try:
                            market_prices = json.loads(market_prices)
                        except:
                            market_prices = []

                    if market_outcomes and market_prices:
                        for o_idx, outcome in enumerate(market_outcomes[:5]):
                            o_name = outcome.get('name', outcome) if isinstance(outcome, dict) else outcome
                            if o_idx < len(market_prices):
                                o_price = float(market_prices[o_idx])
                                o_percentage = o_price * 100 if o_price <= 1 else o_price
                                msg.append(f"     • {o_name}: {o_percentage:.1f}%")

            return "\n".join(msg)

        except Exception as e:
            logger.error(f"Error formatting event: {e}")
            return "Error formatting event data"

    @staticmethod
    async def format_event_with_ai(event_data: Dict) -> str:
        """Format event with Market Context from Polymarket"""
        # Get basic format
        basic_msg = PolymarketAPI.format_event(event_data)

        # Get the market question for more specific context
        slug = event_data.get('slug', '')
        markets = event_data.get('markets', [])
        market_question = None

        # Use the first market's question if available
        if markets and len(markets) > 0:
            market_question = markets[0].get('question')

        # Fetch Market Context from Polymarket
        market_context = await PolymarketAPI.fetch_market_context(slug, market_question)

        if market_context:
            context_msg = f"\n\n🧠 <b>Market Context:</b>\n{market_context}"
            # Don't truncate - show full context
            return basic_msg + context_msg

        return basic_msg


class PolydictionsBot:

    def __init__(self, token: str):
        self.bot = Bot(
            token=token,
            default=DefaultBotProperties(parse_mode=ParseMode.HTML)
        )
        self.dp = Dispatcher()

        # Initialize new features
        self.watchlist = Watchlist()
        self.categories = Categories()
        self.alerts = Alerts()
        self.news_tracker = NewsTracker()
        self.payment_system = PaymentSystem()

        self.setup_handlers()

        global subscribed_users, seen_events, user_keywords, paused_users
        subscribed_users = Storage.load_users()
        seen_events = Storage.load_seen_events()
        user_keywords = Storage.load_keywords()
        paused_users = Storage.load_paused_users()

        logger.info(f"Loaded {len(subscribed_users)} users, {len(seen_events)} events, "
                   f"{len(user_keywords)} keyword filters, {len(paused_users)} paused users")

    def setup_handlers(self):
        self.dp.message.register(self.cmd_start, Command("start"))
        self.dp.message.register(self.cmd_deal, Command("deal"))
        self.dp.message.register(self.cmd_help, Command("help"))
        self.dp.message.register(self.cmd_keywords, Command("keywords"))
        self.dp.message.register(self.cmd_pause, Command("pause"))
        self.dp.message.register(self.cmd_resume, Command("resume"))

        # New feature handlers
        self.dp.message.register(self.cmd_watch, Command("watch"))
        self.dp.message.register(self.cmd_unwatch, Command("unwatch"))
        self.dp.message.register(self.cmd_watchlist, Command("watchlist"))
        self.dp.message.register(self.cmd_category, Command("category"))
        self.dp.message.register(self.cmd_categories, Command("categories"))
        self.dp.message.register(self.cmd_alert, Command("alert"))
        self.dp.message.register(self.cmd_alerts, Command("alerts"))
        self.dp.message.register(self.cmd_rmalert, Command("rmalert"))
        self.dp.message.register(self.cmd_interval, Command("interval"))
        
        # Wallet commands
        self.dp.message.register(self.cmd_balance, Command("balance"))
        self.dp.message.register(self.cmd_withdraw, Command("withdraw"))
        self.dp.message.register(self.cmd_deposit, Command("deposit"))
        self.dp.message.register(self.cmd_mystatus, Command("mystatus"))

        # State handlers - waiting for user input
        self.dp.message.register(self.handle_deal_link, StateFilter(UserStates.waiting_for_deal_link))
        self.dp.message.register(self.handle_watch_link, StateFilter(UserStates.waiting_for_watch_link))

    async def setup_bot_commands(self):
        """Set up the bot menu button with commands"""
        commands = [
            BotCommand(command="start", description="🚀 Subscribe to notifications"),
            BotCommand(command="deal", description="📊 Analyze event with AI"),
            BotCommand(command="watch", description="🔍 Monitor event (Polydictor)"),
            BotCommand(command="balance", description="💰 Check wallet balance"),
            BotCommand(command="mystatus", description="📋 View subscriptions"),
            BotCommand(command="watchlist", description="📋 Show your watchlist"),
            BotCommand(command="interval", description="⏱️ Set update interval"),
            BotCommand(command="alerts", description="🔔 Show price alerts"),
            BotCommand(command="alert", description="⏰ Set price alert"),
            BotCommand(command="keywords", description="🔍 Set keyword filters"),
            BotCommand(command="pause", description="⏸️ Pause notifications"),
            BotCommand(command="help", description="❓ Show help"),
        ]

        await self.bot.set_my_commands(commands)
        await self.bot.set_chat_menu_button(menu_button=MenuButtonCommands())
        logger.info("Bot menu commands set up successfully")

    async def cmd_start(self, message: Message):
        user_id = message.from_user.id
        subscribed_users.add(user_id)
        Storage.save_users(subscribed_users)

        text = (
            "🎯 <b>Welcome to Polydictions Bot</b>\n\n"
            "Track and analyze Polymarket events.\n\n"
            "<b>📊 Main Commands:</b>\n"
            "📊 /deal &lt;link&gt; - Analyze event\n"
            "🔔 /start - Subscribe to notifications\n"
            "⏸️ /pause - Pause notifications\n"
            "▶️ /resume - Resume notifications\n\n"
            "<b>🔍 Filters:</b>\n"
            "🔍 /keywords - Filter by keywords\n"
            "📂 /category - Filter by category\n"
            "📂 /categories - Show all categories\n\n"
            "<b>📋 Watchlist:</b>\n"
            "⭐ /watch &lt;slug&gt; - Add to watchlist\n"
            "📋 /watchlist - Show watchlist\n"
            "❌ /unwatch &lt;slug&gt; - Remove from watchlist\n\n"
            "<b>🔔 Price Alerts:</b>\n"
            "🔔 /alert &lt;slug&gt; &gt; &lt;%&gt; - Set alert\n"
            "📊 /alerts - Show alerts\n"
            "❌ /rmalert &lt;#&gt; - Remove alert\n\n"
            "You're now subscribed to new events! 🔔\n"
            "Use /help for more info"
        )

        await message.answer(text)
        logger.info(f"User {user_id} subscribed")

    async def cmd_deal(self, message: Message, state: FSMContext):
        text = message.text or ""
        parts = text.split(maxsplit=1)

        if len(parts) < 2:
            # No link provided - ask for it and wait
            await message.answer(
                "🔗 <b>Send me a Polymarket link</b>\n\n"
                "Example:\nhttps://polymarket.com/event/your-event-slug"
            )
            await state.set_state(UserStates.waiting_for_deal_link)
            return

        url = parts[1].strip()
        slug = PolymarketAPI.parse_polymarket_url(url)

        if not slug:
            await message.answer("❌ Invalid Polymarket URL")
            return

        processing = await message.answer("⏳ Fetching event data...")

        try:
            event_data = await PolymarketAPI.fetch_event_by_slug(slug)

            if not event_data:
                await processing.edit_text("❌ Event not found")
                return

            # Format basic event info
            basic_msg = PolymarketAPI.format_event(event_data)

            # Send basic info first
            await processing.edit_text(basic_msg)

            # Now fetch Market Context (this takes time)
            context_msg = await message.answer("🧠 Generating Market Context... (this may take 10-30 seconds)")

            # Get the market question for more specific context
            markets = event_data.get('markets', [])
            market_question = None
            if markets and len(markets) > 0:
                market_question = markets[0].get('question')

            # Fetch Market Context
            event_slug = event_data.get('slug', '')
            logger.info(f"Attempting to fetch Market Context for slug: {event_slug}")

            market_context = await PolymarketAPI.fetch_market_context(
                event_slug,
                market_question
            )

            if market_context:
                logger.info(f"Successfully fetched Market Context: {len(market_context)} chars")
                context_text = f"🧠 <b>Market Context:</b>\n\n{market_context}"

                # Check if context is too long
                if len(context_text) > 4000:
                    # Split into chunks
                    await context_msg.edit_text("🧠 <b>Market Context:</b>\n\n(Message too long, sending in parts...)")
                    chunks = [market_context[i:i+3900] for i in range(0, len(market_context), 3900)]
                    for idx, chunk in enumerate(chunks):
                        if idx == 0:
                            await context_msg.edit_text(f"🧠 <b>Market Context (Part {idx+1}):</b>\n\n{chunk}")
                        else:
                            await message.answer(f"🧠 <b>Market Context (Part {idx+1}):</b>\n\n{chunk}")
                else:
                    await context_msg.edit_text(context_text)
            else:
                logger.error(f"Market Context returned None for slug: {event_slug}")
                await context_msg.edit_text(
                    "⚠️ Market Context generation failed.\n\n"
                    "This can happen if:\n"
                    "• The event is too new\n"
                    "• The API is temporarily unavailable\n"
                    "• The event doesn't have enough data\n\n"
                    "Check bot logs for details."
                )

            logger.info(f"User {message.from_user.id} checked event: {slug}")

        except Exception as e:
            logger.error(f"Error in /deal: {e}")
            await processing.edit_text(f"❌ Error: {str(e)}")

    async def handle_deal_link(self, message: Message, state: FSMContext):
        """Handle link sent after /deal command"""
        # Clear state first
        await state.clear()

        url = message.text.strip() if message.text else ""
        slug = PolymarketAPI.parse_polymarket_url(url)

        # Also try treating input as slug directly
        if not slug:
            slug = url.replace("https://", "").replace("http://", "").strip("/")
            if "/" in slug or " " in slug or len(slug) < 3:
                slug = None

        if not slug:
            await message.answer(
                "❌ Invalid link. Please send a valid Polymarket URL.\n\n"
                "Example: https://polymarket.com/event/your-event-slug"
            )
            return

        # Process the event (same logic as cmd_deal)
        processing = await message.answer("⏳ Fetching event data...")

        try:
            event_data = await PolymarketAPI.fetch_event_by_slug(slug)

            if not event_data:
                await processing.edit_text("❌ Event not found")
                return

            basic_msg = PolymarketAPI.format_event(event_data)
            await processing.edit_text(basic_msg)

            context_msg = await message.answer("🧠 Generating Market Context... (this may take 10-30 seconds)")

            markets = event_data.get('markets', [])
            market_question = markets[0].get('question') if markets else None

            event_slug = event_data.get('slug', '')
            market_context = await PolymarketAPI.fetch_market_context(event_slug, market_question)

            if market_context:
                context_text = f"🧠 <b>Market Context:</b>\n\n{market_context}"
                if len(context_text) > 4000:
                    chunks = [market_context[i:i+3900] for i in range(0, len(market_context), 3900)]
                    for idx, chunk in enumerate(chunks):
                        if idx == 0:
                            await context_msg.edit_text(f"🧠 <b>Market Context (Part {idx+1}):</b>\n\n{chunk}")
                        else:
                            await message.answer(f"🧠 <b>Market Context (Part {idx+1}):</b>\n\n{chunk}")
                else:
                    await context_msg.edit_text(context_text)
            else:
                await context_msg.edit_text(
                    "⚠️ Market Context generation failed.\n\n"
                    "This can happen if:\n"
                    "• The event is too new\n"
                    "• The API is temporarily unavailable"
                )

            logger.info(f"User {message.from_user.id} checked event: {slug}")

        except Exception as e:
            logger.error(f"Error in handle_deal_link: {e}")
            await processing.edit_text(f"❌ Error: {str(e)}")

    async def handle_watch_link(self, message: Message, state: FSMContext):
        """Handle link sent after /watch command"""
        await state.clear()

        url = message.text.strip() if message.text else ""
        slug = PolymarketAPI.parse_polymarket_url(url)

        if not slug:
            slug = url.replace("https://", "").replace("http://", "").strip("/")
            if "/" in slug or " " in slug or len(slug) < 3:
                slug = None

        if not slug:
            await message.answer(
                "❌ Invalid link. Please send a valid Polymarket URL.\n\n"
                "Example: https://polymarket.com/event/your-event-slug"
            )
            return

        user_id = message.from_user.id

        if self.watchlist.add(user_id, slug):
            await message.answer(f"✅ Added <b>{slug}</b> to your watchlist!")
            logger.info(f"User {user_id} added {slug} to watchlist")
        else:
            await message.answer(f"ℹ️ <b>{slug}</b> is already in your watchlist.")

    async def cmd_help(self, message: Message):
        text = (
            "<b>Polydictions Bot</b>\n\n"
            "<b>📊 Main Commands:</b>\n"
            "/deal &lt;link&gt; - Analyze event with Market Context\n"
            "/start - Subscribe to notifications\n"
            "/pause - Pause notifications\n"
            "/resume - Resume notifications\n\n"
            "<b>🔍 Filters:</b>\n"
            "/keywords - Filter by keywords\n"
            "/category - Filter by category (crypto, politics, sports)\n"
            "/categories - Show all categories\n\n"
            "<b>📋 Watchlist:</b>\n"
            "/watch &lt;slug&gt; - Add to watchlist\n"
            "/watchlist - Show watchlist\n"
            "/unwatch &lt;slug&gt; - Remove from watchlist\n\n"
            "<b>🔔 Price Alerts:</b>\n"
            "/alert &lt;slug&gt; &gt; &lt;%&gt; - Set alert\n"
            "/alerts - Show alerts\n"
            "/rmalert &lt;#&gt; - Remove alert\n\n"
            "<b>Features:</b>\n"
            "• 🧠 AI-powered Market Context\n"
            "• 📈 Event statistics & odds\n"
            "• 🔔 Price alerts\n"
            "• 📋 Watchlist tracking\n"
            "• 🔍 Smart filtering"
        )

        await message.answer(text)

    async def cmd_keywords(self, message: Message):
        user_id = message.from_user.id
        text = message.text or ""
        parts = text.split(maxsplit=1)

        # Show current keywords and help
        if len(parts) < 2:
            current = user_keywords.get(user_id, [])
            if current:
                keywords_text = ", ".join(current)
                help_text = (
                    f"<b>Your current keywords:</b>\n{keywords_text}\n\n"
                    "<b>How to use:</b>\n"
                    "/keywords btc, eth, election - Set keywords\n"
                    "/keywords clear - Remove all filters\n\n"
                    "<b>Filter options:</b>\n"
                    "• Simple words: btc, eth, sports\n"
                    "• Phrases: \"united states\", \"world cup\"\n"
                    "• OR logic: keywords separated by commas\n\n"
                    "<b>Examples:</b>\n"
                    "• <code>btc, eth</code> → any event with btc OR eth\n"
                    "• <code>\"united states\", election</code> → phrase + word\n"
                    "• <code>sports, football, basketball</code> → any sports event\n\n"
                    "Only events matching your keywords will be sent!"
                )
            else:
                help_text = (
                    "<b>Keyword Filters</b>\n\n"
                    "Filter events by keywords to see only what matters!\n\n"
                    "<b>How to use:</b>\n"
                    "/keywords btc, eth, election - Set keywords\n"
                    "/keywords clear - Remove all filters\n\n"
                    "<b>Filter options:</b>\n"
                    "• Simple words: btc, eth, sports\n"
                    "• Phrases: \"united states\", \"world cup\"\n"
                    "• OR logic: keywords separated by commas\n\n"
                    "<b>Examples:</b>\n"
                    "• <code>btc, eth</code> → any event with btc OR eth\n"
                    "• <code>\"united states\", election</code> → phrase + word\n"
                    "• <code>sports, football, basketball</code> → any sports event\n\n"
                    "Currently no filters set - you'll receive all events."
                )

            await message.answer(help_text)
            return

        # Parse keywords
        keyword_input = parts[1].strip()

        # Clear keywords
        if keyword_input.lower() == "clear":
            if user_id in user_keywords:
                del user_keywords[user_id]
                Storage.save_keywords(user_keywords)
                await message.answer("✅ All keyword filters removed. You'll receive all events.")
            else:
                await message.answer("You don't have any keyword filters set.")
            return

        # Parse comma-separated keywords
        keywords = [k.strip() for k in keyword_input.split(',')]
        keywords = [k for k in keywords if k]  # Remove empty strings

        if not keywords:
            await message.answer("❌ Please provide at least one keyword.")
            return

        # Save keywords
        user_keywords[user_id] = keywords
        Storage.save_keywords(user_keywords)

        keywords_display = "\n".join([f"  • {k}" for k in keywords])
        await message.answer(
            f"✅ <b>Keywords saved!</b>\n\n"
            f"You will only receive events matching:\n{keywords_display}\n\n"
            f"Use /keywords clear to remove filters."
        )
        logger.info(f"User {user_id} set keywords: {keywords}")

    async def cmd_pause(self, message: Message):
        user_id = message.from_user.id

        if user_id in paused_users:
            await message.answer("You're already paused. Use /resume to resume notifications.")
            return

        paused_users.add(user_id)
        Storage.save_paused_users(paused_users)

        await message.answer(
            "⏸️ <b>Notifications paused</b>\n\n"
            "You won't receive any new event notifications.\n\n"
            "Use /resume when you want to resume notifications."
        )
        logger.info(f"User {user_id} paused notifications")

    async def cmd_resume(self, message: Message):
        user_id = message.from_user.id

        if user_id not in paused_users:
            await message.answer("You're not paused. Notifications are already active!")
            return

        paused_users.remove(user_id)
        Storage.save_paused_users(paused_users)

        keywords_info = ""
        if user_id in user_keywords:
            keywords_info = f"\n\n🔍 Active filters: {', '.join(user_keywords[user_id])}"

        await message.answer(
            f"▶️ <b>Notifications resumed</b>\n\n"
            f"You'll receive new event notifications again!{keywords_info}"
        )
        logger.info(f"User {user_id} resumed notifications")

    # Watchlist commands
    async def cmd_watch(self, message: Message, state: FSMContext):
        """Add event to watchlist with Grok + TwitterAPI.io monitoring"""
        user_id = message.from_user.id
        text = message.text or ""
        parts = text.split(maxsplit=1)

        if len(parts) < 2:
            # No link provided - ask for it and wait
            await message.answer(
                "🔗 <b>Send me a Polymarket link to watch</b>\n\n"
                "Example:\nhttps://polymarket.com/event/btc-price-2025\n\n"
                "🧠 <b>You'll get:</b>\n"
                "• Grok AI analysis of tweets\n"
                "• Real-time Twitter monitoring\n"
                "• Priority alerts for critical developments\n"
                "• Hourly intelligence digests"
            )
            await state.set_state(UserStates.waiting_for_watch_link)
            return

        url_or_slug = parts[1].strip()
        slug = PolymarketAPI.parse_polymarket_url(url_or_slug)
        if not slug:
            slug = url_or_slug

        # Check if already watching
        if agent_manager.is_user_subscribed(slug, user_id):
            await message.answer(
                f"ℹ️ You're already monitoring <b>{slug}</b>\n\n"
                f"Use /mystatus to see your active subscriptions"
            )
            return

        processing = await message.answer("⏳ Setting up monitoring...\n\n1️⃣ Fetching event data...")

        try:
            # Fetch event data from Polymarket
            event_data = await PolymarketAPI.fetch_event_by_slug(slug)
            
            if not event_data:
                await processing.edit_text("❌ Event not found on Polymarket")
                return

            # Get event question
            markets = event_data.get('markets', [])
            if not markets:
                await processing.edit_text("❌ Event has no markets")
                return
            
            event_question = markets[0].get('question', slug)
            
            await processing.edit_text(
                f"⏳ Setting up monitoring...\n\n"
                f"1️⃣ Event: {event_question}\n"
                f"2️⃣ Creating agent with Grok AI..."
            )

            # Create or get agent
            agent = agent_manager.agents.get(slug)
            
            if not agent:
                # Create new agent (this uses Grok + TwitterAPI.io)
                agent = await agent_manager.create_agent(
                    event_slug=slug,
                    event_question=event_question,
                    initial_subscriber=user_id
                )
                
                if not agent:
                    await processing.edit_text(
                        "❌ Failed to create monitoring agent\n\n"
                        "This could be due to:\n"
                        "• Insufficient balance (need $5 minimum)\n"
                        "• Grok API issue\n"
                        "• No relevant Twitter accounts found\n\n"
                        "Check /balance and try again"
                    )
                    return
                
                await processing.edit_text(
                    f"⏳ Setting up monitoring...\n\n"
                    f"1️⃣ Event: {event_question}\n"
                    f"2️⃣ Agent created ✅\n"
                    f"3️⃣ Starting Twitter monitoring..."
                )
                
                # Start the agent
                await agent_manager.start_agent(slug)
                
            else:
                # Add user to existing agent
                agent_manager.add_subscriber(slug, user_id)

            # Success message
            monitored_accounts = agent.ruleset.get('accounts', [])[:5]
            priority_nodes = agent.ruleset.get('priority_nodes', [])
            
            success_msg = (
                f"✅ <b>Monitoring Active!</b>\n\n"
                f"📊 <b>Event:</b> {event_question}\n"
                f"🔗 https://polymarket.com/event/{slug}\n\n"
                f"🐦 <b>Monitoring {len(monitored_accounts)} Twitter accounts:</b>\n"
            )
            
            for acc in monitored_accounts:
                success_msg += f"  • @{acc}\n"
            
            success_msg += (
                f"\n🚨 <b>Priority alerts for:</b>\n"
                f"  • {len(priority_nodes)} critical developments\n\n"
                f"💰 <b>Cost:</b>\n"
                f"  • $0.01 per Grok analysis\n"
                f"  • $2.00 per day for Twitter monitoring\n\n"
                f"📊 Check /mystatus for details\n"
                f"💵 Check /balance for your funds"
            )
            
            await processing.edit_text(success_msg)
            logger.info(f"User {user_id} started monitoring {slug} with agent")

        except Exception as e:
            logger.error(f"Error in /watch: {e}", exc_info=True)
            await processing.edit_text(
                f"❌ Error setting up monitoring: {str(e)}\n\n"
                f"Please try again or contact support"
            )

    async def cmd_unwatch(self, message: Message):
        """Remove event from watchlist and stop agent monitoring"""
        user_id = message.from_user.id
        text = message.text or ""
        parts = text.split(maxsplit=1)

        if len(parts) < 2:
            await message.answer("❌ Please provide an event slug.\n\nExample:\n/unwatch btc-price-2025")
            return

        slug = parts[1].strip()

        # Check if user is subscribed to this agent
        if not agent_manager.is_user_subscribed(slug, user_id):
            await message.answer(f"❌ You're not monitoring <b>{slug}</b>")
            return

        processing = await message.answer("⏳ Stopping monitoring...")

        try:
            # Remove user from agent
            removed = await agent_manager.remove_subscriber(slug, user_id)
            
            if removed:
                # Check if agent was stopped (no more subscribers)
                agent = agent_manager.agents.get(slug)
                
                if not agent or agent.status == "stopped":
                    await processing.edit_text(
                        f"✅ <b>Monitoring stopped for {slug}</b>\n\n"
                        f"• Agent removed from your subscriptions\n"
                        f"• Twitter monitoring stopped (no active subscribers)\n"
                        f"• All tasks cancelled\n\n"
                        f"Your balance has been preserved. Use /balance to check."
                    )
                else:
                    await processing.edit_text(
                        f"✅ <b>Removed from your watchlist: {slug}</b>\n\n"
                        f"• Agent still active for other subscribers\n"
                        f"• No further charges to your account\n\n"
                        f"Use /balance to check your funds."
                    )
                
                logger.info(f"User {user_id} unwatched {slug}")
            else:
                await processing.edit_text("❌ Failed to remove subscription")

        except Exception as e:
            logger.error(f"Error in /unwatch: {e}")
            await processing.edit_text(f"❌ Error: {str(e)}")
            logger.info(f"User {user_id} removed {slug} from watchlist")
        else:
            await message.answer("⚠️ Event not found in your watchlist.")

    async def cmd_watchlist(self, message: Message):
        """Show user's active agent subscriptions"""
        user_id = message.from_user.id
        
        # Get all agents user is subscribed to
        user_agents = []
        for event_slug, agent in agent_manager.agents.items():
            if user_id in agent.subscribers:
                user_agents.append((event_slug, agent))

        if not user_agents:
            # Check if user has old watchlist data (before agent integration)
            old_watchlist = self.watchlist.get(user_id)
            
            if old_watchlist:
                await message.answer(
                    f"📋 <b>You have {len(old_watchlist)} events in your old watchlist</b>\n\n"
                    f"⚠️ These are NOT being monitored with Grok AI + Twitter yet.\n\n"
                    f"<b>To activate full monitoring:</b>\n"
                    f"Use /watch &lt;polymarket-link&gt; for each event\n\n"
                    f"<b>Old watchlist events:</b>\n" +
                    "\n".join([f"  • {slug}" for slug in old_watchlist[:10]]) +
                    (f"\n  • ... and {len(old_watchlist) - 10} more" if len(old_watchlist) > 10 else "") +
                    f"\n\n<b>What you'll get with /watch:</b>\n"
                    f"🧠 Grok AI analysis\n"
                    f"🐦 Real-time Twitter monitoring\n"
                    f"🚨 Priority alerts\n"
                    f"📊 Hourly digests"
                )
            else:
                await message.answer(
                    "📋 <b>You're not monitoring any events</b>\n\n"
                    "Start monitoring with:\n/watch &lt;polymarket-link&gt;\n\n"
                    "You'll get:\n"
                    "🧠 Grok AI analysis\n"
                    "🐦 Real-time Twitter monitoring\n"
                    "🚨 Priority alerts\n"
                    "📊 Hourly digests"
                )
            return

        msg = ["📋 <b>Your Active Monitoring:</b>\n"]
        
        for idx, (slug, agent) in enumerate(user_agents, 1):
            status_icon = "🟢" if agent.status == "active" else "🔴"
            monitored_count = len(agent.ruleset.get('accounts', []))
            
            msg.append(
                f"{idx}. {status_icon} <b>{slug}</b>\n"
                f"   📊 {agent.event_question[:60]}...\n"
                f"   🐦 Monitoring {monitored_count} Twitter accounts\n"
                f"   🔗 https://polymarket.com/event/{slug}\n"
            )

        msg.append(f"\n<b>Total:</b> {len(user_agents)} events")
        msg.append("\nUse /unwatch &lt;slug&gt; to stop monitoring")
        msg.append("Use /mystatus for detailed stats")

        await message.answer("\n".join(msg))

    # Category filter commands
    async def cmd_category(self, message: Message):
        """Set category filters"""
        user_id = message.from_user.id
        text = message.text or ""
        parts = text.split(maxsplit=1)

        if len(parts) < 2:
            current_cats = self.categories.get_categories(user_id)
            all_cats = self.categories.get_all_categories()

            if current_cats:
                msg = f"<b>Your categories:</b> {', '.join(current_cats)}\n\n"
            else:
                msg = "<b>No category filters set</b>\n\n"

            msg += "<b>Available categories:</b>\n"
            msg += ", ".join(all_cats)
            msg += "\n\n<b>Usage:</b>\n"
            msg += "/category crypto politics\n"
            msg += "/category clear - Remove filters"

            await message.answer(msg)
            return

        categories_input = parts[1].strip()

        if categories_input.lower() == "clear":
            self.categories.clear_categories(user_id)
            await message.answer("✅ Category filters cleared. You'll receive all events.")
            logger.info(f"User {user_id} cleared category filters")
            return

        categories = [c.strip() for c in categories_input.split()]

        if self.categories.set_categories(user_id, categories):
            await message.answer(
                f"✅ <b>Category filters set!</b>\n\n"
                f"You'll only receive events in:\n{', '.join(self.categories.get_categories(user_id))}"
            )
            logger.info(f"User {user_id} set categories: {categories}")
        else:
            await message.answer(
                f"❌ Invalid categories.\n\n"
                f"Available: {', '.join(self.categories.get_all_categories())}"
            )

    async def cmd_categories(self, message: Message):
        """Show all available categories"""
        all_cats = self.categories.get_all_categories()
        msg = "<b>📂 Available Categories:</b>\n\n"
        msg += "\n".join([f"• {cat}" for cat in all_cats])
        msg += "\n\n<b>Usage:</b>\n/category crypto politics"

        await message.answer(msg)

    # Price alert commands
    async def cmd_alert(self, message: Message):
        """Set price alert"""
        user_id = message.from_user.id
        text = message.text or ""
        parts = text.split()

        if len(parts) < 4:
            await message.answer(
                "❌ Invalid format.\n\n"
                "<b>Usage:</b>\n"
                "/alert &lt;event-slug&gt; &gt; &lt;threshold&gt;\n"
                "/alert &lt;event-slug&gt; &lt; &lt;threshold&gt;\n\n"
                "<b>Examples:</b>\n"
                "/alert btc-price-2025 &gt; 70\n"
                "/alert election-winner &lt; 30"
            )
            return

        slug = parts[1]
        condition = parts[2]
        try:
            threshold = float(parts[3])
        except ValueError:
            await message.answer("❌ Threshold must be a number (0-100)")
            return

        if condition not in [">", "<"]:
            await message.answer("❌ Condition must be '>' or '<'")
            return

        if threshold < 0 or threshold > 100:
            await message.answer("❌ Threshold must be between 0 and 100")
            return

        if self.alerts.add_alert(user_id, slug, condition, threshold):
            await message.answer(
                f"✅ <b>Alert set!</b>\n\n"
                f"Event: {slug}\n"
                f"Condition: {condition} {threshold}%\n\n"
                f"You'll be notified when the price crosses this threshold."
            )
            logger.info(f"User {user_id} set alert: {slug} {condition} {threshold}%")
        else:
            await message.answer("⚠️ This alert already exists.")

    async def cmd_alerts(self, message: Message):
        """Show user's alerts"""
        user_id = message.from_user.id
        alerts = self.alerts.get_alerts(user_id)

        if not alerts:
            await message.answer(
                "🔔 <b>No alerts set</b>\n\n"
                "Set alerts with:\n/alert &lt;event-slug&gt; &gt; &lt;threshold&gt;"
            )
            return

        msg = ["🔔 <b>Your Price Alerts:</b>\n"]
        for idx, alert in enumerate(alerts):
            status = "✅ Triggered" if alert.triggered else "⏳ Active"
            msg.append(f"{idx + 1}. {alert.event_slug}")
            msg.append(f"   {alert.condition} {alert.threshold}% - {status}\n")

        msg.append(f"\n<b>Total:</b> {len(alerts)} alerts")
        msg.append("\nUse /rmalert &lt;number&gt; to remove")

        await message.answer("\n".join(msg))

    async def cmd_rmalert(self, message: Message):
        """Remove price alert"""
        user_id = message.from_user.id
        text = message.text or ""
        parts = text.split()

        if len(parts) < 2:
            await message.answer("❌ Please provide alert number.\n\nExample:\n/rmalert 1")
            return

        try:
            index = int(parts[1]) - 1
        except ValueError:
            await message.answer("❌ Invalid number")
            return

        if self.alerts.remove_alert(user_id, index):
            await message.answer("✅ Alert removed!")
            logger.info(f"User {user_id} removed alert {index}")
        else:
            await message.answer("❌ Alert not found.")

    async def cmd_interval(self, message: Message):
        """Set watchlist update interval"""
        user_id = message.from_user.id
        text = message.text or ""
        parts = text.split()

        current_interval = self.news_tracker.get_interval_minutes(user_id)

        if len(parts) < 2:
            await message.answer(
                f"⏱️ <b>Update Interval</b>\n\n"
                f"Current: <b>{current_interval} minutes</b>\n\n"
                f"<b>Usage:</b>\n"
                f"/interval &lt;minutes&gt;\n\n"
                f"<b>Examples:</b>\n"
                f"/interval 3 - every 3 minutes\n"
                f"/interval 10 - every 10 minutes\n"
                f"/interval 30 - every 30 minutes\n\n"
                f"<i>Minimum: 3 minutes</i>"
            )
            return

        try:
            minutes = int(parts[1])
        except ValueError:
            await message.answer("❌ Please provide a number of minutes.")
            return

        if self.news_tracker.set_interval(user_id, minutes):
            await message.answer(
                f"✅ <b>Interval set to {minutes} minutes!</b>\n\n"
                f"You'll receive watchlist updates every {minutes} minutes."
            )
        else:
            await message.answer(
                f"❌ Minimum interval is 3 minutes.\n\n"
                f"Example: /interval 3"
            )

    async def cmd_balance(self, message: Message):
        """Show user's wallet balance"""
        user_id = message.from_user.id
        
        # Get or create wallet
        wallet = self.payment_system.get_user_wallet(user_id)
        balance = await self.payment_system.check_user_balance(user_id)
        
        text = (
            f"💰 <b>Your Wallet</b>\n\n"
            f"<b>Address:</b>\n<code>{wallet['address']}</code>\n\n"
            f"<b>Balance:</b> {balance:.2f} USDC\n\n"
        )
        
        if balance >= 5.0:
            days_remaining = int(balance / 2.5)  # Rough estimate at $2.50/day
            text += f"<b>Estimated monitoring:</b> ~{days_remaining} days\n\n"
        else:
            text += f"⚠️ <b>Minimum balance:</b> 5 USDC required to start monitoring\n\n"
        
        text += (
            f"<b>💳 Deposit USDC:</b>\n"
            f"Send USDC (Solana) to the address above\n\n"
            f"<b>💸 Withdraw:</b>\n"
            f"/withdraw &lt;address&gt; [amount]\n\n"
            f"<b>📊 Pricing:</b>\n"
            f"• Grok analysis: $0.01 per call\n"
            f"• TwitterAPI.io: $2.00 per 24 hours\n"
            f"• Total: ~$2.50/day per event"
        )
        
        await message.answer(text)
    
    async def cmd_withdraw(self, message: Message):
        """Withdraw USDC to external wallet"""
        user_id = message.from_user.id
        text = message.text or ""
        parts = text.split()
        
        if len(parts) < 2:
            await message.answer(
                "💸 <b>Withdraw USDC</b>\n\n"
                "<b>Usage:</b>\n"
                "/withdraw &lt;solana_address&gt; [amount]\n\n"
                "<b>Examples:</b>\n"
                "• <code>/withdraw 8zHfXy...pQrS 10.5</code> - Withdraw 10.5 USDC\n"
                "• <code>/withdraw 8zHfXy...pQrS</code> - Withdraw ALL available USDC\n\n"
                "⚠️ Make sure the address is correct - transactions cannot be reversed!"
            )
            return
        
        destination = parts[1]
        amount = float(parts[2]) if len(parts) > 2 else None
        
        await message.answer("⏳ Processing withdrawal...")
        
        result = await self.payment_system.withdraw_to_external_wallet(
            user_id, destination, amount
        )
        
        if result['success']:
            response_text = (
                f"✅ <b>Withdrawal Successful!</b>\n\n"
                f"<b>Amount:</b> {result['amount']:.2f} USDC\n"
                f"<b>To:</b> <code>{destination[:20]}...</code>\n"
                f"<b>Signature:</b> <code>{result['signature'][:20]}...</code>\n\n"
                f"<b>New balance:</b> {result.get('new_balance', 0):.2f} USDC"
            )
        else:
            response_text = f"❌ <b>Withdrawal Failed</b>\n\n{result['message']}"
        
        await message.answer(response_text)
    
    async def cmd_deposit(self, message: Message):
        """Show deposit instructions"""
        user_id = message.from_user.id
        wallet = self.payment_system.get_user_wallet(user_id)
        
        text = (
            f"💳 <b>Deposit USDC</b>\n\n"
            f"<b>Your Wallet Address:</b>\n"
            f"<code>{wallet['address']}</code>\n\n"
            f"<b>How to deposit:</b>\n"
            f"1. Send USDC on Solana network to the address above\n"
            f"2. Balance updates automatically\n"
            f"3. Start with $10-20 for testing\n\n"
            f"<b>⚠️ Important:</b>\n"
            f"• Use Solana network only (NOT Ethereum!)\n"
            f"• Send USDC only (SPL token)\n"
            f"• Minimum $5 required to start monitoring\n\n"
            f"Check balance: /balance"
        )
        
        await message.answer(text)
    
    async def cmd_mystatus(self, message: Message):
        """Show user's active subscriptions and usage"""
        user_id = message.from_user.id
        balance = await self.payment_system.check_user_balance(user_id)
        
        # Get subscriptions
        user_subs = [
            (slug, data) for slug, data in self.payment_system.subscriptions.items()
            if data.get('user_id') == user_id
        ]
        
        text = f"📊 <b>My Status</b>\n\n"
        text += f"<b>💰 Balance:</b> {balance:.2f} USDC\n\n"
        
        if user_subs:
            text += f"<b>🔍 Active Monitoring:</b>\n"
            for slug, data in user_subs:
                subscribed_at = data.get('subscribed_at', 'Unknown')
                text += f"• {slug}\n  Started: {subscribed_at[:10]}\n"
            text += f"\n<b>📈 Usage:</b>\n"
            text += f"Use /usage &lt;event&gt; for detailed breakdown\n"
        else:
            text += f"<b>No active monitoring</b>\n\n"
            text += f"Start monitoring with /watch &lt;event&gt;\n"
        
        await message.answer(text)

    async def check_new_events(self):
        global seen_events
        logger.info(f"Starting event monitoring with {len(seen_events)} seen events already loaded")

        if not seen_events:
            logger.info("Seen events is empty, initializing with recent 100 events...")
            initial = await PolymarketAPI.fetch_recent_events(limit=100)
            for event in initial:
                event_id = event.get('id')
                if event_id:
                    seen_events.add(str(event_id))
            Storage.save_seen_events(seen_events)
            logger.info(f"Initialized with {len(seen_events)} events")
        else:
            logger.info(f"Using existing {len(seen_events)} seen events from storage")

        while True:
            try:
                await asyncio.sleep(CHECK_INTERVAL)

                recent = await PolymarketAPI.fetch_recent_events(limit=20)
                new_events = []
                filtered_count = 0
                filtered_high_volume = 0

                for event in recent:
                    event_id = str(event.get('id', ''))
                    if event_id:
                        if event_id not in seen_events:
                            # Check if event is actually new (created in last 48 hours)
                            created_at_str = event.get('createdAt') or event.get('startDate')
                            is_actually_new = False

                            if created_at_str:
                                try:
                                    created_at = datetime.fromisoformat(created_at_str.replace('Z', '+00:00'))
                                    now = datetime.now(created_at.tzinfo) if created_at.tzinfo else datetime.now()
                                    age_hours = (now - created_at).total_seconds() / 3600
                                    is_actually_new = age_hours < 48  # Only events created in last 48h
                                except Exception as e:
                                    logger.error(f"Error parsing date {created_at_str}: {e}")
                                    is_actually_new = False

                            volume = float(event.get('volume', 0) or 0)

                            if not is_actually_new:
                                # Old event appearing for first time - mark as seen but don't notify
                                seen_events.add(event_id)
                                filtered_high_volume += 1
                                logger.info(f"Filtered old event: ID={event_id}, Created={created_at_str}, Title={event.get('title', 'N/A')[:50]}")
                            elif volume > 50000:
                                # This is likely an old event with high volume, mark as seen but don't notify
                                seen_events.add(event_id)
                                filtered_high_volume += 1
                                logger.info(f"Filtered high-volume event: ID={event_id}, Volume=${volume:,.0f}, Title={event.get('title', 'N/A')[:50]}")
                            else:
                                # This is a genuinely new event
                                seen_events.add(event_id)
                                new_events.append(event)
                                logger.info(f"New event found: ID={event_id}, Volume=${volume:,.0f}, Title={event.get('title', 'N/A')[:50]}")
                        else:
                            filtered_count += 1

                logger.info(f"Checked {len(recent)} events: {len(new_events)} new, {filtered_count} already seen, {filtered_high_volume} filtered (high volume)")

                if new_events:
                    Storage.save_seen_events(seen_events)
                    logger.info(f"Found {len(new_events)} new events")

                    for event in new_events:
                        formatted = PolymarketAPI.format_event(event)
                        notification = f"🆕 <b>New Polymarket Event</b>\n\n{formatted}"

                        # Post to channel only (no DM to users)
                        if CHANNEL_ID:
                            try:
                                await self.bot.send_message(CHANNEL_ID, notification)
                                logger.info(f"Posted event to channel {CHANNEL_ID}: {event.get('title', 'N/A')[:50]}")

                                # Save to posted_events.json for extension sync
                                Storage.save_posted_event(event)

                                await asyncio.sleep(0.5)
                            except Exception as e:
                                logger.error(f"Failed to post to channel {CHANNEL_ID}: {e}")

            except Exception as e:
                logger.error(f"Error in monitoring: {e}")

    async def check_watchlist_news(self):
        """Monitor watchlist events for news/context updates with per-user intervals"""
        logger.info("Starting watchlist news monitoring...")

        # Track last check time per user: {user_id: timestamp}
        last_check: Dict[int, float] = {}

        # Initial delay - wait 60 seconds before first check
        logger.info("Waiting 60 seconds before first watchlist check...")
        await asyncio.sleep(60)

        while True:
            try:
                current_time = datetime.now().timestamp()

                for user_id, user_slugs in self.watchlist.user_watchlists.items():
                    if not user_slugs:
                        continue

                    # Get user's interval
                    user_interval = self.news_tracker.get_interval(user_id)

                    # Check if it's time to send update to this user
                    user_last = last_check.get(user_id, 0)
                    if current_time - user_last < user_interval:
                        continue  # Not time yet

                    # Update last check time
                    last_check[user_id] = current_time

                    logger.info(f"Checking news for user {user_id}: {len(user_slugs)} events (interval: {user_interval}s)")

                    # Collect status for all slugs
                    updates = []
                    no_updates = []

                    for slug in user_slugs:
                        try:
                            new_context = await PolymarketAPI.fetch_market_context(slug)

                            if not new_context:
                                no_updates.append(slug)
                                continue

                            update = self.news_tracker.check_for_update(slug, new_context)

                            if update:
                                updates.append((slug, new_context))
                                logger.info(f"News update detected for {slug}")
                            else:
                                no_updates.append(slug)

                            await asyncio.sleep(2)

                        except Exception as e:
                            logger.error(f"Error checking news for {slug}: {e}")
                            no_updates.append(slug)

                    # Build and send notification ONLY if there are actual updates
                    try:
                        # Only notify if there are ACTUAL updates (not status reports)
                        if updates:
                            msg_parts = []
                            interval_min = self.news_tracker.get_interval_minutes(user_id)

                            for slug, context in updates:
                                msg_parts.append(
                                    f"📰 <b>New Update: {slug}</b>\n"
                                    f"🔗 https://polymarket.com/event/{slug}\n\n"
                                    f"🧠 <b>Market Context:</b>\n{context[:800]}"
                                )
                                if len(context) > 800:
                                    msg_parts.append("...\n\n<i>Use /deal for full details</i>")

                            header = f"📋 <b>Watchlist Alert</b> ({datetime.now().strftime('%H:%M')})\n\n"
                            full_msg = header + "\n\n".join(msg_parts)

                            if len(full_msg) > 4000:
                                full_msg = full_msg[:3950] + "\n\n<i>...truncated</i>"

                            await self.bot.send_message(user_id, full_msg)
                            logger.info(f"Sent {len(updates)} watchlist updates to user {user_id}")
                            await asyncio.sleep(0.5)
                        else:
                            # No updates - just log it, don't spam the user
                            logger.debug(f"No updates for user {user_id} watchlist (checked {len(user_slugs)} events)")

                    except Exception as e:
                        logger.error(f"Failed to send updates to {user_id}: {e}")

            except Exception as e:
                logger.error(f"Error in news monitoring: {e}")

            # Check every 30 seconds for users who need updates
            await asyncio.sleep(30)

    async def start(self):
        # Set up menu commands
        await self.setup_bot_commands()

        # Start API server for Chrome extension sync
        from api_server import APIServer
        api_server = APIServer(port=8765)
        await api_server.start()

        # Event monitoring disabled - using agent system with Grok + TwitterAPI.io
        # Old simple watchlist monitoring also disabled - agents handle everything
        # asyncio.create_task(self.check_new_events())
        # asyncio.create_task(self.check_watchlist_news())

        logger.info("Bot started with API server on port 8765")
        logger.info("Agent system ready: Grok AI + TwitterAPI.io monitoring")
        await self.dp.start_polling(self.bot, allowed_updates=["message"])


async def main():
    token = None

    try:
        import sys
        sys.path.insert(0, str(Path(__file__).parent))
        from config import BOT_TOKEN
        token = BOT_TOKEN
        logger.info("Loaded token from config.py")
    except ImportError as e:
        logger.error(f"Failed to import config.py: {e}")
        token = os.getenv('BOT_TOKEN')
    except Exception as e:
        logger.error(f"Error loading config: {e}")
        token = os.getenv('BOT_TOKEN')

    if not token:
        logger.error("BOT_TOKEN not found!")
        logger.error(f".env path: {Path(__file__).parent / '.env'}")
        logger.error(f".env exists: {(Path(__file__).parent / '.env').exists()}")
        logger.error("Create .env with: BOT_TOKEN=your_token")
        logger.error("Or config.py with: BOT_TOKEN = 'your_token'")
        return

    token = token.strip()

    bot = PolydictionsBot(token)
    await bot.start()


if __name__ == '__main__':
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Bot stopped")
