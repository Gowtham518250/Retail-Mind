import os
import uuid

os.environ.setdefault(
    "DATABASE_URL",
    "postgresql://postgres:postgres@localhost:5432/retail_mind_test",
)
os.environ.setdefault(
    "SECRET_KEY",
    "owner-otp-attempt-test-secret-key-1234567890",
)

from db import Base, engine, sessionLocal
from models import PasswordReset, User
from security import hash_password
from auth_routes import (
    OWNER_VERIFICATION_OTP_PURPOSE,
    _find_db_otp,
    _store_db_otp,
)

Base.metadata.create_all(bind=engine)


def test_owner_otp_wrong_attempts_are_persisted_and_bounded():
    email = f"owner-otp-{uuid.uuid4().hex}@example.com"
    db = sessionLocal()
    user = User(
        user_name="OTP Attempt Test",
        email=email,
        password=hash_password("TestPassword123!"),
        user_type="OWNER",
        is_active=True,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    user_id = user.id

    try:
        _store_db_otp(
            db,
            user_id=user_id,
            otp="123456",
            purpose=OWNER_VERIFICATION_OTP_PURPOSE,
        )
        db.commit()

        for attempt in range(1, 6):
            assert _find_db_otp(
                db,
                user_id=user_id,
                otp="999999",
                purpose=OWNER_VERIFICATION_OTP_PURPOSE,
            ) is None
            remaining = db.query(PasswordReset).filter(
                PasswordReset.user_id == user_id,
                PasswordReset.description == OWNER_VERIFICATION_OTP_PURPOSE,
            ).first()
            if attempt < 5:
                assert remaining is not None
                assert remaining.attempts == attempt
            else:
                assert remaining is None
    finally:
        db.query(PasswordReset).filter(PasswordReset.user_id == user_id).delete(
            synchronize_session=False
        )
        db.query(User).filter(User.id == user_id).delete(synchronize_session=False)
        db.commit()
        db.close()
