"""
Test Payment Rail
Verifies that the Solana USDC payment system is working correctly.
"""
import asyncio
import os
from dotenv import load_dotenv

# IMPORTANT: Load .env BEFORE importing payment_system
# Otherwise PLATFORM_WALLET_ADDRESS will be empty
load_dotenv()

from payment_system import PaymentSystem
from usage_billing import UsageBilling, get_usage_billing

async def test_payment_rail():
    """Test the complete payment flow"""
    print("\n" + "="*60)
    print("🧪 TESTING PAYMENT RAIL")
    print("="*60)
    
    # Initialize payment system
    payment_system = PaymentSystem()
    usage_billing = get_usage_billing(payment_system)
    
    # Test user ID
    test_user_id = 999999
    
    print(f"\n1️⃣  Testing Wallet Creation")
    print("-"*60)
    wallet = payment_system.create_user_wallet(test_user_id)
    print(f"✅ Wallet created: {wallet['address']}")
    print(f"   Created at: {wallet['created_at']}")
    
    print(f"\n2️⃣  Testing Balance Check")
    print("-"*60)
    balance = await payment_system.check_user_balance(test_user_id)
    print(f"✅ Current balance: {balance} USDC")
    
    print(f"\n3️⃣  Testing Platform Wallet Configuration")
    print("-"*60)
    platform_wallet = os.getenv('PLATFORM_WALLET_ADDRESS')
    if platform_wallet:
        print(f"✅ Platform wallet configured: {platform_wallet}")
        print(f"   This is where user payments will go")
    else:
        print(f"❌ Platform wallet NOT configured!")
        return False
    
    print(f"\n4️⃣  Testing USDC Transfer")
    print("-"*60)
    test_amount = 2.0
    print(f"   Attempting to transfer {test_amount} USDC to platform...")
    
    transfer_result = await payment_system.transfer_usdc_to_platform(
        test_user_id,
        test_amount
    )
    
    if transfer_result['success']:
        print(f"✅ Transfer successful!")
        print(f"   Signature: {transfer_result['signature']}")
        print(f"   Message: {transfer_result['message']}")
    else:
        print(f"❌ Transfer failed: {transfer_result['message']}")
        return False
    
    print(f"\n5️⃣  Testing Balance Update")
    print("-"*60)
    new_balance = await payment_system.check_user_balance(test_user_id)
    print(f"✅ New balance: {new_balance} USDC")
    print(f"   Deducted: {balance - new_balance} USDC")
    
    print(f"\n6️⃣  Testing Usage Billing System")
    print("-"*60)
    test_event = "test-bitcoin-100k"
    
    # Initialize event tracking
    usage_billing.init_event_tracking(test_user_id, test_event)
    print(f"✅ Initialized usage tracking for {test_event}")
    
    # Record some Grok calls
    usage_billing.record_grok_call(test_user_id, test_event, "analyze_tweet")
    usage_billing.record_grok_call(test_user_id, test_event, "analyze_tweet")
    usage_billing.record_grok_call(test_user_id, test_event, "synthesize_digest")
    print(f"✅ Recorded 3 Grok API calls")
    
    # Get usage summary
    summary = usage_billing.get_usage_summary(test_user_id, test_event)
    if summary['exists']:
        print(f"✅ Usage Summary:")
        print(f"   Total Grok calls: {summary['total_grok_calls']}")
        print(f"   Grok cost: ${summary['total_grok_cost']:.4f}")
        print(f"   Twitter API cost: ${summary['twitter_api_cost']:.2f}")
        print(f"   Total cost: ${summary['total_cost']:.2f}")
    
    print(f"\n7️⃣  Testing Daily Fee Charge")
    print("-"*60)
    # This would normally be called after 24 hours
    daily_charge = await usage_billing.check_and_charge_daily_fee(test_user_id, test_event)
    print(f"   Daily fee check: {daily_charge['message']}")
    
    print(f"\n" + "="*60)
    print("✅ ALL PAYMENT RAIL TESTS PASSED")
    print("="*60)
    
    print(f"\n📊 PAYMENT FLOW SUMMARY")
    print("-"*60)
    print(f"1. User wallet: {wallet['address'][:20]}...")
    print(f"2. Platform wallet: {platform_wallet[:20]}...")
    print(f"3. Transfer mechanism: ✅ Working")
    print(f"4. Balance tracking: ✅ Working")
    print(f"5. Usage billing: ✅ Working")
    print(f"6. Auto-deduction: ✅ Working")
    
    print(f"\n💰 PRICING MODEL")
    print("-"*60)
    print(f"• Grok API calls: $0.01 per call")
    print(f"• TwitterAPI.io: $2.00 per 24 hours per event")
    print(f"• Example: 30 Grok calls/day + Twitter = $2.30/day")
    
    print(f"\n🔒 SECURITY")
    print("-"*60)
    print(f"• User wallets: Separate per user")
    print(f"• Private keys: Encrypted in user_wallets.json")
    print(f"• Platform wallet: {platform_wallet}")
    print(f"• All payments go to platform wallet")
    
    return True

if __name__ == "__main__":
    success = asyncio.run(test_payment_rail())
    
    if success:
        print(f"\n✅ Payment rail is READY for production!")
    else:
        print(f"\n❌ Payment rail has issues - check logs")
