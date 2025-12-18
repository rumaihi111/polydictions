# 🔐 Wallet Security Model - Custodial with Encryption

## How It Works

### Custodial Wallets
Polydictor uses a **custodial wallet model** similar to popular Telegram crypto bots (Trojan, Bonkbot, Maestro):

1. **System generates a Solana wallet for you**
2. **Private keys are encrypted and stored securely**
3. **System can auto-deduct fees** (Grok API + TwitterAPI.io)
4. **You can withdraw funds anytime** to your personal wallet

### Why Custodial?

**Convenience:**
- No wallet approval needed for every $0.01 Grok call
- Automatic daily $2 TwitterAPI.io fees
- Instant tweet analysis without delays
- Seamless user experience

**Industry Standard:**
All major Telegram trading bots use this model because Telegram doesn't support native wallet connections like Discord/web apps.

---

## 🔒 Security Measures

### 1. Encrypted Private Keys
```
❌ OLD (INSECURE):
"private_key": "2QzHt3vF..."  // Anyone with file access can steal funds

✅ NEW (SECURE):
"private_key_encrypted": "gAAAAABh3k2..."  // Encrypted with Fernet (AES-128)
```

Private keys are encrypted using **Fernet (symmetric encryption)**:
- Master key stored in `.env` (never committed to git)
- AES-128 CBC mode with HMAC authentication
- Keys only decrypted in-memory when signing transactions
- Immediately destroyed after use

### 2. Master Key Security
```
WALLET_MASTER_KEY=6M4j5PM8ieTsxQ5ma2XTVvFMZOdXcW-73E7JLU4g3Fo=
```

**Critical Security Rules:**
- ✅ Stored in `.env` file
- ✅ Added to `.gitignore` (never committed)
- ✅ Different key per deployment (dev/staging/prod)
- ✅ Rotated periodically (every 90 days recommended)
- ❌ NEVER share this key
- ❌ NEVER commit to GitHub
- ❌ NEVER log this key

### 3. Withdrawal Functionality
Users can withdraw ALL funds anytime:
```
/withdraw <your_solana_address> [amount]
```

**Examples:**
- `/withdraw 8zHfXy... 10.5` - Withdraw 10.5 USDC
- `/withdraw 8zHfXy...` - Withdraw ALL available USDC

This ensures users always have an exit route.

---

## ⚠️ User Disclaimers

### What Users See on `/start`:
```
🔐 Wallet Security Notice

You're using a CUSTODIAL wallet managed by Polydictor.

✅ We encrypt your private keys
✅ You can withdraw anytime with /withdraw
✅ Used by major bots like Trojan, Bonkbot

⚠️ Risks:
• Platform holds encrypted private keys
• Deposit only what you're willing to use
• Withdraw funds when not actively using

Your wallet: 6yGeEwDivwge...
Deposit USDC to this address to get started!
```

### What Users See Before Depositing:
```
💰 How to Deposit

1. Send USDC (Solana) to:
   6yGeEwDivwge7prTJGe8aMTkfuVMsXhxq4H8KX3sXMVQ

2. Start with $10-20 for testing
3. Withdraw anytime with /withdraw

⚠️ Only deposit what you plan to use for monitoring.
```

---

## 🛡️ Platform Security Responsibilities

### What You (Platform Owner) Must Do:

1. **Secure the Master Key**
   - Store in `.env` only
   - Use environment variables in production
   - Different keys for dev/staging/prod
   - Rotate every 90 days

2. **Secure the Server**
   - Use SSH keys, not passwords
   - Enable firewall (only ports 80/443/22)
   - Keep system updated
   - Monitor access logs

3. **Backup Encrypted Wallets**
   - Daily backup of `user_wallets.json`
   - Store backups encrypted
   - Test restoration process

4. **Monitor for Breaches**
   - Log all withdrawal attempts
   - Alert on unusual activity
   - Rate limit withdrawals

5. **Insurance (Optional but Recommended)**
   - Consider setting aside funds
   - Cover potential losses if hacked
   - Build user trust

---

## 🔍 How Encryption Works

### When Creating Wallet:
```python
# 1. Generate Solana keypair
keypair = Keypair()
private_key_bytes = bytes(keypair)  # Raw private key

# 2. Encrypt with master key
cipher = Fernet(MASTER_KEY)
encrypted = cipher.encrypt(private_key_bytes)

# 3. Store only encrypted version
wallet = {
    "address": str(keypair.pubkey()),
    "private_key_encrypted": encrypted.decode(),
    "encrypted": True
}
```

### When Signing Transaction:
```python
# 1. Load encrypted key from storage
encrypted_key = wallet["private_key_encrypted"]

# 2. Decrypt in-memory (never touches disk)
cipher = Fernet(MASTER_KEY)
private_key_bytes = cipher.decrypt(encrypted_key.encode())

# 3. Sign transaction
keypair = Keypair.from_bytes(private_key_bytes)
tx.sign(keypair)

# 4. Immediately destroy decrypted key
del private_key_bytes
del keypair
```

Key never exists unencrypted on disk!

---

## 📊 Risk Comparison

| Model | User Control | Convenience | Platform Risk | User Risk |
|-------|--------------|-------------|---------------|-----------|
| **Non-Custodial** | 100% | Low | None | User error |
| **Custodial (Unencrypted)** | 0% | High | Total liability | Total trust |
| **Custodial (Encrypted)** ⭐ | Withdrawable | High | Moderate | Moderate |
| **Smart Contract** | High | Medium | Low | Contract bugs |

Polydictor uses **Custodial (Encrypted)** - the industry standard for Telegram bots.

---

## 🚀 What Makes This Better Than Average

### Compared to Other Telegram Bots:

**Most bots:**
- ❌ Don't disclose security model
- ❌ No withdrawal feature
- ❌ Private keys unencrypted
- ❌ No transparency

**Polydictor:**
- ✅ Full disclosure of custodial model
- ✅ Withdrawal anytime
- ✅ Encrypted private keys
- ✅ Open source (users can audit)
- ✅ Usage-based billing (no lock-in)

---

## 💡 Best Practices for Users

1. **Start Small** - Deposit $10-20 for testing
2. **Withdraw Regularly** - Don't leave large balances
3. **Monitor Usage** - Check `/usage` and `/balance` often
4. **Understand Risks** - You're trusting the platform
5. **Use Multiple Bots** - Don't put all funds in one place

---

## 🔄 Key Rotation Procedure

**Every 90 days:**

1. Generate new master key:
```bash
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key())"
```

2. Re-encrypt all wallets:
```python
old_cipher = Fernet(OLD_KEY)
new_cipher = Fernet(NEW_KEY)

for user_id, wallet in user_wallets.items():
    # Decrypt with old key
    decrypted = old_cipher.decrypt(wallet["private_key_encrypted"])
    
    # Re-encrypt with new key
    wallet["private_key_encrypted"] = new_cipher.encrypt(decrypted).decode()
```

3. Update `.env` with new key

4. Test withdrawal on test account

5. Monitor for any issues

---

## 📞 Incident Response Plan

### If Master Key is Compromised:

**Immediate Actions (< 1 hour):**
1. Take bot offline
2. Generate new master key
3. Re-encrypt all wallets with new key
4. Audit withdrawal logs for suspicious activity

**Short-term (< 24 hours):**
1. Notify all users via broadcast
2. Pause all automated deductions
3. Offer emergency withdrawal window
4. Investigate breach source

**Long-term (< 7 days):**
1. Review and update security measures
2. Consider migration to non-custodial
3. Implement additional monitoring
4. Publish transparent incident report

---

## ✅ Security Checklist

Before deploying to production:

- [ ] Master key generated and in `.env`
- [ ] `.env` added to `.gitignore`
- [ ] Different master keys for dev/staging/prod
- [ ] Server has firewall enabled
- [ ] SSH key authentication only
- [ ] Daily backups configured
- [ ] Withdrawal feature tested
- [ ] User disclaimers added to bot
- [ ] Monitoring/alerting set up
- [ ] Incident response plan documented
- [ ] Insurance fund allocated (optional)

---

**Bottom Line:** This is as secure as custodial wallets get. Users get convenience, you minimize liability, and everyone understands the tradeoffs. 🎯
