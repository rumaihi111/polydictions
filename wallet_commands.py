"""
Wallet commands for Polydictor prepaid system
"""

from aiogram import types, Router
from aiogram.filters import Command
from payment_system import payment_system

wallet_router = Router()


@wallet_router.message(Command("balance"))
async def cmd_balance(message: types.Message):
    """Check user's wallet balance"""
    user_id = message.from_user.id
    
    # Get wallet info
    wallet = payment_system.get_user_wallet(user_id)
    balance = await payment_system.check_user_balance(user_id)
    
    balance_msg = f"""💰 **Your Wallet**

**Balance:** {balance} USDC
**Wallet Address:** `{wallet['address']}`

**Events you can watch:** {int(balance / payment_system.WATCH_PRICE_USDC)} ({payment_system.WATCH_PRICE_USDC} USDC each)

Use /deposit to add funds
Use /watch to monitor an event
"""
    
    await message.answer(balance_msg, parse_mode="Markdown")


@wallet_router.message(Command("deposit"))
async def cmd_deposit(message: types.Message):
    """Show deposit instructions"""
    user_id = message.from_user.id
    
    instructions = payment_system.get_deposit_instructions(user_id)
    await message.answer(instructions, parse_mode="Markdown")


@wallet_router.message(Command("wallet"))
async def cmd_wallet(message: types.Message):
    """Alias for /balance"""
    await cmd_balance(message)
