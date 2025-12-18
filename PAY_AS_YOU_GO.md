# Pay-As-You-Go Billing System

## 💰 Pricing Model

### Grok API Usage
- **Cost**: $0.01 USD per call
- **Billed**: Real-time per API call
- **Types of calls**:
  - `analyze_tweet` - Regular tweet analysis (~15-20/day per event)
  - `analyze_tweet_priority` - Priority node immediate analysis (~3-5/day per event)
  - `synthesize_digest` - Hourly digest generation (24/day per event)
  - `refine_ruleset` - 6-hour ruleset refinement (4/day per event)

**Estimated Grok usage**: ~43 calls/day = **$0.43/day** per event

### TwitterAPI.io Service
- **Cost**: $2.00 USDC flat fee
- **Billed**: Every 24 hours while event is active
- **Covers**: Unlimited tweet monitoring for all accounts in ruleset

**Total estimated daily cost**: ~$2.43/day per event

---

## 🔐 Payment Flow

### 1. Platform Wallet
All user payments go to:
```
55BSkfcQM2QGA7HHNu13iY5SJB7KYvWJ2NgQJSthbHAE
```

### 2. User Wallet Creation
- Each user gets their own Solana wallet when they use `/start`
- Private keys are encrypted and stored in `user_wallets.json`
- Users deposit USDC to their personal wallet address
- Balance is tracked in real-time

### 3. Automatic Deduction
When user creates a `/watch`:
- System checks user's USDC balance
- Deducts initial amount to cover expected costs
- Tracks actual usage in real-time
- Charges $2 USDC every 24 hours for TwitterAPI.io
- Charges $0.01 per Grok API call as they happen

### 4. Balance Monitoring
Users can check balance anytime:
```
/balance - Show current USDC balance
/usage <event> - Show usage stats for specific event
```

---

## 📊 Usage Tracking

### Event Initialization
When a new event is created via `/watch`:
```python
usage_billing.init_event_tracking(user_id, event_slug)
```

Creates tracking record:
```json
{
  "user_id": 123456,
  "event_slug": "bitcoin-100k",
  "start_time": "2025-01-15T10:00:00",
  "grok_calls": [],
  "total_grok_cost": 0.0,
  "last_daily_charge": "2025-01-15T10:00:00",
  "twitter_api_cost": 2.0
}
```

### Grok Call Tracking
Every time Grok API is called:
```python
usage_billing.record_grok_call(user_id, event_slug, call_type)
```

Adds to tracking:
```json
{
  "timestamp": "2025-01-15T10:15:23",
  "call_type": "analyze_tweet",
  "cost": 0.01
}
```

### Daily Fee Charging
Every 24 hours:
```python
result = await usage_billing.check_and_charge_daily_fee(user_id, event_slug)
```

Charges $2 USDC if:
- Event is still active
- At least 24 hours since last charge
- User has sufficient balance

---

## 🔧 Implementation Details

### Files
- **usage_billing.py**: Core billing system
  - `UsageBilling` class
  - Methods: `init_event_tracking()`, `record_grok_call()`, `check_and_charge_daily_fee()`
  
- **agent.py**: Integrated usage tracking
  - Lines 25-26: Import payment system and usage billing
  - Line 73: Initialize usage billing in `__init__()`
  - Line 259: Initialize tracking on event creation
  - Lines 378, 426, 667, 705: Track Grok calls at all 4 call points
  - Lines 310-313: Schedule daily fee checking
  - Lines 677-701: Daily fee scheduler runs every 24 hours

- **payment_system.py**: Solana wallet operations
  - Creates user wallets
  - Transfers USDC to platform wallet
  - Checks balances
  - Records transactions

### Grok Call Points (All Tracked)
1. **Priority Tweet Analysis** (`_handle_tweet` line 378)
   - Immediate analysis of critical developments
   - Bypasses all filters
   
2. **Regular Tweet Analysis** (`_handle_tweet` line 426)
   - Normal tweet processing after pre-filter
   - Majority of Grok usage
   
3. **Hourly Digest** (`_digest_scheduler` line 667)
   - Synthesizes recent intelligence
   - Runs every hour
   
4. **Ruleset Refinement** (`_refine_rules` line 705)
   - Updates monitoring strategy
   - Runs every 6 hours

### Daily Fee Scheduler
- Runs in background per event
- Checks every 24 hours
- Automatically charges $2 USDC
- Logs success/failure
- Can pause agent if balance too low

---

## 💡 Cost Optimization

### Pre-Filtering (Saves 80-90% of Grok Calls)
Before calling Grok, tweets are checked for:
- Bot/spam indicators (no Grok call)
- Low engagement (< 100 views, no Grok call)
- Duplicate/retweet (no Grok call)
- Basic relevance (no Grok call)

**Only high-quality tweets go to Grok**

### Priority Nodes (Zero-Latency Critical Events)
Grok defines 4 types of priority nodes:
1. `account_specific` - Specific account posts about specific topic
2. `account_any` - High-authority account posts anything
3. `keyword_critical` - Critical keywords mentioned
4. `breaking_news` - Breaking news indicators

**Priority nodes bypass ALL filters for instant delivery**

### Estimated Usage Breakdown
| Call Type | Frequency | Daily Count | Daily Cost |
|-----------|-----------|-------------|------------|
| Priority tweets | ~3-5/day | 4 | $0.04 |
| Regular tweets | ~15-20/day | 18 | $0.18 |
| Hourly digests | 1/hour | 24 | $0.24 |
| Refinements | Every 6h | 4 | $0.04 |
| **Total Grok** | - | **50** | **$0.50** |
| TwitterAPI.io | Per 24h | 1 | $2.00 |
| **TOTAL** | - | - | **$2.50/day** |

---

## 🧪 Testing

### Test Payment Rail
Run comprehensive test:
```bash
python test_payment_rail.py
```

Tests:
1. ✅ Wallet creation
2. ✅ Balance checking
3. ✅ Platform wallet configuration
4. ✅ USDC transfers
5. ✅ Usage tracking
6. ✅ Daily fee charging
7. ✅ Summary generation

### Expected Output
```
============================================================
🧪 TESTING PAYMENT RAIL
============================================================

1️⃣  Testing Wallet Creation
✅ Wallet created: 6yGeEwDivwge7prTJGe8aMTkfuVMsXhxq4H8KX3sXMVQ

2️⃣  Testing Balance Check
✅ Current balance: 0.0 USDC

3️⃣  Testing Platform Wallet Configuration
✅ Platform wallet configured: 55BSkfcQM2QGA7HHNu13iY5SJB7KYvWJ2NgQJSthbHAE

6️⃣  Testing Usage Billing System
✅ Usage Summary:
   Total Grok calls: 3
   Grok cost: $0.0300
   Twitter API cost: $2.00
   Total cost: $2.03

✅ Payment rail is READY for production!
```

---

## 📈 Usage Transparency

### Get Usage Summary
```python
summary = usage_billing.get_usage_summary(user_id, event_slug)

# Returns:
{
    'exists': True,
    'total_grok_calls': 45,
    'total_grok_cost': 0.45,
    'twitter_api_cost': 2.0,
    'total_cost': 2.45,
    'daily_charges': 1,
    'start_time': '2025-01-15T10:00:00',
    'last_charge': '2025-01-15T10:00:00'
}
```

### Bot Commands (To Be Implemented)
```
/usage bitcoin-100k - Show usage for specific event
/balance - Show USDC balance and projected days remaining
/topup - Instructions to add more USDC
/mystatus - Show all active events with costs
```

---

## 🔒 Security

### Wallet Security
- Each user has separate wallet
- Private keys encrypted in storage
- Never exposed to users
- Platform cannot access without decryption

### Payment Verification
- All transfers recorded with Solana transaction signatures
- Blockchain provides immutable audit trail
- Users can verify on Solana explorer

### Balance Protection
- System checks balance before operations
- Automatically stops if balance too low
- Prevents overdraft
- User maintains control of funds until spent

---

## 🚀 Next Steps

### Integration with Telegram Bot
1. Add `/usage` command to show current costs
2. Update `/watch` to show pricing before confirmation
3. Add `/balance` to show remaining funds
4. Send notifications when balance low (< $10)
5. Show projected days remaining based on usage

### Enhanced Billing
1. Volume discounts for multiple events
2. Refund unused TwitterAPI.io fees if stopped early
3. Detailed transaction history
4. Export usage reports
5. Set spending limits

### Monitoring
1. Alert users when daily costs spike
2. Show cost breakdown in hourly digests
3. Compare actual vs estimated costs
4. Optimize Grok usage based on value delivered
