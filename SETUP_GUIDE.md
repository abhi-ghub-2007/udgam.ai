# UDGAM.ai - Setup & Running Guide

## Project Overview
UDGAM.ai is a direct farmer-to-buyer agricultural marketplace built with:
- **Frontend**: Vanilla JavaScript (no frameworks)
- **Backend**: FastAPI (Python)
- **Database**: Supabase (PostgreSQL + Auth)
- **Authentication**: Supabase Auth (browser-based) + FastAPI JWT

---

## Prerequisites

### System Requirements
- Python 3.11+
- Node.js 16+ (optional, only if using build tools)
- Git
- Bash/Shell

### For Development
- Text editor or IDE (VS Code recommended)
- Supabase account (free tier available at supabase.com)
- PostgreSQL knowledge (optional)

---

## Backend Setup

### 1. Clone and Navigate
```bash
cd udagm.ai
cd backend
```

### 2. Create Virtual Environment
```bash
# Linux/Mac
python3 -m venv .venv
source .venv/bin/activate

# Windows
python -m venv .venv
.\.venv\Scripts\activate
```

### 3. Install Dependencies
```bash
pip install --upgrade pip
pip install -r requirements.txt
```

### 4. Configure Environment
Create `.env` file in the backend root:
```env
# Supabase Configuration
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_ANON_KEY=your_anon_key_here
SUPABASE_SERVICE_ROLE_KEY=your_service_role_key_here

# Optional: External Integrations
AGMARKNET_API_KEY=your_api_key
OPENWEATHERMAP_API_KEY=your_api_key
OSRM_BASE_URL=http://localhost:5000
RAZORPAY_KEY_ID=your_key
RAZORPAY_KEY_SECRET=your_secret

# App Configuration
APP_ENV=development
CORS_ORIGINS=http://localhost:3000,http://127.0.0.1:8000,http://localhost:8000

# Optional: Development
LOG_LEVEL=INFO
USE_MOCK_INTEGRATIONS=true
```

### 5. Initialize Database
```bash
# Apply schema
python scripts/apply_schema.py

# Optional: Seed demo data
python scripts/seed_demo.py
```

### 6. Run Backend Server
```bash
# Development with auto-reload
python -m uvicorn backend.app.main:app --reload --port 8001 --host 0.0.0.0

# Production (without --reload)
python -m uvicorn backend.app.main:app --port 8000 --host 0.0.0.0
```

Server will be available at: `http://localhost:8001`
API docs at: `http://localhost:8001/docs`

---

## Frontend Setup

### 1. Navigate to Frontend
```bash
cd frontend
```

### 2. Configure API Base URL
Edit `index.html` or set environment variable:
```html
<script>
  window.__UDGAM_API_BASE__ = 'http://127.0.0.1:8001';
</script>
```

Or in JavaScript:
```javascript
// frontend/js/app.js
const API_BASE = window.__UDGAM_API_BASE__ || 'http://127.0.0.1:8001';
```

### 3. Serve Frontend
Option 1: Using Python's built-in server
```bash
cd frontend
python -m http.server 3000
```

Option 2: Using Node.js http-server
```bash
npx http-server frontend -p 3000
```

Option 3: Using Live Server (VS Code extension)
- Install "Live Server" extension
- Right-click `index.html` → "Open with Live Server"

Frontend will be available at: `http://localhost:3000`

---

## Supabase Setup

### 1. Create Supabase Project
1. Visit https://supabase.com
2. Click "New Project"
3. Choose region close to your users
4. Wait for database initialization

### 2. Configure Authentication
1. Go to Authentication → Providers
2. Enable Email/Password provider
3. Configure redirect URLs in Settings:
   ```
   http://localhost:3000
   http://localhost:3000/
   http://127.0.0.1:3000
   ```

### 3. Get API Keys
1. Go to Settings → API
2. Copy:
   - `anon` (public) key → `SUPABASE_ANON_KEY`
   - `service_role` (secret) key → `SUPABASE_SERVICE_ROLE_KEY`
3. Copy project URL → `SUPABASE_URL`

### 4. Create Database Tables
Option 1: Using Supabase SQL Editor
```sql
-- Paste contents of db/SCHEMA.sql into SQL Editor
-- Click "Run"
```

Option 2: Using Python script
```bash
python scripts/apply_schema.py
```

---

## Complete Startup Sequence

### Terminal 1 - Backend
```bash
cd backend
source .venv/bin/activate  # Linux/Mac
# or: .\.venv\Scripts\activate  (Windows)
python -m uvicorn backend.app.main:app --reload --port 8001
```

### Terminal 2 - Frontend
```bash
cd frontend
python -m http.server 3000
# or: npx http-server . -p 3000
```

### Terminal 3 (Optional) - Database Migrations
```bash
cd backend
python scripts/apply_schema.py
```

### Open Browser
```
http://localhost:3000
```

---

## Testing Authentication

### 1. Sign Up (Create Account)
```
1. Navigate to /#/signup
2. Select role: Farmer/Buyer/Transporter
3. Fill in details:
   - Full Name: John Farmer
   - Email: john@example.com
   - Password: SecurePass123!
   - Phone: 9876543210 (optional)
   - District: Pune (optional)
   - Pincode: 411001 (optional, 6 digits)
4. Click "Create Account"
5. Should redirect to dashboard
```

### 2. Sign In (Login)
```
1. Navigate to /#/login
2. Enter email: john@example.com
3. Enter password: SecurePass123!
4. Click "Sign In"
5. Should redirect to dashboard
```

### 3. Sign Out (Logout)
```
1. Click "Sign Out" button (sidebar)
2. Should redirect to login page
3. Session should be cleared
```

### 4. Test Error Handling
```
# Invalid Email
- Email: "notanemail"
- Error: "Please enter a valid email address"

# Short Password
- Password: "abc123"
- Error: "Password must be at least 8 characters"

# Wrong Credentials
- Email: john@example.com
- Password: WrongPassword
- Error: "Email or password is incorrect"
```

---

## Verification Checklist

### Backend
- [ ] Backend starts without errors
- [ ] `GET /api/config` returns Supabase config
- [ ] `GET /api/health` returns status
- [ ] Database connection successful
- [ ] CORS headers present in responses

### Frontend
- [ ] Frontend loads without 404 errors
- [ ] Supabase JS client initializes
- [ ] Can access login page
- [ ] Can access signup page
- [ ] Navigation works

### Authentication
- [ ] Can create new account (signup)
- [ ] Can login with valid credentials
- [ ] Cannot login with invalid credentials
- [ ] Can logout successfully
- [ ] Session persists on page reload
- [ ] Protected pages redirect to login
- [ ] Profile loads after login

### Database
- [ ] `profiles` table exists and populated
- [ ] `farmer_profiles` table exists (for farmers)
- [ ] `buyer_profiles` table exists (for buyers)
- [ ] `transporter_profiles` table exists (for transporters)
- [ ] Tables have correct relationships

---

## Troubleshooting

### Backend Issues

#### "ModuleNotFoundError: No module named 'fastapi'"
```bash
# Reinstall dependencies
pip install --upgrade pip
pip install -r requirements.txt
```

#### "Supabase connection failed"
```
✓ Check SUPABASE_URL is correct (should be https://...)
✓ Check SUPABASE_SERVICE_ROLE_KEY is valid
✓ Check internet connection
✓ Check firewall/proxy settings
```

#### "CORS error when frontend calls backend"
```
✓ Verify CORS_ORIGINS in .env includes frontend URL
✓ Restart backend after changing CORS settings
✓ Check that backend is running on correct port
```

#### "Port 8001 already in use"
```bash
# Find process using port
lsof -i :8001  # Linux/Mac
netstat -ano | findstr :8001  # Windows

# Kill process
kill -9 <PID>  # Linux/Mac
taskkill /PID <PID> /F  # Windows

# Or use different port
python -m uvicorn backend.app.main:app --reload --port 8002
```

### Frontend Issues

#### "Cannot reach the UDGAM API"
```
✓ Verify backend is running (http://localhost:8001)
✓ Check API_BASE URL is correct
✓ Check browser console for detailed error
✓ Try accessing http://localhost:8001/api/config in browser
```

#### "Blank page or 404"
```
✓ Check you're accessing http://localhost:3000
✓ Verify frontend files exist in ./frontend/
✓ Check browser console for JavaScript errors
✓ Try hard refresh (Ctrl+Shift+R or Cmd+Shift+R)
```

#### "Supabase Auth is not initialized"
```
✓ Check that /api/config returns Supabase config
✓ Wait for page to load completely
✓ Check browser console for initialization errors
```

### Authentication Issues

#### "Always redirected to login"
```
✓ Check profile was created (backend logs)
✓ Check Supabase session is valid
✓ Check localStorage for session data
✓ Try signing up again
```

#### "Cannot signup - email already exists"
```
✓ Use a different email address
✓ Or check Supabase for existing user
✓ Delete user from Supabase if test account
```

#### "Password validation failing"
```
✓ Password must be minimum 8 characters
✓ Check for spaces (password is trimmed)
✓ Try without special characters first
```

#### "Session not persisting on page reload"
```
✓ Check browser allows localStorage
✓ Check browser is not in private/incognito mode
✓ Check localStorage in DevTools → Application
✓ Verify session stored as 'sb-<project>-auth-token'
```

---

## Development Workflow

### Making Changes

1. **Backend Changes**
   - Edit Python files
   - Backend auto-reloads (with `--reload` flag)
   - Test with http://localhost:8001/docs

2. **Frontend Changes**
   - Edit JavaScript files
   - Refresh browser (browser auto-reloads with Live Server)
   - Check browser console for errors

3. **Database Changes**
   - Edit db/SCHEMA.sql
   - Run `python scripts/apply_schema.py`
   - Verify tables in Supabase UI

### Testing Authentication Locally

1. **Test Sign-Up**
```bash
# 1. Sign up with test account
# 2. Verify profile created in Supabase
# 3. Check logs for any errors
```

2. **Test Sign-In**
```bash
# 1. Sign in with created account
# 2. Check session stored
# 3. Verify redirect to dashboard
```

3. **Test Sign-Out**
```bash
# 1. Click Sign Out
# 2. Verify session cleared
# 3. Verify redirect to login
```

---

## Project Structure

```
udgam.ai/
├── frontend/
│   ├── index.html           # Entry point
│   ├── css/                 # Stylesheets
│   ├── js/
│   │   ├── app.js          # Main bootstrap
│   │   ├── core/           # Core modules
│   │   │   ├── supabase.js # Auth setup
│   │   │   ├── api.js      # API wrapper
│   │   │   ├── store.js    # State management
│   │   │   └── ...
│   │   ├── views/          # Page components
│   │   │   ├── login.js    # Login form
│   │   │   ├── signup.js   # Signup form
│   │   │   └── ...
│   │   └── routes.js       # Route definitions
│   ├── i18n/               # Translations
│   │   ├── en.json         # English
│   │   ├── hi.json         # Hindi
│   │   └── mr.json         # Marathi
│   └── assets/             # Images, logos
│
├── backend/
│   ├── app/
│   │   ├── main.py         # FastAPI app
│   │   ├── config.py       # Configuration
│   │   ├── deps.py         # Dependencies
│   │   ├── routers/        # API routes
│   │   │   ├── auth.py     # Auth endpoints
│   │   │   └── ...
│   │   ├── db/             # Database
│   │   └── services/       # Business logic
│   ├── requirements.txt    # Python dependencies
│   └── .env               # Environment variables
│
├── db/
│   └── SCHEMA.sql         # Database schema
│
├── docs/                  # Documentation
├── scripts/               # Setup scripts
└── README.md             # Project README
```

---

## Environment Variables Reference

### Backend (.env)

| Variable | Required | Example | Notes |
|----------|----------|---------|-------|
| `SUPABASE_URL` | Yes | `https://xxx.supabase.co` | Project URL from Supabase |
| `SUPABASE_ANON_KEY` | Yes | `eyJ0...` | Public anonymous key |
| `SUPABASE_SERVICE_ROLE_KEY` | Yes | `eyJ0...` | Secret server key, never expose |
| `APP_ENV` | No | `development` | `development` or `production` |
| `CORS_ORIGINS` | No | `http://localhost:3000` | Comma-separated allowed origins |
| `AGMARKNET_API_KEY` | No | `key...` | For agriculture market data |
| `OPENWEATHERMAP_API_KEY` | No | `key...` | For weather data |
| `OSRM_BASE_URL` | No | `http://localhost:5000` | For routing/maps |
| `RAZORPAY_KEY_ID` | No | `key...` | For payments |
| `USE_MOCK_INTEGRATIONS` | No | `true` | Use mock data instead of real APIs |

---

## Performance Optimization

### Frontend
- CSS bundled and minified
- JavaScript modular and tree-shakeable
- No framework overhead
- Light i18n system
- Efficient DOM updates

### Backend
- Async/await with FastAPI
- Connection pooling to Supabase
- Proper indexing on database
- CORS middleware for efficiency
- Error handling and logging

### Database
- Proper foreign keys
- Indexes on common queries
- Denormalization where needed
- Partitioning for large tables (future)

---

## Deployment Notes

### Before Deploying

1. **Update Environment**
   - [ ] Set `APP_ENV=production`
   - [ ] Update Supabase redirect URLs
   - [ ] Update CORS origins
   - [ ] Remove mock integrations

2. **Security**
   - [ ] Verify SERVICE_ROLE_KEY is never in frontend code
   - [ ] Enable HTTPS everywhere
   - [ ] Set secure cookies
   - [ ] Enable rate limiting

3. **Testing**
   - [ ] Full auth flow works
   - [ ] All error messages appear
   - [ ] Translations work in all languages
   - [ ] No console errors

4. **Monitoring**
   - [ ] Setup error logging
   - [ ] Monitor API performance
   - [ ] Watch for auth failures
   - [ ] Check database connections

---

## Support & Documentation

### Additional Resources
- Supabase Docs: https://supabase.com/docs
- FastAPI Docs: https://fastapi.tiangolo.com
- Auth Architecture: See `AUTH_FIXES.md`
- API Contract: See `docs/API_CONTRACT.md`
- Database Schema: See `db/SCHEMA.sql`

### Getting Help
1. Check browser console for errors
2. Check backend server logs
3. Verify Supabase connectivity
4. Review `AUTH_FIXES.md` troubleshooting section
5. Check API health: `GET /api/health`

---

## Quick Command Reference

```bash
# Backend
cd backend
source .venv/bin/activate                    # Activate venv
pip install -r requirements.txt              # Install deps
python scripts/apply_schema.py               # Setup database
python -m uvicorn backend.app.main:app --reload --port 8001  # Run server

# Frontend
cd frontend
python -m http.server 3000                   # Serve locally
# or: npx http-server . -p 3000

# Database
python scripts/apply_schema.py               # Apply schema
python scripts/seed_demo.py                  # Seed data

# Testing
# Navigate to: http://localhost:3000
# API Docs: http://localhost:8001/docs
# Health Check: http://localhost:8001/api/health
```

---

## Congratulations! 🎉

Your UDGAM.ai instance is now running. Happy coding!
