# bcrypt Hash Shell Escaping

## Confidence: HIGH (auth broken silently in production 2026-06-29)

bcrypt hashes contain `$` characters: `$2b$12$salt...hash...`
Bash interprets `$` as variable expansion. Inserting via shell corrupts the hash silently.
Password verification then fails — "Invalid username or password" with no error log.

## The Trap

```bash
# BROKEN — $ gets expanded by bash
psql -c "INSERT INTO users ... VALUES ('$2b$12$abc...')"
# Becomes: INSERT INTO users ... VALUES ('2babc...')

# ALSO BROKEN — ! triggers bash history expansion in double quotes
python -c "bcrypt.hashpw(b'Password123!', ...)"
# bash: !',: event not found
```

## Fix

Generate hash INSIDE the container, then update via psql:

```bash
# Step 1: Generate hash inside API container (single quotes!)
docker exec anveshak-api-1 python -c 'import bcrypt;print(bcrypt.hashpw(b"MyPassword123!",bcrypt.gensalt(12)).decode())'

# Step 2: Copy output, update via psql (escape $ with \$)
docker exec anveshak-postgres-1 psql -U anveshak -d anveshak -c \
  "UPDATE users SET password_hash = '\$2b\$12\$THE_FULL_HASH' WHERE username = 'admin';"
```

## Rules

1. Generate bcrypt hashes inside Docker container, never on host shell
2. Use single quotes around Python string containing `!` — prevents bash history expansion
3. When inserting hash via psql, escape every `$` with `\$`
4. Never pass passwords/hashes through environment variables in docker run commands
