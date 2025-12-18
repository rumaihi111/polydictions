"""
Polydictor Bot Integration

Extends bot.py with new Polydictor features:
- /watch command to start monitoring an event
- Payment flow for subscriptions
- Intelligence delivery to users
"""

import logging
from typing import Optional, Dict
from aiogram import types, Router, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

from agent import agent_manager
from payment_system import payment_system
from grok_engine import grok_engine
from bot import PolymarketAPI  # Use existing Polymarket integration

logger = logging.getLogger(__name__)

# Router for Polydictor features
polydictor_router = Router()


class PolydictorStates(StatesGroup):
    """FSM states for Polydictor features"""
    waiting_for_polymarket_url = State()
    waiting_for_payment_verification = State()


@polydictor_router.message(Command("watch"))
async def cmd_watch(message: types.Message, state: FSMContext):
    """
    /watch - Start monitoring a Polymarket event
    
    New flow with prepaid wallets:
    1. User sends /watch
    2. Bot asks for Polymarket URL
    3. Bot extracts event details
    4. Grok generates monitoring rules
    5. Bot checks user's wallet balance
    6. If sufficient → Auto-deduct & activate
    7. If insufficient → Show deposit instructions
    """
    await message.answer(
        "🔍 **Start Event Monitoring**\n\n"
        "Send me a Polymarket event URL to start receiving real-time Twitter intelligence.\n\n"
        "Example:\n"
        "`https://polymarket.com/event/presidential-election-winner-2024`\n\n"
        f"💰 Cost: {payment_system.WATCH_PRICE_USDC} USDC (auto-deducted from your wallet)\n\n"
        "Or send /cancel to abort.",
        parse_mode="Markdown"
    )
    await state.set_state(PolydictorStates.waiting_for_polymarket_url)


@polydictor_router.message(PolydictorStates.waiting_for_polymarket_url)
async def process_polymarket_url(message: types.Message, state: FSMContext):
    """Process Polymarket URL and create agent"""
    url = message.text.strip()
    
    # Extract event slug from URL using existing PolymarketAPI
    event_slug = PolymarketAPI.parse_polymarket_url(url)
    if not event_slug:
        # Might already be just a slug
        if '/' not in url and url.replace('-', '').isalnum():
            event_slug = url
        else:
            await message.answer(
                "❌ Invalid Polymarket URL. Please send a valid event URL.\n\n"
                "Example: https://polymarket.com/event/your-event-slug"
            )
            return
    
    # Show processing message
    processing_msg = await message.answer("🔄 Setting up intelligence monitoring...")
    
    # Fetch event details from Polymarket API using existing method
    event_data = await PolymarketAPI.fetch_event_by_slug(event_slug)
    if not event_data:
        await processing_msg.edit_text(
            "❌ Could not fetch event details. Please check the URL and try again."
        )
        await state.clear()
        return
    
    event_question = event_data.get('title', 'Unknown Event')
    event_description = event_data.get('description', '')
    category = event_data.get('category', 'Other')
    
    # Check if agent already exists
    existing_agent = agent_manager.agents.get(event_slug)
    if existing_agent:
        # User wants to subscribe to existing agent
        if message.from_user.id in existing_agent.subscribers:
            await processing_msg.edit_text(
                f"✅ You're already subscribed to:\n\n**{event_question}**"
            )
            await state.clear()
            return
        else:
            # Add as subscriber with payment
            payment_request = payment_system.generate_payment_request(
                user_id=message.from_user.id,
                event_slug=event_slug,
                event_question=event_question
            )
            
            await show_payment_instructions(message, processing_msg, payment_request, state)
            return
    
    # Create new agent
    await processing_msg.edit_text(
        "🧠 Asking Grok to analyze event and generate monitoring strategy...\n\n"
        f"**Event:** {event_question}\n"
        f"**Category:** {category}"
    )
    
    agent = await agent_manager.create_agent(
        event_slug=event_slug,
        event_question=event_question,
        event_description=event_description,
        category=category,
        initial_subscriber=message.from_user.id
    )
    
    if not agent:
        await processing_msg.edit_text(
            "❌ Failed to create monitoring agent. Please try again later."
        )
        await state.clear()
        return
    
    # Show agent details
    ruleset = agent.ruleset
    
    setup_message = f"""✅ **Intelligence Agent Created**

📊 **Event:** {event_question}

🎯 **Monitoring Strategy:**
• **Twitter Accounts:** {len(ruleset.get('accounts', []))} verified accounts
• **Keywords:** {len(ruleset.get('keywords', []))} tracked terms
• **Relevance Threshold:** {ruleset.get('filters', {}).get('relevance_threshold', 0.7)*100:.0f}%

**What you'll receive:**
• Real-time high-priority intelligence (immediate)
• Hourly synthesized digests
• Sentiment analysis & market insights
• Credibility-scored information

**Top Monitored Accounts:**
{format_accounts(ruleset.get('accounts', [])[:5])}

**Key Terms:**
{', '.join(ruleset.get('keywords', [])[:10])}
"""
    
    await processing_msg.edit_text(setup_message, parse_mode="Markdown")
    
    # Check user balance and auto-charge
    charge_result = await payment_system.charge_user_for_watch(
        user_id=message.from_user.id,
        event_slug=event_slug,
        event_question=event_question
    )
    
    if not charge_result['success']:
        # Insufficient balance
        shortfall = charge_result.get('shortfall', 0)
        balance = charge_result.get('balance', 0)
        
        await message.answer(
            f"❌ **Insufficient Balance**\n\n"
            f"Your balance: {balance} USDC\n"
            f"Required: {payment_system.WATCH_PRICE_USDC} USDC\n"
            f"Need: {shortfall} USDC more\n\n"
            f"Use /deposit to add funds to your wallet.",
            parse_mode="Markdown"
        )
        await state.clear()
        return
    
    # Payment successful - activate agent
    agent_manager.add_subscriber(event_slug, message.from_user.id)
    await agent_manager.start_agent(event_slug)
    
    await message.answer(
        f"✅ **Agent Activated!**\n\n"
        f"💰 Charged: {charge_result['charged']} USDC\n"
        f"💵 New Balance: {charge_result['balance_after']} USDC\n\n"
        f"📡 Now monitoring: **{event_question}**\n\n"
        f"You'll receive:\n"
        f"• 🔴 High-priority intelligence (immediate)\n"
        f"• 📊 Hourly digest reports\n"
        f"• 🧠 Grok-powered analysis\n\n"
        f"The agent is learning and will refine its monitoring every 6 hours.\n\n"
        f"Use /mystatus to see your active subscriptions.\n"
        f"Use /balance to check your wallet.",
        parse_mode="Markdown"
    )
    
    await state.clear()


async def show_payment_instructions(
    message: types.Message,
    edit_msg: Optional[types.Message],
    payment_request: Dict,
    state: FSMContext
):
    """Show payment instructions to user"""
    instructions = payment_system.get_payment_instructions()
    
    payment_msg = f"""{instructions}

**Your Payment ID:** `{payment_request['payment_id']}`

After payment, send:
`/verify <your_transaction_hash>`

Or for testing/demo:
`/verify demo` (skips payment)
"""
    
    if edit_msg:
        await message.answer(payment_msg, parse_mode="Markdown")
    else:
        await message.answer(payment_msg, parse_mode="Markdown")
    
    # Store payment info in state
    await state.update_data(
        payment_id=payment_request['payment_id'],
        event_slug=payment_request['event_slug']
    )
    await state.set_state(PolydictorStates.waiting_for_payment_verification)


@polydictor_router.message(Command("mystatus"))
async def cmd_my_status(message: types.Message):
    """Show user's active subscriptions"""
    subscriptions = payment_system.get_user_subscriptions(message.from_user.id)
    
    if not subscriptions:
        await message.answer(
            "You have no active subscriptions.\n\n"
            "Use /watch to start monitoring an event."
        )
        return
    
    active_subs = [s for s in subscriptions if s.get('status') in ['verified', 'completed']]
    
    if not active_subs:
        await message.answer(
            "You have no active subscriptions.\n\n"
            "Use /watch to start monitoring an event."
        )
        return
    
    status_msg = "📊 **Your Active Intelligence Feeds**\n\n"
    
    for sub in active_subs:
        event_slug = sub.get('event_slug')
        agent = agent_manager.agents.get(event_slug)
        
        if agent:
            metrics = agent_manager.performance_metrics.get(event_slug, {})
            
            status_msg += f"**{sub['event_question']}**\n"
            status_msg += f"• Status: {agent.status.title()}\n"
            status_msg += f"• Intelligence: {metrics.get('relevant_tweets', 0)} signals\n"
            status_msg += f"• High Priority: {metrics.get('high_priority_tweets', 0)}\n"
            status_msg += f"• Avg Relevance: {metrics.get('avg_relevance_score', 0)*100:.1f}%\n"
            status_msg += f"• Started: {sub.get('verified_at', 'N/A')[:10]}\n"
            status_msg += "\n"
    
    status_msg += "Use /unwatch <event_slug> to cancel a subscription."
    
    await message.answer(status_msg, parse_mode="Markdown")


@polydictor_router.message(Command("unwatch"))
async def cmd_unwatch(message: types.Message):
    """Cancel subscription to an event"""
    parts = message.text.split(maxsplit=1)
    
    if len(parts) < 2:
        await message.answer(
            "Usage: `/unwatch <event_slug>`\n\n"
            "Use /mystatus to see your subscriptions.",
            parse_mode="Markdown"
        )
        return
    
    event_slug = parts[1].strip()
    
    # Remove subscriber
    removed = agent_manager.remove_subscriber(event_slug, message.from_user.id)
    
    if removed:
        payment_system.cancel_subscription(message.from_user.id, event_slug)
        await message.answer(
            f"✅ Unsubscribed from event: {event_slug}\n\n"
            "You will no longer receive intelligence for this event."
        )
    else:
        await message.answer(
            "❌ Subscription not found. Use /mystatus to see active subscriptions."
        )


@polydictor_router.message(Command("balance"))
async def cmd_balance(message: types.Message):
    """Check user's wallet balance"""
    user_id = message.from_user.id
    
    # Get wallet info
    wallet = payment_system.get_user_wallet(user_id)
    balance = await payment_system.check_user_balance(user_id)
    
    # Get price from module variable
    from payment_system import WATCH_PRICE_USDC
    
    balance_msg = f"""💰 **Your Wallet**

**Balance:** {balance} USDC
**Wallet Address:** `{wallet['address']}`

**Events you can watch:** {int(balance / WATCH_PRICE_USDC)} ({WATCH_PRICE_USDC} USDC each)

Use /deposit to add funds
Use /watch to monitor an event
"""
    
    await message.answer(balance_msg, parse_mode="Markdown")


@polydictor_router.message(Command("deposit"))
async def cmd_deposit(message: types.Message):
    """Show deposit instructions"""
    user_id = message.from_user.id
    
    instructions = payment_system.get_deposit_instructions(user_id)
    await message.answer(instructions, parse_mode="Markdown")


@polydictor_router.message(Command("wallet"))
async def cmd_wallet(message: types.Message):
    """Alias for /balance"""
    await cmd_balance(message)


# Helper functions

def format_accounts(accounts: list) -> str:
    """Format list of Twitter accounts for display"""
    if not accounts:
        return "None"
    return "\n".join([f"  • {acc}" for acc in accounts])


async def deliver_intelligence_to_user(user_id: int, intelligence: Dict, bot):
    """
    Deliver intelligence to a specific user.
    Called by agent when high-priority intelligence is detected.
    """
    priority = intelligence.get('priority', 'low')
    event_slug = intelligence.get('event_slug')
    
    agent = agent_manager.agents.get(event_slug)
    if not agent:
        return
    
    # Format message based on priority
    if priority == 'high':
        icon = "🔴"
    elif priority == 'medium':
        icon = "🟡"
    else:
        icon = "⚪"
    
    message = f"""{icon} **Intelligence Alert**

**Event:** {agent.event_question}

**From:** @{intelligence['author']} {'✅' if intelligence.get('author_verified') else ''}
**Sentiment:** {intelligence['sentiment'].title()}
**Credibility:** {intelligence.get('credibility_score', 0)*100:.0f}%

**Analysis:**
{intelligence['insights']}

**Tweet:**
_{intelligence['text'][:500]}_

**Priority:** {priority.upper()}
**Relevance:** {intelligence.get('relevance_score', 0)*100:.0f}%
"""
    
    try:
        await bot.send_message(user_id, message, parse_mode="Markdown")
        
        # Track engagement
        metrics = agent_manager.performance_metrics.get(event_slug, {})
        metrics.setdefault('user_engagement', {})['delivered'] = \
            metrics.get('user_engagement', {}).get('delivered', 0) + 1
        
    except Exception as e:
        logger.error(f"Failed to deliver intelligence to user {user_id}: {e}")


async def deliver_digest_to_subscribers(event_slug: str, digest: str, bot):
    """
    Deliver hourly digest to all subscribers.
    Called by agent after digest synthesis.
    """
    agent = agent_manager.agents.get(event_slug)
    if not agent:
        return
    
    digest_message = f"""📊 **Hourly Intelligence Digest**

**Event:** {agent.event_question}

{digest}

---
_Next digest in 1 hour_
"""
    
    for user_id in agent.subscribers:
        try:
            await bot.send_message(user_id, digest_message, parse_mode="Markdown")
        except Exception as e:
            logger.error(f"Failed to deliver digest to user {user_id}: {e}")
