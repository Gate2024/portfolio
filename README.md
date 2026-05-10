# 🚀 Narayan Adhude — Full Stack AI/ML Portfolio

A **production-ready, fully dynamic portfolio website** built with Python Flask, PostgreSQL, SQLAlchemy, and a premium Silicon Valley-style UI featuring glassmorphism, AOS animations, Particles.js, and Typed.js.

---

## ✨ Features

- 🎨 **Premium Light UI** — Glassmorphism, gradient accents, smooth AOS animations
- 🤖 **Dynamic Admin Dashboard** — Full CRUD for all content without touching code
- 🔒 **Secure Authentication** — Flask-Login with hashed passwords
- 📬 **Contact Form** — AJAX-powered with PostgreSQL storage
- 📱 **Fully Responsive** — Mobile, tablet, and desktop optimised
- ⚡ **Typed.js** hero animations + Particles.js background
- 🌐 **SEO Ready** — Meta tags, semantic HTML, clean URLs
- 🗄️ **PostgreSQL / SQLite** — Auto-seeds all default data on first run
- 🚀 **One-click deploy** on Render, Railway, PythonAnywhere, Replit

---

## 🗂️ Project Structure

```
portfolio/
├── app.py                  # Flask app, models, routes, seed data
├── requirements.txt
├── runtime.txt
├── Procfile
├── .env.example
├── .gitignore
├── README.md
│
├── static/
│   ├── css/style.css       # Premium stylesheet
│   ├── js/main.js          # Animations, filters, AJAX
│   ├── images/             # Static images
│   └── uploads/            # User-uploaded files (gitignored)
│
└── templates/
    ├── index.html          # Main portfolio page (all sections)
    ├── 404.html
    ├── 500.html
    ├── auth/
    │   └── login.html      # Admin login
    └── admin/
        ├── base.html       # Sidebar layout
        ├── dashboard.html
        ├── profile.html
        ├── projects.html
        ├── project_form.html
        ├── skills.html
        ├── certifications.html
        ├── achievements.html
        ├── experience.html
        ├── messages.html
        └── social.html
```

---

## ⚙️ Local Development Setup

### 1. Clone the Repository

```bash
git clone https://github.com/Gate2024/portfolio.git
cd portfolio
```

### 2. Create Virtual Environment

```bash
python -m venv venv

# Windows
venv\Scripts\activate

# macOS / Linux
source venv/bin/activate
```

### 3. Install Dependencies

```bash
pip install -r requirements.txt
```

### 4. Configure Environment Variables

```bash
cp .env.example .env
```

Edit `.env`:

```env
SECRET_KEY=your-very-secret-key-here
DATABASE_URL=sqlite:///portfolio.db        # SQLite for local dev
# DATABASE_URL=postgresql://user:pass@localhost:5432/portfolio_db  # PostgreSQL
ADMIN_USERNAME=admin
ADMIN_PASSWORD=yourpassword
ADMIN_EMAIL=your@email.com
FLASK_DEBUG=1
```

### 5. Run the Application

```bash
python app.py
```

Visit: **http://localhost:5000**
Admin: **http://localhost:5000/admin/login**

> The database is auto-created and seeded with all default data on first run.

---

## 🗄️ PostgreSQL Setup (Production)

```bash
# Install PostgreSQL and create database
psql -U postgres
CREATE DATABASE portfolio_db;
CREATE USER portfolio_user WITH PASSWORD 'strongpassword';
GRANT ALL PRIVILEGES ON DATABASE portfolio_db TO portfolio_user;
\q
```

Update `.env`:
```env
DATABASE_URL=postgresql://portfolio_user:strongpassword@localhost:5432/portfolio_db
```

---

## 🌐 Deployment

### ▶ Render (Recommended)

1. Push code to GitHub
2. Go to [render.com](https://render.com) → **New Web Service**
3. Connect your GitHub repo
4. Set:
   - **Build Command:** `pip install -r requirements.txt`
   - **Start Command:** `gunicorn app:app --bind 0.0.0.0:$PORT`
5. Add Environment Variables:
   ```
   SECRET_KEY         = your-secret-key
   DATABASE_URL       = (from Render PostgreSQL add-on)
   ADMIN_USERNAME     = admin
   ADMIN_PASSWORD     = yourpassword
   ADMIN_EMAIL        = your@email.com
   FLASK_DEBUG        = 0
   ```
6. Add a **PostgreSQL** database from Render dashboard and copy the URL

### ▶ Railway

1. Push to GitHub
2. New Project → Deploy from GitHub
3. Add PostgreSQL plugin → copy DATABASE_URL
4. Set all environment variables under **Variables**
5. Railway auto-detects `Procfile`

### ▶ PythonAnywhere

1. Upload files via **Files** tab
2. Create a new **Web App** → Manual config → Python 3.11
3. Set WSGI file to point to `app:app`
4. Install requirements in a **virtualenv**
5. Set environment variables in the WSGI file:
   ```python
   import os
   os.environ['SECRET_KEY'] = 'your-key'
   os.environ['DATABASE_URL'] = 'sqlite:////home/username/portfolio/portfolio.db'
   ```

### ▶ Replit

1. Import from GitHub
2. Set Secrets (Environment Variables) in sidebar
3. Click **Run** — Replit detects `app.py` automatically

---

## 🔐 Admin Dashboard

Access at: `/admin/login`

Default credentials (from `.env`):
- **Username:** `admin`
- **Password:** `admin123` *(change this!)*

### Admin Capabilities

| Section        | Actions                          |
|----------------|----------------------------------|
| Profile        | Edit name, bio, photo, resume    |
| Projects       | Add / Edit / Delete + image upload |
| Skills         | Add / Edit / Delete + proficiency |
| Experience     | Add / Delete work history        |
| Certifications | Add / Delete credentials         |
| Achievements   | Add / Delete milestones          |
| Social Links   | Add / Delete platform links      |
| Messages       | View / Delete contact messages   |

---

## 🎨 Customisation

### Update Owner Details
All default data is seeded in `seed_data()` inside `app.py`. Edit that function before first run, or update everything through the **Admin Dashboard** after deployment.

### Change Colour Theme
Edit CSS variables at the top of `static/css/style.css`:
```css
:root {
  --primary:   #4F46E5;  /* Main brand colour */
  --secondary: #0EA5E9;  /* Accent blue        */
  --purple:    #7C3AED;  /* Gradient end       */
  --accent:    #06B6D4;  /* Cyan accent        */
}
```

### Add Typed.js Roles
Edit the strings array in `static/js/main.js`:
```js
strings: [
  'AI/ML Engineer',
  'Full Stack Developer',
  'Your Custom Role',
],
```

---

## 📦 Tech Stack

| Layer       | Technology                                      |
|-------------|-------------------------------------------------|
| Backend     | Python 3.11, Flask 3.0, SQLAlchemy 2.0          |
| Database    | PostgreSQL (prod) / SQLite (dev)                |
| Auth        | Flask-Login, Werkzeug password hashing          |
| Frontend    | HTML5, CSS3, Bootstrap 5, Tailwind CSS (utils)  |
| Animations  | AOS 2.3, Typed.js 2.1, Particles.js 2.0        |
| Icons       | FontAwesome 6.5                                 |
| Fonts       | Syne + DM Sans (Google Fonts)                   |
| Deploy      | Gunicorn, Render / Railway / PythonAnywhere     |

---

## 🛠️ Common Issues & Fixes

**`ModuleNotFoundError`**
```bash
pip install -r requirements.txt
```

**`SQLALCHEMY_DATABASE_URI` error**
Ensure `.env` is present or environment variables are set.

**`postgres://` URI error on Render**
Already handled in `app.py`:
```python
.replace('postgres://', 'postgresql://')
```

**Static files not loading**
Ensure `static/` folder exists and Flask `url_for('static', ...)` is used.

**Admin password forgotten**
Delete the admin user record from DB and restart — `seed_data()` will recreate it from `.env`.

---

## 📄 License

MIT License — Free to use and modify for personal portfolios.

---

## 👤 Author

**Narayan Kishor Adhude**
- 📧 narayanadhude2004@gmail.com
- 🔗 [LinkedIn](http://www.linkedin.com/in/narayan-adhude-🎯-5b14081bb)
- 💻 [GitHub](https://github.com/Gate2024)

---

> Built with ❤️ using Flask, PostgreSQL, and a passion for clean, elegant engineering.
