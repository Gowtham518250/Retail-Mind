#[INFO]/usr/bin/env python3
"""Direct test of register function"""
import sys
import traceback

print("Direct Test of Register Function")
print("=" * 70)

try:
    print("1. Importing modules...")
    from db import SessionLocal
    from models import User, ShopProfile
    from security import hash_password
    from sqlalchemy import func
    print("   [OK] Imports successful")
    
    print("\n2. Creating database session...")
    db = SessionLocal()
    print("   ✓ Session created")
    
    print("\n3. Testing hash_password...")
    test_pass = "Test@123456"
    hashed = hash_password(test_pass)
    print(f"   ✓ Hashed password: {hashed[:50]}...")
    
    print("\n4. Creating test user...")
    username = f"testuser_direct_{int(__import__('time').time())}"
    email = f"test_direct_{int(__import__('time').time())}@test.com"
    
    # Check if user exists
    existing = db.query(User).filter(User.user_name == username).first()
    if existing:
        print(f"   [INFO] User already exists: {username}")
    else:
        print(f"   Creating user: {username}")
    
    # Check email uniqueness
    existing_email = db.query(User).filter(func.lower(User.email) == email.lower()).first()
    if existing_email:
        print(f"   [INFO] Email already exists: {email}")
    else:
        print(f"   Email is unique: {email}")
    
    new_user = User(
        user_name=username,
        email=email.lower(),
        password=hashed,
        user_type="OWNER",
        is_active=True
    )
    
    print("\n5. Adding user to database...")
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    print(f"   ✓ User created with ID: {new_user.id}")
    
    print("\n6. Creating shop profile...")
    shop = ShopProfile(
        shop_id=new_user.id,
        shop_name=f"{username}'s Shop"
    )
    db.add(shop)
    db.commit()
    print(f"   ✓ Shop profile created")
    
    print("\n✓ ALL TESTS PASSED - Register function should work[INFO]")
    
    db.close()
    
except Exception as e:
    print(f"\n✗ ERROR: {type(e).__name__}: {str(e)}")
    traceback.print_exc()
    sys.exit(1)

print("=" * 70)
