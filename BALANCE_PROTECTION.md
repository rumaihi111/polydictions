# Balance Protection & Overdraft Prevention

## Overview

Polydictor implements **comprehensive balance protection** to ensure users never spend more than they have. The system automatically pauses monitoring when balance is insufficient and sends warnings as balance runs low.

---

## 🛡️ Protection Mechanisms

### 1. **Initial Balance Check** (Starting Monitoring)
- **Minimum Required**: $5 USDC to start monitoring any event
- **Why**: Ensures at least 2 days of monitoring coverage (1 day + buffer)
- **Implementation**: `payment_system.py` - `charge_user_for_watch()`

```python
if balance < MIN_BALANCE_USDC:  # $5
    return "Insufficient balance. Please deposit at least $5 USDC"
```

### 2. **Pre-Call Balance Checks** (Before Every Grok Call)
- **Check Before**: Every Grok API call ($0.01 each)
- **Requirement**: Balance must cover Grok call + 1 day TwitterAPI.io fee ($2.01 minimum)
- **Implementation**: `usage_billing.py` - `can_afford_grok_call()` and `record_grok_call()`

```python
# Balance check at 4 call points:
1. Priority node analysis (immediate critical developments)
2. Regular tweet analysis (pre-filtered tweets)
3. Hourly digest synthesis (summary of past hour)
4. 6-hour ruleset refinement (strategy optimization)
```

**What Happens on Insufficient Balance**:
- ❌ Grok call is **blocked** (not executed)
- 🔔 User receives notification via Telegram
- ⏸️ Monitoring **auto-pauses** for that user
- 🧹 User removed from subscriber list
- 🛑 No negative balances (can't go below $0)

### 3. **Daily Fee Protection** (Every 24 Hours)
- **Check Before**: Charging $2 USDC TwitterAPI.io daily fee
- **Requirement**: Balance must be ≥ $2 USDC
- **Implementation**: `usage_billing.py` - `check_and_charge_daily_fee()`

**What Happens on Insufficient Balance**:
- ❌ Daily fee is **not charged**
- 🔔 User receives notification
- ⏸️ Monitoring **auto-pauses**
- 🧹 User removed from event
- 🛑 Agent stops if no subscribers remain

### 4. **Low Balance Warnings** (Proactive Alerts)

#### Critical Warning (Balance < $5)
```
⚠️ LOW BALANCE WARNING

Your balance is $4.23 USDC.

You have less than 2 days of monitoring remaining.
Please deposit more funds to avoid service interruption.

💰 Deposit: /deposit
```
- **Sent**: After each daily fee charge
- **Trigger**: Balance drops below $5 (~2 days remaining)

#### Standard Warning (Balance < $10)
```
💡 Balance Notice

Your balance is $8.75 USDC.

You have approximately 3 days of monitoring remaining.
Consider depositing more funds soon.

💰 Deposit: /deposit
```
- **Sent**: After each daily fee charge
- **Trigger**: Balance drops below $10 (~4 days remaining)

---

## 📊 Balance Protection Flow

```
┌─────────────────────────────────────────────────────────────┐
│                    USER STARTS MONITORING                    │
│                      /watch <event>                          │
└────────────────────────┬────────────────────────────────────┘
                         │
                         ▼
             ┌───────────────────────┐
             │ Check: Balance ≥ $5?  │
             └───────┬───────────────┘
                     │
         ┌───────────┴───────────┐
         │                       │
         ▼                       ▼
      ✅ YES                  ❌ NO
   START MONITORING      "Insufficient balance"
         │                  /deposit to add funds
         │
         ▼
┌──────────────────────────────────────────────────────────────┐
│                   MONITORING ACTIVE                          │
│                                                              │
│  Every Tweet → Priority Check → Pre-Filter → Grok Analysis  │
└────────────────────────┬─────────────────────────────────────┘
                         │
                         ▼
        ┌────────────────────────────────┐
        │ Before EACH Grok Call:         │
        │ Check: Balance ≥ $2.01?        │
        │ ($0.01 Grok + $2 daily fee)    │
        └────────┬───────────────────────┘
                 │
     ┌───────────┴──────────┐
     │                      │
     ▼                      ▼
  ✅ YES                 ❌ NO
Execute Grok          ⏸️ PAUSE MONITORING
Deduct $0.01          🔔 Notify User
Continue              🧹 Remove from Event
     │
     │
     ▼
┌──────────────────────────────────────────────────────────────┐
│                   EVERY 24 HOURS                             │
│                                                              │
│              Daily TwitterAPI.io Fee Due                     │
└────────────────────────┬─────────────────────────────────────┘
                         │
                         ▼
        ┌────────────────────────────────┐
        │ Check: Balance ≥ $2?           │
        └────────┬───────────────────────┘
                 │
     ┌───────────┴──────────┐
     │                      │
     ▼                      ▼
  ✅ YES                 ❌ NO
Charge $2             ⏸️ PAUSE MONITORING
Deduct from Balance   🔔 Notify User
     │                🧹 Remove from Event
     │                🛑 Stop Agent (no subscribers)
     ▼
┌────────────────────────────────┐
│ After Daily Charge:            │
│ Check for Warnings             │
└────────┬───────────────────────┘
         │
         ▼
┌────────────────────────────────┐
│ Balance < $5?                  │
│   → ⚠️ Critical Warning        │
│                                │
│ Balance < $10?                 │
│   → 💡 Standard Warning        │
└────────────────────────────────┘
```

---

## 💰 Cost Breakdown

### Per Event Monitoring (Average):
- **Grok Calls**: ~50/day × $0.01 = **$0.50/day**
- **TwitterAPI.io**: $2/day (flat fee)
- **Total**: **~$2.50/day** per event

### Minimum Balance Requirements:
- **To Start**: $5 USDC (2 days coverage)
- **To Continue**: Must maintain > $2.01 for next Grok call
- **Recommended**: $10+ USDC (4 days coverage)

---

## 🔔 Notification System

### Auto-Pause Notification
```
⚠️ MONITORING PAUSED

Your monitoring for:
_Will Bitcoin reach $200K by year end?_

has been paused due to low balance.

💰 Current Balance: $1.85 USDC

Insufficient balance. Need $2.01 (Grok + daily fee). Current: $1.85

To resume monitoring:
1️⃣ Deposit USDC: /deposit
2️⃣ Check balance: /balance
3️⃣ Restart monitoring: /watch
```

### Low Balance Warnings
- **Critical** (< $5): Sent after daily charge
- **Standard** (< $10): Sent after daily charge
- **Frequency**: Once per 24 hours (with daily fee charge)

---

## ✅ Protection Guarantees

1. ✅ **No Overdraft**: Cannot spend more than you have
2. ✅ **No Negative Balances**: System blocks charges when balance insufficient
3. ✅ **Automatic Pause**: Monitoring stops when balance too low
4. ✅ **Proactive Warnings**: Notified before service interruption
5. ✅ **Clean Shutdown**: TwitterAPI.io monitoring removed, tasks cancelled
6. ✅ **User Control**: Can withdraw funds anytime (/withdraw)

---

## 🔧 Technical Implementation

### Files Modified:
1. **usage_billing.py**:
   - `can_afford_grok_call()` - Check balance before Grok calls
   - `record_grok_call()` - Changed to async, returns success/failure
   - `check_and_charge_daily_fee()` - Returns warnings, should_stop flag

2. **agent.py**:
   - All 4 Grok call points updated with balance checks
   - `_notify_low_balance_and_pause()` - Notify and remove user
   - `_daily_fee_scheduler()` - Handle warnings and auto-pause

### Balance Check Points:
```python
# 1. Priority Node Analysis (agent.py line ~380)
billing_result = await usage_billing.record_grok_call(user_id, event_slug, "analyze_tweet_priority")
if not billing_result.get("success"):
    await _notify_low_balance_and_pause(user_id, event_slug, billing_result)

# 2. Regular Tweet Analysis (agent.py line ~435)
billing_result = await usage_billing.record_grok_call(user_id, event_slug, "analyze_tweet")
if not billing_result.get("success"):
    await _notify_low_balance_and_pause(user_id, event_slug, billing_result)

# 3. Hourly Digest (agent.py line ~695)
billing_result = await usage_billing.record_grok_call(user_id, event_slug, "synthesize_digest")
if not billing_result.get("success"):
    await _notify_low_balance_and_pause(user_id, event_slug, billing_result)

# 4. Ruleset Refinement (agent.py line ~770)
billing_result = await usage_billing.record_grok_call(user_id, event_slug, "refine_ruleset")
if not billing_result.get("success"):
    await _notify_low_balance_and_pause(user_id, event_slug, billing_result)
```

---

## 🧪 Testing Scenarios

### Scenario 1: Insufficient Balance to Start
```bash
User Balance: $3.00
Action: /watch bitcoin-200k
Result: ❌ "Insufficient balance. Need $5 USDC minimum"
```

### Scenario 2: Run Out During Monitoring
```bash
User Balance: $6.00
Day 1: Start monitoring (OK)
Day 2: Daily fee charged → Balance $4.00
Day 3: Grok call → Check fails ($4.00 < $2.01 required)
Result: ⏸️ Monitoring PAUSED, user notified
```

### Scenario 3: Low Balance Warning
```bash
User Balance: $15.00
Day 1-5: Monitoring active
Day 6: Balance → $7.50
Result: 💡 "Balance < $10, ~3 days remaining"
```

### Scenario 4: Multiple Users, One Runs Out
```bash
Event: bitcoin-200k
Subscribers: [User A ($20), User B ($3)]

Tweet arrives → Grok analysis needed
User A: ✅ Balance OK → Charged $0.01 → Analysis proceeds
User B: ❌ Balance insufficient → Paused → Removed from event

Result: Analysis continues for User A only
```

---

## 📝 User Commands

### Check Balance
```
/balance
```
Shows: Wallet address, current balance, estimated days remaining

### Deposit Funds
```
/deposit
```
Shows: Deposit address, instructions, current balance

### Withdraw Funds
```
/withdraw <amount> <destination_address>
```
Example: `/withdraw 10 YourSolanaWalletAddress`

### Check Monitoring Status
```
/mystatus
```
Shows: Active monitoring events, costs, balance

---

## 🎯 Key Takeaways

1. **You control your spending**: System cannot charge more than you have
2. **Proactive warnings**: Get notified before running out
3. **Automatic protection**: Monitoring pauses when balance insufficient
4. **Transparent costs**: See exactly what you're paying for
5. **Exit anytime**: Withdraw remaining balance whenever you want

**Bottom Line**: Your balance is protected at every step. The system ensures you never go negative and always have visibility into your spending.
