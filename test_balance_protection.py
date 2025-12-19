"""
Test Balance Protection & Overdraft Prevention

This script tests that users cannot overdraft and monitoring auto-pauses
when balance is insufficient.
"""

import asyncio
import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Import directly (avoid importing bot.py which starts the bot)
from usage_billing import UsageBilling
from payment_system import PaymentSystem

async def test_balance_protection():
    """Test overdraft protection"""
    print("\n" + "="*70)
    print("TESTING BALANCE PROTECTION & OVERDRAFT PREVENTION")
    print("="*70 + "\n")
    
    # Initialize systems
    payment_system = PaymentSystem()
    
    # Mock transfer for testing (skip actual Solana transaction)
    original_transfer = payment_system.transfer_usdc_to_platform
    async def mock_transfer(user_id, amount):
        """Mock transfer that just updates balance"""
        if user_id not in payment_system.user_balances:
            return {"success": False, "error": "User not found"}
        
        current_balance = payment_system.user_balances[user_id]
        if current_balance < amount:
            return {"success": False, "error": "Insufficient balance"}
        
        # Just deduct from balance (skip Solana transaction)
        payment_system.user_balances[user_id] -= amount
        payment_system.save_user_balances()
        
        return {
            "success": True,
            "signature": "mock_signature_" + str(user_id),
            "amount": amount
        }
    
    payment_system.transfer_usdc_to_platform = mock_transfer
    
    usage_billing = UsageBilling(payment_system)
    
    # Test user
    test_user_id = 999999
    test_event = "test-event-balance"
    
    print("Test 1: Can afford Grok call with sufficient balance")
    print("-" * 70)
    
    # Set balance to $5
    payment_system.user_balances[test_user_id] = 5.0
    payment_system.save_user_balances()
    
    result = await usage_billing.can_afford_grok_call(test_user_id)
    print(f"Balance: $5.00")
    print(f"Can afford: {result['can_afford']}")
    print(f"Message: {result['message']}")
    assert result['can_afford'] == True, "Should be able to afford with $5 balance"
    print("✅ PASSED\n")
    
    print("Test 2: Cannot afford Grok call with insufficient balance")
    print("-" * 70)
    
    # Set balance to $1.50 (below minimum $2.01)
    payment_system.user_balances[test_user_id] = 1.50
    payment_system.save_user_balances()
    
    result = await usage_billing.can_afford_grok_call(test_user_id)
    print(f"Balance: $1.50")
    print(f"Can afford: {result['can_afford']}")
    print(f"Message: {result['message']}")
    assert result['can_afford'] == False, "Should NOT afford with $1.50 balance"
    print("✅ PASSED\n")
    
    print("Test 3: Record Grok call blocks when balance insufficient")
    print("-" * 70)
    
    # Initialize tracking for test user
    usage_billing.init_event_tracking(test_user_id, test_event)
    
    # Try to record Grok call with $1.50 balance
    billing_result = await usage_billing.record_grok_call(
        test_user_id, 
        test_event, 
        "analyze_tweet"
    )
    
    print(f"Balance: $1.50")
    print(f"Success: {billing_result['success']}")
    print(f"Should pause: {billing_result.get('should_pause', False)}")
    print(f"Message: {billing_result['message']}")
    
    assert billing_result['success'] == False, "Grok call should be BLOCKED"
    assert billing_result.get('should_pause') == True, "Should signal to pause monitoring"
    
    # Verify balance didn't change (no charge)
    balance_after = payment_system.user_balances[test_user_id]
    assert balance_after == 1.50, "Balance should NOT decrease (blocked charge)"
    print(f"Balance after (unchanged): ${balance_after:.2f}")
    print("✅ PASSED\n")
    
    print("Test 4: Record Grok call succeeds with sufficient balance")
    print("-" * 70)
    
    # Set balance to $10
    payment_system.user_balances[test_user_id] = 10.0
    payment_system.save_user_balances()
    
    billing_result = await usage_billing.record_grok_call(
        test_user_id, 
        test_event, 
        "analyze_tweet"
    )
    
    print(f"Starting balance: $10.00")
    print(f"Success: {billing_result['success']}")
    print(f"Message: {billing_result['message']}")
    print(f"New balance: ${billing_result['balance']:.2f}")
    
    assert billing_result['success'] == True, "Grok call should SUCCEED"
    assert billing_result['balance'] == 9.99, "Balance should decrease by $0.01"
    print("✅ PASSED\n")
    
    print("Test 5: Daily fee blocks when balance insufficient")
    print("-" * 70)
    
    # Set balance to $1.50 (below $2 daily fee)
    payment_system.user_balances[test_user_id] = 1.50
    payment_system.save_user_balances()
    
    # Manipulate last_billing_cycle to simulate 24 hours passed
    from datetime import datetime, timedelta
    user_id_str = str(test_user_id)
    if user_id_str in usage_billing.usage_data and test_event in usage_billing.usage_data[user_id_str]:
        # Set last billing cycle to 25 hours ago
        past_time = datetime.utcnow() - timedelta(hours=25)
        usage_billing.usage_data[user_id_str][test_event]["last_billing_cycle"] = past_time.isoformat()
        usage_billing.save_usage_data()
    
    # Try to charge daily fee
    result = await usage_billing.check_and_charge_daily_fee(
        test_user_id,
        test_event
    )
    
    print(f"Balance: $1.50")
    print(f"Charged: {result.get('charged', False)}")
    print(f"Should stop: {result.get('should_stop', False)}")
    print(f"Message: {result.get('message', '')}")
    
    assert result.get('charged') == False, "Daily fee should be BLOCKED"
    assert result.get('should_stop') == True, "Should signal to stop agent"
    
    # Verify balance didn't change
    balance_after = payment_system.user_balances[test_user_id]
    assert balance_after == 1.50, "Balance should NOT decrease (blocked charge)"
    print(f"Balance after (unchanged): ${balance_after:.2f}")
    print("✅ PASSED\n")
    
    print("Test 6: Daily fee succeeds with sufficient balance")
    print("-" * 70)
    
    # Set balance to $10
    payment_system.user_balances[test_user_id] = 10.0
    payment_system.save_user_balances()
    
    # Set last billing cycle to 25 hours ago
    past_time = datetime.utcnow() - timedelta(hours=25)
    usage_billing.usage_data[user_id_str][test_event]["last_billing_cycle"] = past_time.isoformat()
    usage_billing.save_usage_data()
    
    result = await usage_billing.check_and_charge_daily_fee(
        test_user_id,
        test_event
    )
    
    print(f"Starting balance: $10.00")
    print(f"Charged: {result.get('charged', False)}")
    print(f"Amount: ${result.get('amount', 0):.2f}")
    print(f"New balance: ${result.get('new_balance', 0):.2f}")
    
    assert result.get('charged') == True, "Daily fee should SUCCEED"
    assert result.get('new_balance') == 8.0, "Balance should decrease by $2.00"
    print("✅ PASSED\n")
    
    print("Test 7: Low balance warning triggers correctly")
    print("-" * 70)
    
    # Set balance to $12 (above $10 threshold - no warning)
    payment_system.user_balances[test_user_id] = 12.0
    payment_system.save_user_balances()
    
    # Set last billing cycle to 25 hours ago
    past_time = datetime.utcnow() - timedelta(hours=25)
    usage_billing.usage_data[user_id_str][test_event]["last_billing_cycle"] = past_time.isoformat()
    usage_billing.save_usage_data()
    
    # Charge daily fee
    result = await usage_billing.check_and_charge_daily_fee(
        test_user_id,
        test_event
    )
    
    print(f"Balance before: $12.00")
    print(f"Balance after: ${result.get('new_balance', 0):.2f}")
    print(f"Warning: {result.get('warning')}")
    
    # $12 - $2 = $10, should trigger standard warning
    assert result.get('new_balance') == 10.0
    assert result.get('warning') is None, "No warning at $10 (threshold)"
    print("✅ PASSED (no warning at threshold)\n")
    
    # Now charge again to drop below $10
    print("Charging again to drop below $10...")
    payment_system.user_balances[test_user_id] = 9.0
    payment_system.save_user_balances()
    
    # Set last billing cycle to 25 hours ago
    past_time = datetime.utcnow() - timedelta(hours=25)
    usage_billing.usage_data[user_id_str][test_event]["last_billing_cycle"] = past_time.isoformat()
    usage_billing.save_usage_data()
    
    result = await usage_billing.check_and_charge_daily_fee(
        test_user_id,
        test_event
    )
    
    print(f"Balance before: $9.00")
    print(f"Balance after: ${result.get('new_balance', 0):.2f}")
    print(f"Warning present: {result.get('warning') is not None}")
    
    # $9 - $2 = $7, should trigger standard warning
    assert result.get('new_balance') == 7.0
    assert result.get('warning') is not None, "Should have warning below $10"
    assert "Balance Notice" in result.get('warning', ''), "Should be standard warning"
    print("✅ PASSED (standard warning triggered)\n")
    
    # Drop below $5 for critical warning
    print("Charging again to drop below $5...")
    payment_system.user_balances[test_user_id] = 4.5
    payment_system.save_user_balances()
    
    # Set last billing cycle to 25 hours ago
    past_time = datetime.utcnow() - timedelta(hours=25)
    usage_billing.usage_data[user_id_str][test_event]["last_billing_cycle"] = past_time.isoformat()
    usage_billing.save_usage_data()
    
    result = await usage_billing.check_and_charge_daily_fee(
        test_user_id,
        test_event
    )
    
    print(f"Balance before: $4.50")
    print(f"Balance after: ${result.get('new_balance', 0):.2f}")
    print(f"Warning present: {result.get('warning') is not None}")
    
    # $4.5 - $2 = $2.5, should trigger critical warning
    assert result.get('new_balance') == 2.5
    assert result.get('warning') is not None, "Should have warning below $5"
    assert "LOW BALANCE WARNING" in result.get('warning', ''), "Should be critical warning"
    print("✅ PASSED (critical warning triggered)\n")
    
    print("\n" + "="*70)
    print("ALL TESTS PASSED ✅")
    print("="*70)
    print("\nBalance Protection Summary:")
    print("  ✅ Cannot overdraft (balance checks before every charge)")
    print("  ✅ Grok calls blocked when balance insufficient")
    print("  ✅ Daily fees blocked when balance insufficient")
    print("  ✅ Monitoring auto-pauses (should_pause flag)")
    print("  ✅ Low balance warnings trigger correctly")
    print("  ✅ No negative balances possible")
    print("\nUser is PROTECTED from overspending! 🛡️")
    
if __name__ == "__main__":
    asyncio.run(test_balance_protection())
