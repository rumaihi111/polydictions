"""
Payment System - Per-User Solana Wallet

Handles:
- Auto-generates Solana wallet for each user
- Users deposit USDC into their wallet
- System auto-withdraws funds when they use /watch
- Prepaid account model
"""

import os
import json
import logging
from typing import Dict, Optional, List
from datetime import datetime, timedelta
from pathlib import Path
from cryptography.fernet import Fernet
import base58

logger = logging.getLogger(__name__)

SUBSCRIPTIONS_FILE = "subscriptions.json"
USER_WALLETS_FILE = "user_wallets.json"
USER_BALANCES_FILE = "user_balances.json"

# Configuration (should be in .env)
MIN_BALANCE_USDC = float(os.getenv("MIN_BALANCE_USDC", "5.0"))  # Minimum balance to start monitoring
PLATFORM_WALLET_ADDRESS = os.getenv("PLATFORM_WALLET_ADDRESS", "")  # Platform's main wallet
SOLANA_RPC_URL = os.getenv("SOLANA_RPC_URL", "https://api.mainnet-beta.solana.com")
USDC_MINT_ADDRESS = "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v"  # USDC on Solana
WALLET_MASTER_KEY = os.getenv("WALLET_MASTER_KEY", "")  # Master encryption key


class PaymentSystem:
    """
    Per-User Wallet System
    
    Each Telegram user gets their own Solana wallet:
    1. User gets /start -> System generates wallet for them
    2. User deposits USDC to their wallet address
    3. User uses /watch -> System checks balance & auto-withdraws to platform wallet
    4. User can check balance anytime with /balance
    
    Advantages:
    - No manual payment verification needed
    - Users control their funds until they spend
    - Can top up balance for multiple watches
    - Transparent pricing
    """
    
    def __init__(self):
        self.subscriptions: Dict[str, Dict] = {}  # event_slug -> subscription data
        self.user_wallets: Dict[int, Dict] = {}  # user_id -> {address, private_key_encrypted}
        self.user_balances: Dict[int, float] = {}  # user_id -> USDC balance (cached)
        
        # Initialize encryption cipher
        if WALLET_MASTER_KEY:
            try:
                self.cipher = Fernet(WALLET_MASTER_KEY.encode())
                logger.info("✓ Wallet encryption enabled")
            except Exception as e:
                logger.error(f"Failed to initialize encryption: {e}")
                self.cipher = None
        else:
            logger.warning("⚠️  WALLET_MASTER_KEY not set - wallets will not be encrypted!")
            self.cipher = None
        
        self.load_subscriptions()
        self.load_user_wallets()
        self.load_user_balances()
    
    def load_subscriptions(self):
        """Load subscription data"""
        if Path(SUBSCRIPTIONS_FILE).exists():
            try:
                with open(SUBSCRIPTIONS_FILE, 'r') as f:
                    self.subscriptions = json.load(f)
                logger.info(f"Loaded {len(self.subscriptions)} subscriptions")
            except Exception as e:
                logger.error(f"Error loading subscriptions: {e}")
    
    def save_subscriptions(self):
        """Save subscription data"""
        try:
            with open(SUBSCRIPTIONS_FILE, 'w') as f:
                json.dump(self.subscriptions, f, indent=2)
        except Exception as e:
            logger.error(f"Error saving subscriptions: {e}")
    
    def load_user_wallets(self):
        """Load user wallets"""
        if Path(USER_WALLETS_FILE).exists():
            try:
                with open(USER_WALLETS_FILE, 'r') as f:
                    data = json.load(f)
                    self.user_wallets = {int(k): v for k, v in data.items()}
                logger.info(f"Loaded {len(self.user_wallets)} user wallets")
            except Exception as e:
                logger.error(f"Error loading user wallets: {e}")
    
    def save_user_wallets(self):
        """Save user wallets"""
        try:
            with open(USER_WALLETS_FILE, 'w') as f:
                json.dump(self.user_wallets, f, indent=2)
        except Exception as e:
            logger.error(f"Error saving user wallets: {e}")
    
    def load_user_balances(self):
        """Load cached user balances"""
        if Path(USER_BALANCES_FILE).exists():
            try:
                with open(USER_BALANCES_FILE, 'r') as f:
                    data = json.load(f)
                    self.user_balances = {int(k): float(v) for k, v in data.items()}
            except Exception as e:
                logger.error(f"Error loading user balances: {e}")
    
    def save_user_balances(self):
        """Save user balances"""
        try:
            with open(USER_BALANCES_FILE, 'w') as f:
                json.dump(self.user_balances, f, indent=2)
        except Exception as e:
            logger.error(f"Error saving user balances: {e}")
    
    def create_user_wallet(self, user_id: int) -> Dict:
        """
        Generate a new Solana wallet for a user.
        
        Returns:
        {
            "address": "base58_public_key",
            "created_at": "ISO timestamp"
        }
        """
        # Check if user already has a wallet
        if user_id in self.user_wallets:
            return self.user_wallets[user_id]
        
        try:
            from solders.keypair import Keypair
            
            keypair = Keypair()
            public_key = str(keypair.pubkey())
            private_key_bytes = bytes(keypair)
            
            # Encrypt private key with master key
            if self.cipher:
                encrypted_private_key = self.cipher.encrypt(private_key_bytes).decode('utf-8')
                logger.info(f"✓ Private key encrypted for user {user_id}")
            else:
                # Fallback: base58 encoding (not secure!)
                encrypted_private_key = base58.b58encode(private_key_bytes).decode('utf-8')
                logger.warning(f"⚠️  Private key NOT encrypted for user {user_id}")
            
            wallet_data = {
                "address": public_key,
                "private_key_encrypted": encrypted_private_key,
                "created_at": datetime.utcnow().isoformat(),
                "balance": 0.0,
                "encrypted": bool(self.cipher)  # Track if this key is encrypted
            }
            
            self.user_wallets[user_id] = wallet_data
            self.user_balances[user_id] = 0.0
            
            self.save_user_wallets()
            self.save_user_balances()
            
            logger.info(f"✓ Created wallet for user {user_id}: {public_key}")
            return wallet_data
            
        except ImportError:
            logger.error("solders library not installed")
            # Demo fallback
            wallet_data = {
                "address": f"DEMO_WALLET_{user_id}",
                "created_at": datetime.utcnow().isoformat(),
                "balance": 100.0  # Demo balance
            }
            self.user_wallets[user_id] = wallet_data
            self.user_balances[user_id] = 100.0
            self.save_user_wallets()
            self.save_user_balances()
            return wallet_data
    
    def get_user_wallet(self, user_id: int) -> Dict:
        """Get user's wallet or create if doesn't exist"""
        if user_id not in self.user_wallets:
            return self.create_user_wallet(user_id)
        return self.user_wallets[user_id]
    
    def _decrypt_private_key(self, user_id: int) -> Optional[bytes]:
        """
        Decrypt user's private key for transaction signing.
        
        ⚠️ SECURITY CRITICAL: Only call when actually signing a transaction!
        """
        wallet = self.get_user_wallet(user_id)
        if not wallet:
            logger.error(f"No wallet found for user {user_id}")
            return None
        
        encrypted_key_str = wallet.get("private_key_encrypted", "")
        is_encrypted = wallet.get("encrypted", False)
        
        try:
            if is_encrypted and self.cipher:
                # Decrypt with master key
                decrypted_bytes = self.cipher.decrypt(encrypted_key_str.encode())
                logger.debug(f"Decrypted private key for user {user_id}")
                return decrypted_bytes
            else:
                # Fallback: base58 decode (old unencrypted wallets)
                decrypted_bytes = base58.b58decode(encrypted_key_str)
                logger.warning(f"Used unencrypted key for user {user_id}")
                return decrypted_bytes
        except Exception as e:
            logger.error(f"Failed to decrypt private key for user {user_id}: {e}")
            return None
    
    async def check_user_balance(self, user_id: int) -> float:
        """Check user's USDC balance (cached for now, on-chain in production)"""
        wallet = self.get_user_wallet(user_id)
        balance = self.user_balances.get(user_id, 0.0)
        logger.info(f"User {user_id} balance: {balance} USDC")
        return balance
    
    async def transfer_usdc_to_platform(self, user_id: int, amount: float) -> Dict:
        """
        Transfer USDC from user's wallet to platform wallet.
        Called when user uses /watch to actually send payment.
        """
        if not PLATFORM_WALLET_ADDRESS:
            logger.error("PLATFORM_WALLET_ADDRESS not configured!")
            return {"success": False, "message": "Platform wallet not configured", "signature": None}
        
        wallet = self.get_user_wallet(user_id)
        if not wallet:
            return {"success": False, "message": "User wallet not found", "signature": None}
        
        # Demo wallet - just simulate
        if wallet["address"].startswith("DEMO_"):
            logger.info(f"DEMO: Would transfer {amount} USDC from user {user_id} to platform")
            return {
                "success": True,
                "message": f"DEMO transfer of {amount} USDC",
                "signature": f"demo_tx_{int(datetime.utcnow().timestamp())}"
            }
        
        try:
            from solana.rpc.async_api import AsyncClient
            from solana.transaction import Transaction
            from spl.token.instructions import transfer_checked, TransferCheckedParams
            from spl.token.async_client import AsyncToken
            from solders.keypair import Keypair
            from solders.pubkey import Pubkey
            from solders.system_program import ID as SYS_PROGRAM_ID
            
            # Decrypt user's private key
            private_key_bytes = self._decrypt_private_key(user_id)
            if not private_key_bytes:
                return {"success": False, "message": "Failed to decrypt wallet key", "signature": None}
            
            user_keypair = Keypair.from_bytes(private_key_bytes)
            
            # Connect to Solana
            async with AsyncClient(SOLANA_RPC_URL) as client:
                # Get user's USDC token account
                from spl.token.constants import TOKEN_PROGRAM_ID
                usdc_mint = Pubkey.from_string(USDC_MINT_ADDRESS)
                platform_pubkey = Pubkey.from_string(PLATFORM_WALLET_ADDRESS)
                
                # Get associated token accounts
                from spl.token._layouts import ACCOUNT_LAYOUT
                user_token_accounts = await client.get_token_accounts_by_owner(
                    user_keypair.pubkey(),
                    {"mint": usdc_mint}
                )
                
                if not user_token_accounts.value:
                    return {"success": False, "message": "No USDC token account found", "signature": None}
                
                user_token_account = Pubkey.from_string(str(user_token_accounts.value[0].pubkey))
                
                # Get platform's token account
                platform_token_accounts = await client.get_token_accounts_by_owner(
                    platform_pubkey,
                    {"mint": usdc_mint}
                )
                
                if not platform_token_accounts.value:
                    return {"success": False, "message": "Platform USDC account not found", "signature": None}
                
                platform_token_account = Pubkey.from_string(str(platform_token_accounts.value[0].pubkey))
                
                # Create transfer instruction (USDC has 6 decimals)
                amount_lamports = int(amount * 1_000_000)
                
                transfer_ix = transfer_checked(
                    TransferCheckedParams(
                        program_id=TOKEN_PROGRAM_ID,
                        source=user_token_account,
                        mint=usdc_mint,
                        dest=platform_token_account,
                        owner=user_keypair.pubkey(),
                        amount=amount_lamports,
                        decimals=6
                    )
                )
                
                # Create and send transaction
                recent_blockhash = await client.get_latest_blockhash()
                txn = Transaction(recent_blockhash=recent_blockhash.value.blockhash)
                txn.add(transfer_ix)
                
                result = await client.send_transaction(txn, user_keypair)
                signature = str(result.value)
                
                logger.info(f"✓ Transferred {amount} USDC from user {user_id} to platform")
                logger.info(f"  Signature: {signature}")
                
                return {
                    "success": True,
                    "message": f"Transferred {amount} USDC",
                    "signature": signature
                }
                
        except ImportError as e:
            logger.warning(f"Solana libraries not installed: {e}")
            logger.info(f"DEMO: Would transfer {amount} USDC to {PLATFORM_WALLET_ADDRESS}")
            return {
                "success": True,
                "message": f"DEMO transfer (libs not installed)",
                "signature": f"demo_noimport_{int(datetime.utcnow().timestamp())}"
            }
        except Exception as e:
            logger.error(f"Transfer failed: {e}")
            return {"success": False, "message": str(e), "signature": None}
    
    async def charge_user_for_watch(
        self,
        user_id: int,
        event_slug: str,
        event_question: str
    ) -> Dict:
        """
        Check if user has minimum balance for pay-as-you-go monitoring.
        
        NEW MODEL (Pay-As-You-Go):
        - No upfront charge
        - Just verify minimum balance (~$5 for 2 days)
        - Actual charges: $0.01 per Grok call + $2/day for TwitterAPI.io
        - Charged automatically via usage_billing system
        """
        MIN_BALANCE = 5.0  # Minimum $5 to start (covers ~2 days)
        
        balance = await self.check_user_balance(user_id)
        
        if balance < MIN_BALANCE:
            return {
                "success": False,
                "message": f"Insufficient balance for pay-as-you-go monitoring",
                "balance": balance,
                "required": MIN_BALANCE,
                "shortfall": MIN_BALANCE - balance
            }
        
        # Record subscription (NO upfront charge, just tracking)
        self.subscriptions[event_slug] = {
            "user_id": user_id,
            "event_question": event_question,
            "subscribed_at": datetime.utcnow().isoformat(),
            "billing_model": "pay_as_you_go",
            "grok_cost_per_call": 0.01,
            "twitter_api_daily_fee": 2.0
        }
        
        self.save_subscriptions()
        
        return {
            "success": True,
            "message": f"Pay-as-you-go monitoring activated",
            "balance": balance,
            "estimated_days": int(balance / 2.5)  # Rough estimate at $2.50/day
        }
    
    async def withdraw_to_external_wallet(
        self,
        user_id: int,
        destination_address: str,
        amount: Optional[float] = None  # None = withdraw all
    ) -> Dict:
        """
        Allow users to withdraw their USDC to an external wallet.
        
        This gives users control - they can withdraw anytime.
        
        Args:
            user_id: User's Telegram ID
            destination_address: Solana address to send USDC to
            amount: Amount to withdraw (None = all available balance)
        
        Returns:
            {success: bool, message: str, signature: str, amount: float}
        """
        wallet = self.get_user_wallet(user_id)
        if not wallet:
            return {"success": False, "message": "No wallet found", "signature": None}
        
        # Check balance
        balance = await self.check_user_balance(user_id)
        
        if balance <= 0:
            return {"success": False, "message": "No funds to withdraw", "signature": None}
        
        # Determine withdrawal amount
        withdraw_amount = amount if amount is not None else balance
        
        if withdraw_amount > balance:
            return {
                "success": False,
                "message": f"Insufficient balance. You have {balance} USDC",
                "signature": None
            }
        
        if withdraw_amount <= 0:
            return {"success": False, "message": "Invalid withdrawal amount", "signature": None}
        
        # Demo wallet - just simulate
        if wallet["address"].startswith("DEMO_"):
            logger.info(f"DEMO: Would withdraw {withdraw_amount} USDC to {destination_address}")
            self.user_balances[user_id] = balance - withdraw_amount
            self.save_user_balances()
            return {
                "success": True,
                "message": f"DEMO withdrawal of {withdraw_amount} USDC",
                "signature": f"demo_withdrawal_{int(datetime.utcnow().timestamp())}",
                "amount": withdraw_amount
            }
        
        try:
            from solana.rpc.async_api import AsyncClient
            from spl.token.instructions import transfer_checked, TransferCheckedParams
            from spl.token.constants import TOKEN_PROGRAM_ID
            from solders.keypair import Keypair
            from solders.pubkey import Pubkey
            
            # Decrypt private key
            private_key_bytes = self._decrypt_private_key(user_id)
            if not private_key_bytes:
                return {"success": False, "message": "Failed to decrypt wallet", "signature": None}
            
            user_keypair = Keypair.from_bytes(private_key_bytes)
            destination_pubkey = Pubkey.from_string(destination_address)
            usdc_mint = Pubkey.from_string(USDC_MINT_ADDRESS)
            
            async with AsyncClient(SOLANA_RPC_URL) as client:
                # Get user's USDC token account
                user_token_accounts = await client.get_token_accounts_by_owner(
                    user_keypair.pubkey(),
                    {"mint": usdc_mint}
                )
                
                if not user_token_accounts.value:
                    return {"success": False, "message": "No USDC account found", "signature": None}
                
                user_token_account = Pubkey.from_string(str(user_token_accounts.value[0].pubkey))
                
                # Get destination's USDC token account
                dest_token_accounts = await client.get_token_accounts_by_owner(
                    destination_pubkey,
                    {"mint": usdc_mint}
                )
                
                if not dest_token_accounts.value:
                    return {
                        "success": False,
                        "message": "Destination has no USDC account. They need to create one first.",
                        "signature": None
                    }
                
                dest_token_account = Pubkey.from_string(str(dest_token_accounts.value[0].pubkey))
                
                # Create transfer (USDC = 6 decimals)
                amount_lamports = int(withdraw_amount * 1_000_000)
                
                transfer_ix = transfer_checked(
                    TransferCheckedParams(
                        program_id=TOKEN_PROGRAM_ID,
                        source=user_token_account,
                        mint=usdc_mint,
                        dest=dest_token_account,
                        owner=user_keypair.pubkey(),
                        amount=amount_lamports,
                        decimals=6
                    )
                )
                
                # Send transaction
                from solana.transaction import Transaction
                tx = Transaction().add(transfer_ix)
                response = await client.send_transaction(tx, user_keypair)
                
                signature = str(response.value)
                
                # Update balance
                self.user_balances[user_id] = balance - withdraw_amount
                self.save_user_balances()
                
                logger.info(f"✓ User {user_id} withdrew {withdraw_amount} USDC to {destination_address}")
                
                return {
                    "success": True,
                    "message": f"Withdrew {withdraw_amount} USDC",
                    "signature": signature,
                    "amount": withdraw_amount,
                    "new_balance": balance - withdraw_amount
                }
                
        except Exception as e:
            logger.error(f"Withdrawal failed for user {user_id}: {e}")
            return {"success": False, "message": str(e), "signature": None}
        
        # Record subscription with transaction signature
        subscription_key = f"{user_id}_{event_slug}"
        self.subscriptions[subscription_key] = {
            "user_id": user_id,
            "event_slug": event_slug,
            "event_question": event_question,
            "charged": WATCH_PRICE_USDC,
            "charged_at": datetime.utcnow().isoformat(),
            "status": "active",
            "transaction_signature": transfer_result["signature"]
        }
        self.save_subscriptions()
        
        logger.info(f"✓ Charged user {user_id} {WATCH_PRICE_USDC} USDC for {event_slug}")
        logger.info(f"  TX: {transfer_result['signature']}")
        
        return {
            "success": True,
            "message": f"Charged {WATCH_PRICE_USDC} USDC",
            "balance_before": balance,
            "balance_after": new_balance,
            "charged": WATCH_PRICE_USDC,
            "transaction_signature": transfer_result["signature"]
        }
    
    def generate_payment_request(
        self,
        user_id: int,
        event_slug: str,
        event_question: str
    ) -> Dict:
        """
        Generate payment request for a user to subscribe to an event.
        
        Returns:
        {
            "payment_address": "0x...",
            "amount": 10.0,
            "currency": "USDC",
            "network": "Polygon",
            "payment_id": "unique_payment_id",
            "expires_at": "ISO timestamp"
        }
        """
        # For MVP: Use single payment wallet
        # For production: Generate unique address per payment
        
        payment_id = f"{user_id}_{event_slug}_{int(datetime.utcnow().timestamp())}"
        
        payment_request = {
            "payment_id": payment_id,
            "payment_address": PAYMENT_WALLET_ADDRESS,
            "amount": SUBSCRIPTION_PRICE_USDC,
            "currency": "USDC",
            "network": "Solana",
            "event_slug": event_slug,
            "event_question": event_question,
            "user_id": user_id,
            "created_at": datetime.utcnow().isoformat(),
            "expires_at": (datetime.utcnow() + timedelta(hours=24)).isoformat(),
            "status": "pending"
        }
        
        # Store pending payment
        subscription_key = f"{user_id}_{event_slug}"
        self.subscriptions[subscription_key] = payment_request
        self.save_subscriptions()
        
        logger.info(f"Generated payment request for user {user_id}, event {event_slug}")
        return payment_request
    
    async def verify_payment(
        self,
        payment_id: str,
        transaction_hash: Optional[str] = None
    ) -> bool:
        """
        Verify that USDC payment was received.
        
        MVP: Manual verification - admin marks as paid
        Production: Check blockchain for transaction
        
        Args:
            payment_id: Unique payment identifier
            transaction_hash: Optional blockchain transaction hash
            
        Returns:
            True if payment verified
        """
        # Find subscription with this payment_id
        subscription = None
        subscription_key = None
        
        for key, sub in self.subscriptions.items():
            if sub.get('payment_id') == payment_id:
                subscription = sub
                subscription_key = key
                break
        
        if not subscription:
            logger.error(f"Payment {payment_id} not found")
            return False
        
        # MVP: Manual verification
        # In production, this would check blockchain:
        # 1. Verify transaction exists
        # 2. Check it's to correct address
        # 3. Verify amount is correct
        # 4. Confirm it's USDC token transfer
        
        if transaction_hash:
            # Store transaction hash
            subscription['transaction_hash'] = transaction_hash
        
        # Mark as verified
        subscription['status'] = 'verified'
        subscription['verified_at'] = datetime.utcnow().isoformat()
        
        self.save_subscriptions()
        
        logger.info(f"✓ Payment verified: {payment_id}")
        return True
    
    def mark_payment_completed(self, user_id: int, event_slug: str) -> bool:
        """
        Mark payment as completed (called after agent starts).
        
        This is used for manual/admin verification.
        """
        subscription_key = f"{user_id}_{event_slug}"
        
        if subscription_key in self.subscriptions:
            self.subscriptions[subscription_key]['status'] = 'completed'
            self.save_subscriptions()
            return True
        
        return False
    
    def is_subscription_active(self, user_id: int, event_slug: str) -> bool:
        """Check if user has active subscription for event"""
        subscription_key = f"{user_id}_{event_slug}"
        
        if subscription_key not in self.subscriptions:
            return False
        
        sub = self.subscriptions[subscription_key]
        return sub.get('status') in ['verified', 'completed']
    
    def get_user_subscriptions(self, user_id: int) -> List[Dict]:
        """Get all subscriptions for a user"""
        user_subs = []
        
        for key, sub in self.subscriptions.items():
            if sub.get('user_id') == user_id:
                user_subs.append(sub)
        
        return user_subs
    
    def cancel_subscription(self, user_id: int, event_slug: str) -> bool:
        """Cancel a subscription"""
        subscription_key = f"{user_id}_{event_slug}"
        
        if subscription_key in self.subscriptions:
            self.subscriptions[subscription_key]['status'] = 'cancelled'
            self.subscriptions[subscription_key]['cancelled_at'] = datetime.utcnow().isoformat()
            self.save_subscriptions()
            return True
        
        return False
    
    def get_deposit_instructions(self, user_id: int) -> str:
        """Get deposit instructions for a user's wallet"""
        wallet = self.get_user_wallet(user_id)
        address = wallet.get("address", "ERROR")
        current_balance = self.user_balances.get(user_id, 0.0)
        
        return f"""💰 **Your Polydictor Wallet**

**Your Balance:** {current_balance} USDC
**Cost per Event:** {WATCH_PRICE_USDC} USDC

**Your Deposit Address:**
`{address}`

**How to deposit:**
1. Open Phantom/Solflare wallet
2. Send USDC (on Solana) to address above
3. Wait ~30 seconds for confirmation
4. Use /balance to check updated balance

**Why prepaid?**
- No manual payment per event
- Just /watch and go (auto-deducted)
- Top up once, watch multiple events
- Ultra-low Solana fees

Use /balance anytime to check funds.
Need help? Type /help wallet
"""


# For production blockchain integration:
class SolanaVerifier:
    """
    Production blockchain verification using Solana Web3.
    
    This would replace the MVP manual verification.
    """
    
    def __init__(self):
        self.rpc_url = SOLANA_RPC_URL
        # from solana.rpc.api import Client
        # self.client = Client(self.rpc_url)
    
    async def verify_usdc_transfer(
        self,
        transaction_signature: str,
        expected_amount: float,
        expected_recipient: str
    ) -> bool:
        """
        Verify USDC transaction on Solana.
        
        Steps:
        1. Get transaction details by signature
        2. Parse token transfer instruction
        3. Verify recipient address
        4. Verify amount (in 6 decimals for USDC)
        5. Verify token mint is USDC
        6. Confirm transaction is finalized
        """
        # Implementation would use solana-py:
        # tx = await self.client.get_transaction(transaction_signature)
        # Parse instructions for SPL token transfer
        # Verify mint = EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v (USDC)
        # Verify to/from/amount
        
        # For now, placeholder
        logger.info(f"Would verify Solana transaction: {transaction_signature}")
        return True


# Singleton instances
payment_system = PaymentSystem()
# solana_verifier = SolanaVerifier()  # For production
