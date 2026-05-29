# Anveshak — User & Organization Onboarding Guide

This guide walks through setting up Anveshak for a new deployment: creating organizations, users, and assigning roles.

---

## Role Hierarchy

| Role | Scope | Can Do |
|------|-------|--------|
| **Super-Admin** | Platform-wide | Create/manage organizations, create users in any org, see all data |
| **Admin** | Within their org | Create/manage users in their org, full read/write on org data |
| **Analyst** | Within their org | Create topics, sources, generate reports, acknowledge signals |
| **Viewer** | Within their org | Read-only access to topics, content, signals, reports |

**Data isolation:** Users in one organization cannot see another organization's topics, sources, content, signals, or reports.

---

## Step 1 — First Login (Super-Admin)

After a fresh deployment with `make seed-demo`, a default super-admin account exists:

| Field | Value |
|-------|-------|
| URL | `http://localhost:3000` |
| Username | `superadmin@anveshak.local` |
| Password | `AnveshakSuper2024!` |

Log in with these credentials. Change the password after first login.

> **Note:** The default deployment also creates a demo analyst account (`demo@anveshak.local` / `AnveshakDemo2024!`) and an admin account (`admin@anveshak.local` / `AnveshakAdmin2024!`), both assigned to the default "Anshul" organization.

---

## Step 2 — Create an Organization

1. Log in as **super-admin**
2. Go to **Settings** (bottom-left sidebar)
3. Click the **Organizations** tab
4. Click **Create Organization**
5. Enter the organization name (e.g., "National Investigation Agency")
6. Click **Create**

The slug (URL-safe identifier) is auto-generated from the name.

Repeat for each LEA or agency that needs a separate data environment.

---

## Step 3 — Create an Admin for the Organization

1. Stay logged in as **super-admin**
2. Go to **Settings → Users** tab
3. Click **Create User**
4. Fill in:
   - **Organization**: Select the org you just created (dropdown at top)
   - **Username**: e.g., `admin@nia.anveshak.local`
   - **Password**: Strong password (share securely with the org admin)
   - **Role**: `Admin`
5. Click **Create**

This org admin can now log in and manage their own organization's users.

---

## Step 4 — Org Admin Creates Analysts

1. The **org admin** logs in with their credentials
2. Goes to **Settings → Users**
3. Clicks **Create User**
4. Creates analyst and viewer accounts for their team:
   - **Username**: e.g., `analyst1@nia.anveshak.local`
   - **Password**: Share securely
   - **Role**: `Analyst` or `Viewer`

> Org admins can only create users within their own organization. They cannot see or manage users from other organizations.

---

## Step 5 — Analysts Start Working

Once an analyst logs in, they can:

1. **Create Topics** — Define OSINT monitoring areas (e.g., "Cross-border Terror Financing")
2. **Add Sources** — Register web, RSS, Telegram, Reddit sources for each topic
3. **Monitor Signals** — Threshold-based alerts when narrative clusters form
4. **Generate Reports** — AI-generated intelligence briefs from collected content
5. **Analyse Media** — Deepfake detection, object recognition, EXIF analysis

All data created by analysts in one org is invisible to other orgs.

---

## Step 6 — (Optional) Seed Demo Data via SQL

For demo environments, you can seed topics, sources, and content for a specific org using the template script:

```bash
# Copy the template
cp scripts/seed_lea_template.sql scripts/seed_nia.sql

# Edit the file — replace placeholders:
#   __ORG_ID__     → org ID from the Organizations table
#   __ORG_NAME__   → e.g., "National Investigation Agency"
#   __ORG_SLUG__   → e.g., "nia"
#   __USER_ID__    → generate with: python -c "import uuid; print(uuid.uuid4())"
#   __USERNAME__   → e.g., "demo@nia.anveshak.local"
#   __PASSWORD__   → generate hash: uv run python -c "import bcrypt; print(bcrypt.hashpw(b'YourPassword!', bcrypt.gensalt(12)).decode())"

# Run the seed
psql -U anveshak -d anveshak < scripts/seed_nia.sql
```

> **Tip:** To find an org's ID, query the database:
> ```sql
> SELECT id, name FROM organizations;
> ```
> Or check the Organizations tab in Settings (super-admin).

---

## Quick Reference

### Default Accounts (after `make seed-demo`)

| Username | Password | Role | Org |
|----------|----------|------|-----|
| `superadmin@anveshak.local` | `AnveshakSuper2024!` | Super-Admin | None (platform-wide) |
| `admin@anveshak.local` | `AnveshakAdmin2024!` | Admin | Anshul |
| `demo@anveshak.local` | `AnveshakDemo2024!` | Analyst | Anshul |

### Settings Tab Visibility

| Tab | Viewer | Analyst | Admin | Super-Admin |
|-----|:---:|:---:|:---:|:---:|
| Sources | Yes | Yes | Yes | Yes |
| Users | - | - | Yes | Yes |
| Organizations | - | - | - | Yes |
| Audit Trail | Yes | Yes | Yes | Yes |

### Common Workflows

**"I need to demo Anveshak to a new LEA agency"**
1. Super-admin creates the org
2. Super-admin creates an admin user for that org
3. Org admin creates analyst accounts
4. (Optional) Seed demo data with the SQL template

**"An analyst left the team"**
1. Org admin logs in → Settings → Users → Delete the user

**"I need to give a read-only view to a stakeholder"**
1. Org admin creates a Viewer account for them

**"I need to see all orgs' data for debugging"**
1. Log in as super-admin — all data is visible across all orgs
