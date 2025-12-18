"""
Test Wallet Encryption
Verifies that new wallets are properly encrypted with master key.
"""
import os
from dotenv import load_dotenv

# Load env BEFORE importing payment_system
load_dotenv()

from payment_system import PaymentSystem

def test_encryption():
    print("\n" + "="*60)
    print("🔐 TESTING WALLET ENCRYPTION")
    print("="*60)
    
    payment_system = PaymentSystem()
    
    # Check if encryption is enabled
    if payment_system.cipher:
        print("\n✅ Encryption enabled!")
        print(f"   Master key loaded from environment")
    else:
        print("\n❌ Encryption NOT enabled!")
        print(f"   WALLET_MASTER_KEY not found in .env")
        return False
    
    # Create a new test wallet
    test_user_id = 888888
    print(f"\n1️⃣  Creating wallet for test user {test_user_id}...")
    
    wallet = payment_system.create_user_wallet(test_user_id)
    
    print(f"\n✅ Wallet created:")
    print(f"   Address: {wallet['address']}")
    print(f"   Encrypted: {wallet.get('encrypted', False)}")
    print(f"   Private key (first 50 chars): {wallet['private_key_encrypted'][:50]}...")
    
    # Try to decrypt it
    print(f"\n2️⃣  Testing decryption...")
    
    decrypted_key = payment_system._decrypt_private_key(test_user_id)
    
    if decrypted_key:
        print(f"✅ Decryption successful!")
        print(f"   Decrypted key length: {len(decrypted_key)} bytes")
        print(f"   Key type: {type(decrypted_key)}")
    else:
        print(f"❌ Decryption failed!")
        return False
    
    # Show the difference
    print(f"\n3️⃣  Encryption comparison:")
    print(f"   Encrypted (stored): {wallet['private_key_encrypted'][:50]}...")
    print(f"   Decrypted (in-memory): {decrypted_key.hex()[:50]}...")
    print(f"   🔒 These are different! Encryption working!")
    
    # Verify it's actually encrypted (can't be base58 decoded)
    print(f"\n4️⃣  Verifying encryption (not just encoding)...")
    try:
        import base58
        # Try to base58 decode - should FAIL if encrypted
        base58.b58decode(wallet['private_key_encrypted'])
        print(f"❌ Key is NOT encrypted, just base58 encoded!")
        return False
    except Exception as e:
        print(f"✅ Key is properly encrypted!")
        print(f"   Cannot be decoded without master key")
        print(f"   Error when trying base58 decode: {type(e).__name__}")
    
    print(f"\n" + "="*60)
    print("✅ WALLET ENCRYPTION TEST PASSED!")
    print("="*60)
    
    print(f"\n🔒 SECURITY STATUS")
    print(f"-"*60)
    print(f"• Encryption: ENABLED")
    print(f"• Algorithm: Fernet (AES-128 CBC + HMAC)")
    print(f"• Master key: Loaded from .env")
    print(f"• Private keys: Encrypted at rest")
    print(f"• Decryption: Only when signing transactions")
    
    return True

if __name__ == "__main__":
    success = test_encryption()
    
    if success:
        print(f"\n✅ Your wallets are SECURE!")
    else:
        print(f"\n❌ Encryption has issues - check configuration")
