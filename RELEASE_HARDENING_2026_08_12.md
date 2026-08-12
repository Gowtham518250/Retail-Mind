# Retail Mind Release Hardening — 2026-08-12

This branch is intended for production hardening before the August release.

Goals:
- never permanently park unsynced offline transactions
- recover transactions parked by older app versions
- ensure Khata payment idempotency exists in the database schema
- keep sale/invoice retries safe under timeouts and duplicate delivery

Required validation before merging to `main`:
- `flutter analyze`
- `flutter test`
- `flutter build apk --split-per-abi`
- backend test suite
- `alembic upgrade head` on staging
- offline sale -> kill app -> reopen -> reconnect -> verify one backend invoice and exact inventory
- offline Khata payment -> retry -> verify one Payment row
