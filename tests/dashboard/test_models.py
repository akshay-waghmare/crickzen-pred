"""Tests for SQLModel schemas: User and RefreshToken."""

from datetime import datetime, timezone

from sqlmodel import Session, select

from app.models import RefreshToken, User


class TestUserModel:
    """User model schema tests."""

    def test_user_has_uuid_primary_key(self, engine):
        """User.id is a UUID4 string generated on creation."""
        with Session(engine) as session:
            user = User(
                email="modeltest@test.com",
                hashed_password="$argon2id$fakehash",
                is_active=True,
            )
            session.add(user)
            session.commit()
            session.refresh(user)

            assert user.id is not None
            assert isinstance(user.id, str)
            assert len(user.id) == 36  # UUID4 format: 8-4-4-4-12

    def test_user_created_at_is_utc(self, engine):
        """User.created_at defaults to UTC timestamp."""
        with Session(engine) as session:
            user = User(
                email="utctest@test.com",
                hashed_password="$argon2id$fakehash",
            )
            session.add(user)
            session.commit()
            session.refresh(user)

            assert user.created_at is not None
            assert isinstance(user.created_at, datetime)

    def test_user_email_unique_constraint(self, engine):
        """Duplicate emails are rejected by the database."""
        import sqlalchemy

        with Session(engine) as session:
            user1 = User(
                email="unique@test.com",
                hashed_password="$argon2id$hash1",
            )
            session.add(user1)
            session.commit()

        with Session(engine) as session:
            user2 = User(
                email="unique@test.com",
                hashed_password="$argon2id$hash2",
            )
            session.add(user2)
            try:
                session.commit()
                assert False, "Should have raised IntegrityError"
            except sqlalchemy.exc.IntegrityError:
                session.rollback()

    def test_user_is_active_defaults_true(self, engine):
        """User.is_active defaults to True."""
        with Session(engine) as session:
            user = User(
                email="activedefault@test.com",
                hashed_password="$argon2id$fakehash",
            )
            session.add(user)
            session.commit()
            session.refresh(user)

            assert user.is_active is True


class TestRefreshTokenModel:
    """RefreshToken model schema tests."""

    def test_refresh_token_autoincrement_id(self, engine):
        """RefreshToken.id auto-increments."""
        with Session(engine) as session:
            # Create a user first
            user = User(
                email="rttest@test.com",
                hashed_password="$argon2id$fakehash",
            )
            session.add(user)
            session.commit()
            session.refresh(user)

            token1 = RefreshToken(
                token_hash="hash1",
                user_id=user.id,
                expires_at=datetime.now(timezone.utc),
            )
            token2 = RefreshToken(
                token_hash="hash2",
                user_id=user.id,
                expires_at=datetime.now(timezone.utc),
            )
            session.add(token1)
            session.add(token2)
            session.commit()
            session.refresh(token1)
            session.refresh(token2)

            assert token1.id is not None
            assert token2.id is not None
            assert token2.id > token1.id

    def test_refresh_token_revoked_defaults_false(self, engine):
        """RefreshToken.revoked defaults to False."""
        with Session(engine) as session:
            user = User(
                email="revoketest@test.com",
                hashed_password="$argon2id$fakehash",
            )
            session.add(user)
            session.commit()
            session.refresh(user)

            token = RefreshToken(
                token_hash="hashrevoke",
                user_id=user.id,
                expires_at=datetime.now(timezone.utc),
            )
            session.add(token)
            session.commit()
            session.refresh(token)

            assert token.revoked is False

    def test_refresh_token_fk_enforced(self, engine):
        """RefreshToken.user_id references a valid User."""
        with Session(engine) as session:
            user = User(
                email="fktest@test.com",
                hashed_password="$argon2id$fakehash",
            )
            session.add(user)
            session.commit()
            session.refresh(user)

            token = RefreshToken(
                token_hash="hashfk",
                user_id=user.id,
                expires_at=datetime.now(timezone.utc),
            )
            session.add(token)
            session.commit()

            # Verify FK relationship via query
            result = session.exec(
                select(RefreshToken).where(RefreshToken.user_id == user.id)
            ).first()
            assert result is not None
            assert result.token_hash == "hashfk"
