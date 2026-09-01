import os
import json
import re
import time
from contextlib import contextmanager
from datetime import datetime
from functools import wraps
from urllib.parse import urlparse
from flask import (Flask, render_template, request, redirect,
                   url_for, flash, jsonify, session, send_from_directory)
from flask_sqlalchemy import SQLAlchemy
from flask_wtf.csrf import CSRFError, CSRFProtect
from flask_login import (LoginManager, UserMixin, login_user,
                         logout_user, login_required, current_user)
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from dotenv import load_dotenv
from PIL import Image
from sqlalchemy import text
from supabase import create_client

load_dotenv()

app = Flask(__name__)

# ─── Configuration ───────────────────────────────────────────────────────────
APP_ENV = os.environ.get('FLASK_ENV', 'development').lower()
IS_PRODUCTION = APP_ENV == 'production'
secret_key = os.environ.get('SECRET_KEY', '').strip()
if IS_PRODUCTION and (
    not secret_key
    or secret_key == 'your-super-secret-key-change-this-in-production'
    or secret_key.startswith('replace-with-')
):
    raise RuntimeError('SECRET_KEY must be explicitly configured for production.')
app.config['SECRET_KEY'] = secret_key or 'dev-secret-change-me'
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get(
    'DATABASE_URL', 'sqlite:///portfolio.db'
).replace('postgres://', 'postgresql://')  # Fix Render's postgres:// URI
app.config['SQLALCHEMY_ENGINE_OPTIONS'] = {
    'pool_pre_ping': True,
}
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16 MB
app.config['SESSION_COOKIE_HTTPONLY'] = True
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'
app.config['SESSION_COOKIE_SECURE'] = IS_PRODUCTION

_SUPABASE_URL = os.environ.get('SUPABASE_URL', '').strip().rstrip('/')
_SUPABASE_STORAGE_BUCKET = os.environ.get('SUPABASE_STORAGE_BUCKET', '').strip()
_SUPABASE_SECRET_KEY = (
    os.environ.get('SUPABASE_SECRET_KEY', '').strip()
    or os.environ.get('SUPABASE_SERVICE_ROLE_KEY', '').strip()
)
if IS_PRODUCTION and (
    not _SUPABASE_URL
    or not _SUPABASE_STORAGE_BUCKET
    or not _SUPABASE_SECRET_KEY
):
    raise RuntimeError(
        'SUPABASE_URL, SUPABASE_STORAGE_BUCKET, and '
        'SUPABASE_SECRET_KEY (or SUPABASE_SERVICE_ROLE_KEY) '
        'must be explicitly configured for production.'
    )

_supabase_client = None

ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'webp', 'pdf', 'svg'}
ALLOWED_IMAGE_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'webp'}
MAX_IMAGE_SIZE = 5 * 1024 * 1024  # 5 MB per profile/project image
IMAGE_SUBFOLDERS = {'profile', 'projects'}
IMAGE_FORMAT_EXTENSIONS = {
    'PNG': {'png'},
    'JPEG': {'jpg', 'jpeg'},
    'GIF': {'gif'},
    'WEBP': {'webp'},
}
IMAGE_MIME_TYPES = {
    'png': 'image/png',
    'jpg': 'image/jpeg',
    'jpeg': 'image/jpeg',
    'gif': 'image/gif',
    'webp': 'image/webp',
}

db = SQLAlchemy(app)
csrf = CSRFProtect(app)
login_manager = LoginManager(app)
login_manager.login_view = 'admin_login'
login_manager.login_message_category = 'info'


def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


def parse_integer_field(value, label, default=None, min_value=None, max_value=None):
    raw_value = '' if value is None else str(value).strip()
    if not raw_value:
        return default, None
    try:
        parsed_value = int(raw_value)
    except (TypeError, ValueError):
        return default, f'{label} must be a valid integer.'
    if min_value is not None and parsed_value < min_value:
        return default, f'{label} must be at least {min_value}.'
    if max_value is not None and parsed_value > max_value:
        return default, f'{label} must be at most {max_value}.'
    return parsed_value, None


def parse_order_field(value, default=None):
    return parse_integer_field(value, 'Display order', default, min_value=0)


def validate_field_lengths(fields):
    for label, value, max_length in fields:
        if value is not None and len(str(value)) > max_length:
            return f'{label} must be {max_length} characters or fewer.'
    return None


def validate_http_url(value, label, max_length=500):
    raw_value = '' if value is None else str(value)
    length_error = validate_field_lengths(((label, raw_value, max_length),))
    if length_error:
        return raw_value, length_error
    candidate = raw_value.strip()
    if not candidate:
        return raw_value, None
    parsed_url = urlparse(candidate)
    if parsed_url.scheme.lower() not in ('http', 'https') or not parsed_url.netloc:
        return raw_value, f'{label} must be a valid HTTP or HTTPS URL.'
    return raw_value, None


def _storage_is_configured():
    return bool(
        _SUPABASE_URL
        and _SUPABASE_STORAGE_BUCKET
        and _SUPABASE_SECRET_KEY
    )


def get_supabase_client():
    """Return one server-side Supabase client per application process."""
    global _supabase_client
    if _supabase_client is None:
        if not _storage_is_configured():
            raise RuntimeError(
                'Supabase Storage is not configured. Set SUPABASE_URL, '
                'SUPABASE_STORAGE_BUCKET, and SUPABASE_SECRET_KEY '
                '(or SUPABASE_SERVICE_ROLE_KEY).'
            )
        _supabase_client = create_client(_SUPABASE_URL, _SUPABASE_SECRET_KEY)
    return _supabase_client


def _storage_object_path(relative_path, expected_subfolder=None):
    """Convert one database path into a safe Storage object path."""
    if not isinstance(relative_path, str) or not relative_path:
        return None
    if '\\' in relative_path:
        return None

    parts = relative_path.split('/')
    if len(parts) != 3 or parts[0] != 'uploads':
        return None
    subfolder, filename = parts[1], parts[2]
    if subfolder not in IMAGE_SUBFOLDERS:
        return None
    if expected_subfolder and subfolder != expected_subfolder:
        return None
    if (
        not filename
        or filename in {'.', '..'}
        or secure_filename(filename) != filename
    ):
        return None
    return f'{subfolder}/{filename}'


def storage_image_url(relative_path):
    """Build a public Storage URL from a database-compatible image path."""
    object_path = _storage_object_path(relative_path)
    if not object_path or not _storage_is_configured():
        return None
    try:
        return get_supabase_client().storage.from_(_SUPABASE_STORAGE_BUCKET).get_public_url(
            object_path
        )
    except Exception:
        app.logger.warning('Could not build the Supabase Storage image URL.')
        return None


app.jinja_env.globals['storage_image_url'] = storage_image_url


def remove_uploaded_file(relative_path, subfolder):
    """Remove only a profile/projects object from Supabase Storage."""
    object_path = _storage_object_path(relative_path, subfolder)
    if not object_path or not _storage_is_configured():
        return False
    try:
        get_supabase_client().storage.from_(_SUPABASE_STORAGE_BUCKET).remove(
            [object_path]
        )
        return True
    except Exception:
        app.logger.warning('Could not remove the Supabase Storage image.')
        return False


def save_image_file(file, subfolder=''):
    """Validate and upload a portfolio image, returning (database path, error)."""
    if not file or not file.filename:
        return None, 'Please select an image file.'
    if subfolder not in IMAGE_SUBFOLDERS:
        return None, 'The image destination is not configured.'

    filename = secure_filename(file.filename)
    if not filename or '.' not in filename:
        return None, 'Please upload a PNG, JPG, JPEG, GIF, or WEBP image.'
    extension = filename.rsplit('.', 1)[1].lower()
    if extension not in ALLOWED_IMAGE_EXTENSIONS:
        return None, 'Only PNG, JPG, JPEG, GIF, and WEBP images are allowed.'

    try:
        file.stream.seek(0, os.SEEK_END)
        file_size = file.stream.tell()
        file.stream.seek(0)
    except (OSError, ValueError):
        return None, 'The uploaded image could not be read.'
    if file_size > MAX_IMAGE_SIZE:
        return None, 'Image files must be 5 MB or smaller.'

    try:
        with Image.open(file.stream) as image:
            image.verify()
            image_format = (image.format or '').upper()
    except Exception:
        file.stream.seek(0)
        return None, 'The uploaded file is not a valid image.'
    finally:
        file.stream.seek(0)

    if extension not in IMAGE_FORMAT_EXTENSIONS.get(image_format, set()):
        return None, 'The file extension does not match the actual image format.'

    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S_')
    filename = timestamp + filename
    object_path = f'{subfolder}/{filename}'
    relative_path = f'uploads/{object_path}'
    try:
        file.stream.seek(0)
        image_data = file.stream.read()
        get_supabase_client().storage.from_(_SUPABASE_STORAGE_BUCKET).upload(
            path=object_path,
            file=image_data,
            file_options={
                'cache-control': '3600',
                'upsert': 'false',
                'content-type': IMAGE_MIME_TYPES[extension],
            },
        )
    except RuntimeError as error:
        return None, str(error)
    except Exception:
        return None, 'The image could not be uploaded. Please try again.'
    return relative_path, None


# ─── Models ──────────────────────────────────────────────────────────────────

class AdminUser(UserMixin, db.Model):
    __tablename__ = 'admin_users'
    id            = db.Column(db.Integer, primary_key=True)
    username      = db.Column(db.String(80), unique=True, nullable=False)
    email         = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(256), nullable=False)
    created_at    = db.Column(db.DateTime, default=datetime.utcnow)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)


class Profile(db.Model):
    __tablename__ = 'profile'
    id            = db.Column(db.Integer, primary_key=True)
    full_name     = db.Column(db.String(120), default='Narayan Kishor Adhude')
    tagline       = db.Column(db.String(300), default='Full Stack Developer | Python Developer | .NET Developer | AI & ML Enthusiast | Data Scientist')
    bio           = db.Column(db.Text)
    career_obj    = db.Column(db.Text)
    location      = db.Column(db.String(200), default='Chhatrapati Sambhajinagar, Maharashtra, India')
    email         = db.Column(db.String(120), default='narayanadhude2004@gmail.com')
    phone         = db.Column(db.String(20), default='7030503039')
    profile_image = db.Column(db.String(300), default='')
    resume_url    = db.Column(db.String(500), default='https://drive.google.com/file/d/15XZGYBJ6F60FzIM0E2hSKEKEN99Y9Fkw/view')
    projects_count        = db.Column(db.Integer, default=10)
    certifications_count  = db.Column(db.Integer, default=13)
    technologies_count    = db.Column(db.Integer, default=25)
    experience_months     = db.Column(db.Integer, default=2)
    updated_at    = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class Service(db.Model):
    __tablename__ = 'services'
    id          = db.Column(db.Integer, primary_key=True)
    title       = db.Column(db.String(300), nullable=False)
    description = db.Column(db.Text, nullable=False)
    icon        = db.Column(db.String(100), nullable=False)
    order       = db.Column(db.Integer, default=0)
    is_active   = db.Column(db.Boolean, default=True)


class Language(db.Model):
    __tablename__ = 'languages'
    id          = db.Column(db.Integer, primary_key=True)
    name        = db.Column(db.String(100), nullable=False)
    proficiency = db.Column(db.String(100), nullable=False)
    order       = db.Column(db.Integer, default=0)
    is_active   = db.Column(db.Boolean, default=True)


class SocialLink(db.Model):
    __tablename__ = 'social_links'
    id       = db.Column(db.Integer, primary_key=True)
    platform = db.Column(db.String(50), nullable=False)
    url      = db.Column(db.String(500), nullable=False)
    icon     = db.Column(db.String(100), default='fab fa-link')
    order    = db.Column(db.Integer, default=0)
    is_active = db.Column(db.Boolean, default=True)


class Project(db.Model):
    __tablename__ = 'projects'
    id          = db.Column(db.Integer, primary_key=True)
    title       = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text)
    tech_stack  = db.Column(db.String(500))   # comma-separated
    features    = db.Column(db.Text)           # JSON list stored as text
    github_url  = db.Column(db.String(500))
    live_url    = db.Column(db.String(500))
    image       = db.Column(db.String(300))
    category    = db.Column(db.String(100), default='AI/ML')
    is_featured = db.Column(db.Boolean, default=False)
    order       = db.Column(db.Integer, default=0)
    created_at  = db.Column(db.DateTime, default=datetime.utcnow)

    def tech_list(self):
        return [t.strip() for t in (self.tech_stack or '').split(',') if t.strip()]

    def features_list(self):
        try:
            return json.loads(self.features or '[]')
        except Exception:
            return [f.strip() for f in (self.features or '').split('\n') if f.strip()]


class Skill(db.Model):
    __tablename__ = 'skills'
    id         = db.Column(db.Integer, primary_key=True)
    name       = db.Column(db.String(100), nullable=False)
    category   = db.Column(db.String(100), nullable=False)
    proficiency = db.Column(db.Integer, default=80)  # 0-100
    icon       = db.Column(db.String(100), default='')
    order      = db.Column(db.Integer, default=0)


class Experience(db.Model):
    __tablename__ = 'experiences'
    id           = db.Column(db.Integer, primary_key=True)
    title        = db.Column(db.String(200), nullable=False)
    company      = db.Column(db.String(200), nullable=False)
    location     = db.Column(db.String(200))
    start_date   = db.Column(db.String(50))
    end_date     = db.Column(db.String(50))
    emp_type     = db.Column(db.String(100))  # Intern, Full-time, etc.
    technologies = db.Column(db.String(500))
    responsibilities = db.Column(db.Text)     # JSON list
    order        = db.Column(db.Integer, default=0)
    is_current   = db.Column(db.Boolean, default=False)

    def resp_list(self):
        try:
            return json.loads(self.responsibilities or '[]')
        except Exception:
            return [r.strip() for r in (self.responsibilities or '').split('\n') if r.strip()]

    def tech_list(self):
        return [t.strip() for t in (self.technologies or '').split(',') if t.strip()]


class Education(db.Model):
    __tablename__ = 'education'
    id         = db.Column(db.Integer, primary_key=True)
    degree     = db.Column(db.String(200), nullable=False)
    institution = db.Column(db.String(300), nullable=False)
    year_start = db.Column(db.String(10))
    year_end   = db.Column(db.String(10))
    grade      = db.Column(db.String(50))
    grade_type = db.Column(db.String(20), default='CGPA')  # CGPA or %
    description = db.Column(db.Text)
    order      = db.Column(db.Integer, default=0)


class Certification(db.Model):
    __tablename__ = 'certifications'
    id           = db.Column(db.Integer, primary_key=True)
    title        = db.Column(db.String(300), nullable=False)
    issuer       = db.Column(db.String(200), nullable=False)
    category     = db.Column(db.String(100), default='Technical')
    cert_url     = db.Column(db.String(500))
    issue_date   = db.Column(db.String(50))
    credential_id = db.Column(db.String(200))
    image        = db.Column(db.String(300))
    order        = db.Column(db.Integer, default=0)


class Achievement(db.Model):
    __tablename__ = 'achievements'
    id          = db.Column(db.Integer, primary_key=True)
    title       = db.Column(db.String(300), nullable=False)
    description = db.Column(db.Text)
    date        = db.Column(db.String(50))
    icon        = db.Column(db.String(100), default='fas fa-trophy')
    category    = db.Column(db.String(100), default='Leadership')
    order       = db.Column(db.Integer, default=0)


class Research(db.Model):
    __tablename__ = 'research'
    id          = db.Column(db.Integer, primary_key=True)
    title       = db.Column(db.String(500), nullable=False)
    journal     = db.Column(db.String(300))
    abstract    = db.Column(db.Text)
    paper_url   = db.Column(db.String(500))
    pub_date    = db.Column(db.String(50))
    authors     = db.Column(db.String(500))
    keywords    = db.Column(db.String(300))
    order       = db.Column(db.Integer, default=0)


class Contact(db.Model):
    __tablename__ = 'contacts'
    id         = db.Column(db.Integer, primary_key=True)
    name       = db.Column(db.String(100), nullable=False)
    email      = db.Column(db.String(120), nullable=False)
    subject    = db.Column(db.String(300))
    message    = db.Column(db.Text, nullable=False)
    is_read    = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


@login_manager.user_loader
def load_user(user_id):
    return AdminUser.query.get(int(user_id))


# ─── Seed Default Data ────────────────────────────────────────────────────────

def seed_data():
    """Populate database with default portfolio data."""

    # Admin user
    if not AdminUser.query.first():
        admin_username = os.environ.get('ADMIN_USERNAME', '').strip()
        admin_email = os.environ.get('ADMIN_EMAIL', '').strip()
        admin_password = os.environ.get('ADMIN_PASSWORD', '').strip()
        if IS_PRODUCTION and (
            not admin_username or not admin_email or not admin_password
            or admin_username.startswith('replace-with-')
            or admin_email.startswith('replace-with-')
            or admin_password == 'admin123'
            or admin_password.startswith('replace-with-')
        ):
            raise RuntimeError(
                'ADMIN_USERNAME, ADMIN_EMAIL, and a non-default ADMIN_PASSWORD '
                'must be explicitly configured for production.'
            )
        admin = AdminUser(
            username=admin_username or 'admin',
            email=admin_email or 'admin@portfolio.com',
        )
        admin.set_password(admin_password or 'admin123')
        db.session.add(admin)

    # Profile
    if not Profile.query.first():
        profile = Profile(
            full_name='Narayan Kishor Adhude',
            tagline='Full Stack Developer | Python Developer | .NET Developer | AI & ML Enthusiast | Data Scientist',
            bio=("I'm a passionate Final Year B.E. student specializing in AI/ML and Full Stack Development. "
                 "With hands-on experience in Python, Flask, TensorFlow, and ASP.NET, I build intelligent "
                 "systems and scalable web applications. My research in plant disease detection using CNN "
                 "reflects my drive to solve real-world problems with cutting-edge technology. "
                 "I thrive in collaborative environments, having served as General Secretary of the Student Council "
                 "and participated in national-level hackathons and cultural events."),
            career_obj=("To secure a position in a reputed MNC where I can work on real-world projects, "
                        "contribute effectively, enhance my technical skills, and grow as a Software Engineer "
                        "and AI/ML Professional."),
            location='Chhatrapati Sambhajinagar, Maharashtra, India',
            email='narayanadhude2004@gmail.com',
            phone='7030503039',
            resume_url='https://drive.google.com/file/d/15XZGYBJ6F60FzIM0E2hSKEKEN99Y9Fkw/view',
            projects_count=10,
            certifications_count=13,
            technologies_count=25,
            experience_months=2,
        )
        db.session.add(profile)

    # Services
    if not Service.query.first():
        services = [
            ('Full Stack Web Development', 'Building full stack web applications with the MERN Stack, Java, Python, ASP.NET, C#, and SQL.', 'fas fa-brain', 1),
            ('AI & Machine Learning Solutions', 'Developing Python-based AI and Machine Learning applications, including Computer Vision and CNN-based solutions.', 'fas fa-layer-group', 2),
            ('Backend & API Development', 'Developing Flask backends and REST APIs, with API integration and testing using Postman.', 'fab fa-python', 3),
            ('Frontend & UI Development', 'Creating responsive interfaces with React, JavaScript, HTML, CSS, Tailwind CSS, and Bootstrap.', 'fas fa-server', 4),
            ('DevOps & Containerization', 'Supporting containerized application environments with Docker and Kubernetes.', 'fas fa-chart-line', 5),
            ('Java Development', 'Developing software solutions with Java while applying object-oriented programming and problem-solving skills.', 'fas fa-database', 6),
            ('Python Development', 'Building Python applications, Flask backends, and Python-based AI/ML solutions.', 'fab fa-python', 7),
            ('ASP.NET & C# Development', 'Developing web applications with ASP.NET, C#, SQL, and responsive Bootstrap interfaces.', 'fas fa-windows', 8),
            ('Figma & Responsive UI Implementation', 'Translating Figma designs into responsive frontend interfaces using HTML, CSS, React, and Tailwind CSS.', 'fas fa-robot', 9),
        ]
        for title, description, icon, order in services:
            db.session.add(Service(title=title, description=description, icon=icon, order=order, is_active=True))

    # Languages
    if not Language.query.first():
        languages = [
            ('English', '', 1),
            ('Hindi', '', 2),
            ('Marathi', '', 3),
            ('Japanese', 'Foundation', 4),
        ]
        for name, proficiency, order in languages:
            db.session.add(Language(name=name, proficiency=proficiency, order=order, is_active=True))

    # Social Links
    if not SocialLink.query.first():
        socials = [
            ('LinkedIn',   'http://www.linkedin.com/in/narayan-adhude-🎯-5b14081bb', 'fab fa-linkedin', 1),
            ('GitHub',     'https://github.com/Gate2024',                              'fab fa-github',   2),
            ('Instagram',  'https://www.instagram.com/narayan_adhude0106',             'fab fa-instagram',3),
            ('Twitter/X',  'https://x.com/AdhudeNarayan',                              'fab fa-x-twitter',4),
            ('YouTube',    'https://www.youtube.com/@narayanadhude2004',               'fab fa-youtube',  5),
            ('Facebook',   'https://www.facebook.com/people/Narayan-Adhude',           'fab fa-facebook', 6),
        ]
        for name, url, icon, order in socials:
            db.session.add(SocialLink(platform=name, url=url, icon=icon, order=order))

    # Education
    if not Education.query.first():
        edu_data = [
            ('Bachelor of Engineering', 'Dr. Babasaheb Ambedkar Marathwada University', '2022', '2026', '7.93', 'CGPA', 'Computer Engineering', 1),
            ('12th – HSC', 'Maharashtra State Board (MSBSHSE)', '2020', '2022', '77.33', '%', 'Science & Technology', 2),
            ('10th – SSC', 'Maharashtra State Board (MSBSHSE)', '2019', '2020', '89.80', '%', 'General Studies', 3),
        ]
        for d, i, ys, ye, g, gt, desc, o in edu_data:
            db.session.add(Education(degree=d, institution=i, year_start=ys, year_end=ye, grade=g, grade_type=gt, description=desc, order=o))

    # Skills
    if not Skill.query.first():
        skills_data = [
            # Programming Languages
            ('Python', 'Programming Languages', 95), ('Java', 'Programming Languages', 80),
            ('JavaScript', 'Programming Languages', 82), ('C#', 'Programming Languages', 78),
            ('SQL', 'Programming Languages', 85),
            # AI/ML
            ('TensorFlow', 'AI / ML', 88), ('OpenCV', 'AI / ML', 85),
            ('NumPy', 'AI / ML', 92), ('Pandas', 'AI / ML', 90),
            ('Matplotlib', 'AI / ML', 85), ('scikit-learn', 'AI / ML', 87),
            ('Streamlit', 'AI / ML', 80),
            # Web Dev
            ('HTML5', 'Web Development', 92), ('CSS3', 'Web Development', 88),
            ('Bootstrap', 'Web Development', 90), ('Tailwind CSS', 'Web Development', 82),
            ('Flask', 'Web Development', 88), ('ASP.NET Web Forms', 'Web Development', 78),
            # Databases
            ('PostgreSQL', 'Databases', 82), ('MySQL', 'Databases', 85),
            # Cloud
            ('AWS', 'Cloud & DevOps', 70), ('Azure', 'Cloud & DevOps', 68),
            ('GCP', 'Cloud & DevOps', 65), ('OCI', 'Cloud & DevOps', 72),
            ('Git & GitHub', 'Cloud & DevOps', 90),
            # CS Fundamentals
            ('DSA', 'CS Fundamentals', 80), ('OOP', 'CS Fundamentals', 88),
            ('DBMS', 'CS Fundamentals', 85), ('OS', 'CS Fundamentals', 78),
            ('Computer Networks', 'CS Fundamentals', 75),
        ]
        for name, cat, prof in skills_data:
            db.session.add(Skill(name=name, category=cat, proficiency=prof))

    # Experience
    if not Experience.query.first():
        exp1_resp = json.dumps([
            "Developed Book and Student Management modules for library system",
            "Implemented Issue-Return tracking system with fine auto-calculation",
            "Built secure session-based authentication with role-based dashboards",
            "Executed complete CRUD operations using ADO.NET and MySQL",
            "Designed responsive Bootstrap UI with dynamic GridView data handling",
            "Resolved complex data binding and update issues in ASP.NET Web Forms",
        ])
        db.session.add(Experience(
            title='Software Development Intern',
            company='Vikalpa Guru Pvt. Ltd',
            location='On-site',
            start_date='Jun 2025',
            end_date='Aug 2025',
            emp_type='Internship · 2 Months',
            technologies='ASP.NET Web Forms, C#, MySQL, ADO.NET, Bootstrap',
            responsibilities=exp1_resp,
            order=1,
        ))
        exp2_resp = json.dumps([
            "Conducted online paid internship focused on human rights research",
            "Researched AI applications for human rights monitoring",
            "Prepared and presented research findings achieving First Place award",
        ])
        db.session.add(Experience(
            title='Research Intern',
            company='National Human Rights Commission, India (NHRC)',
            location='Online',
            start_date='2024',
            end_date='2024',
            emp_type='Online Paid Internship',
            technologies='Research, Documentation, AI Applications',
            responsibilities=exp2_resp,
            order=2,
        ))

    # Projects
    if not Project.query.first():
        projects_data = [
            {
                'title': 'ML-Based Crop Disease Diagnostic System',
                'description': 'An intelligent web application for detecting plant diseases from leaf images using deep learning. Designed to empower farmers with real-time AI-powered diagnostics, treatment suggestions, and disease history tracking.',
                'tech_stack': 'Python, Flask, TensorFlow, CNN, OpenCV, SQLite',
                'features': json.dumps(['Plant disease prediction via deep learning CNN model', 'Real-time image processing with OpenCV', 'Integrated chatbot for farmer guidance', 'Admin dashboard with analytics', 'Farmer-friendly responsive UI', 'Prediction history and reporting', 'Secure JWT authentication']),
                'github_url': '',
                'category': 'AI / ML',
                'is_featured': True,
                'order': 1,
            },
            {
                'title': 'Emotion Detection System using CNN',
                'description': 'Real-time facial emotion recognition system using webcam feed. Classifies seven human emotions with high accuracy using a custom CNN architecture and OpenCV face detection pipeline.',
                'tech_stack': 'Python, Flask, OpenCV, NumPy, TensorFlow',
                'features': json.dumps(['Real-time emotion detection via webcam', 'CNN-based 7-class emotion classification', 'Face detection with OpenCV Haar Cascade', 'Responsive live camera integration', 'Emotion frequency analytics dashboard']),
                'github_url': '',
                'category': 'AI / ML',
                'is_featured': True,
                'order': 2,
            },
            {
                'title': 'Bank Application',
                'description': 'A console-based Python banking application demonstrating core financial operations with robust input validation, modular architecture, and file-based persistent storage.',
                'tech_stack': 'Python, NumPy, Pandas',
                'features': json.dumps(['Deposit, withdrawal, and balance operations', 'Complete transaction history', 'Input validation and error handling', 'Modular and clean architecture', 'File-based data persistence']),
                'github_url': 'https://github.com/Gate2024/Bank_Application.git',
                'category': 'Python',
                'is_featured': False,
                'order': 3,
            },
            {
                'title': 'Iris Flower Classification – Streamlit ML App',
                'description': 'An interactive machine learning web app built with Streamlit for classifying Iris flower species. Features a clean UI for real-time predictions using a trained scikit-learn model.',
                'tech_stack': 'Python, Streamlit, scikit-learn, NumPy, joblib',
                'features': json.dumps(['Interactive Streamlit web interface', 'Real-time ML classification predictions', 'Data preprocessing pipeline', 'Pre-trained model loading with joblib', 'Visual prediction analytics and charts']),
                'github_url': 'https://github.com/Gate2024/Iris_Streamlit_App.git',
                'category': 'AI / ML',
                'is_featured': True,
                'order': 4,
            },
            {
                'title': 'Library Management System',
                'description': 'A full-featured library management web application developed during internship at Vikalpa Guru Pvt. Ltd. Supports complete book lifecycle management with role-based access control.',
                'tech_stack': 'ASP.NET Web Forms, C#, MySQL, ADO.NET, Bootstrap',
                'features': json.dumps(['Complete book and student management', 'Secure authentication with session management', 'Issue-return tracking system', 'Automated fine calculation engine', 'Role-based admin and student dashboards', 'Dynamic GridView with full CRUD', 'Responsive Bootstrap UI']),
                'github_url': '',
                'category': '.NET',
                'is_featured': True,
                'order': 5,
            },
        ]
        for p in projects_data:
            db.session.add(Project(**p))

    # Certifications
    if not Certification.query.first():
        certs = [
            ('Programming in Java', 'IIT Kharagpur (NPTEL)', 'Technical', 1),
            ('Python for Data Science', 'IIT Kanpur (NPTEL)', 'Technical', 2),
            ('Overview of GIS', 'ISRO / IIRS', 'Technical', 3),
            ('Geodata Processing using Python', 'ISRO / IIRS', 'Technical', 4),
            ('Oracle Cloud Infrastructure 2025 – Data Science Professional', 'Oracle (OCI)', 'Cloud', 5),
            ('Python Essentials 1', 'Cisco Networking Academy', 'Technical', 6),
            ('Database Management System', 'Infosys Springboard', 'Technical', 7),
            ('Cybersecurity Fundamentals', 'Tech Mahindra Foundation', 'Technical', 8),
            ('Linux Fundamentals RH104', 'Red Hat Academy', 'Technical', 9),
            ('Green Skills & AI', 'Shell & Edunet Foundation', 'AI/ML', 10),
            ('Data Science & Analytics', 'HP LIFE', 'Data Science', 11),
            ('Generative AI Recruiting', 'LinkedIn Learning', 'AI/ML', 12),
            ('YUVA AI For All', 'TCS iON', 'AI/ML', 13),
            ('TCS iON Career Edge', 'TCS iON', 'Soft Skills', 14),
            ('Communication & Presentation Skills', 'Various Platforms', 'Soft Skills', 15),
        ]
        for title, issuer, cat, order in certs:
            db.session.add(Certification(title=title, issuer=issuer, category=cat, order=order))

    # Achievements
    if not Achievement.query.first():
        achievements = [
            ('General Secretary – Student Council 2K26', 'Elected as General Secretary for the college Student Council 2K26, leading student governance, event planning, and institutional representation.', '2025', 'fas fa-crown', 'Leadership'),
            ('NSS Representative – Student Council 2K25', 'Served as NSS Representative, organizing community service activities and social awareness campaigns on campus.', '2024', 'fas fa-hands-helping', 'Leadership'),
            ('Tokushima University Summer School 2025', 'Selected for the prestigious international summer school program at Tokushima University, Japan, gaining global exposure.', '2025', 'fas fa-globe-asia', 'Academic'),
            ('1st Place – NHRC Internship Research Project', 'Secured First Place for the research project during the National Human Rights Commission online internship.', '2024', 'fas fa-medal', 'Academic'),
            ('District Level Aavishkar 2025', 'Participated in District Level Aavishkar 2025, a state-level inter-university research festival showcasing innovative projects.', '2025', 'fas fa-flask', 'Research'),
            ('Swayambhu 2025 – National Event', 'Participated in Swayambhu 2025, a prestigious national-level event celebrating student achievements and innovations.', '2025', 'fas fa-star', 'Events'),
            ('District Youth Festival 2025', 'Active participant in the District Youth Festival 2025, representing the college in cultural and academic competitions.', '2025', 'fas fa-music', 'Cultural'),
            ('MSME Idea Hackathon 4.0', 'Submitted innovative idea in MSME Idea Hackathon 4.0, demonstrating entrepreneurial thinking and problem-solving skills.', '2024', 'fas fa-lightbulb', 'Hackathon'),
        ]
        for title, desc, date, icon, cat in achievements:
            db.session.add(Achievement(title=title, description=desc, date=date, icon=icon, category=cat))

    # Research
    if not Research.query.first():
        db.session.add(Research(
            title='AI-Driven Plant Disease Detection Classification Using Convolutional Neural Network',
            journal='IJCRT (International Journal of Creative Research Thoughts)',
            abstract='This research presents an AI-powered system for automated plant disease detection using Convolutional Neural Networks (CNN). The system processes leaf images to classify diseases with high accuracy, enabling timely interventions in agriculture. The model demonstrates significant improvements over traditional detection methods, offering a scalable solution for precision farming.',
            paper_url='https://drive.google.com/file/d/1ww9MiuUdKF3HZyVyUO52UAdkLr_1l0iq/view',
            authors='Narayan Kishor Adhude',
            keywords='CNN, Plant Disease Detection, Deep Learning, TensorFlow, OpenCV, Precision Agriculture',
        ))

    db.session.commit()


@contextmanager
def _sqlite_initialization_lock():
    """Serialize SQLite initialization across workers without adding a dependency."""
    lock_path = os.path.join(app.instance_path, '.portfolio-init.lock')
    os.makedirs(app.instance_path, exist_ok=True)

    with open(lock_path, 'a+b') as lock_file:
        if os.name == 'nt':
            import msvcrt

            lock_file.seek(0, os.SEEK_END)
            if lock_file.tell() == 0:
                lock_file.write(b'0')
                lock_file.flush()
            lock_file.seek(0)
            while True:
                try:
                    msvcrt.locking(lock_file.fileno(), msvcrt.LK_NBLCK, 1)
                    break
                except OSError:
                    time.sleep(0.05)
        else:
            import fcntl

            fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX)

        try:
            yield
        finally:
            if os.name == 'nt':
                lock_file.seek(0)
                msvcrt.locking(lock_file.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)


@contextmanager
def database_initialization_lock():
    """Serialize startup work for PostgreSQL and the local SQLite fallback."""
    if db.engine.url.get_backend_name() == 'postgresql':
        lock_key = 418271
        with db.engine.connect() as lock_connection:
            lock_connection.execute(
                text('SELECT pg_advisory_lock(:lock_key)'),
                {'lock_key': lock_key},
            )
            lock_connection.commit()
            try:
                yield
            finally:
                lock_connection.execute(
                    text('SELECT pg_advisory_unlock(:lock_key)'),
                    {'lock_key': lock_key},
                )
                lock_connection.commit()
    else:
        with _sqlite_initialization_lock():
            yield


def initialize_database():
    with database_initialization_lock():
        db.create_all()
        seed_data()


# ─── Public Routes ────────────────────────────────────────────────────────────

@app.route('/')
def index():
    profile       = Profile.query.first()
    social_links  = SocialLink.query.filter_by(is_active=True).order_by(SocialLink.order).all()
    projects      = Project.query.order_by(Project.order).all()
    skills        = Skill.query.order_by(Skill.category, Skill.order).all()
    experiences   = Experience.query.order_by(Experience.order).all()
    education     = Education.query.order_by(Education.order).all()
    certifications = Certification.query.order_by(Certification.order).all()
    achievements  = Achievement.query.order_by(Achievement.order).all()
    research      = Research.query.order_by(Research.order).all()
    services      = Service.query.filter_by(is_active=True).order_by(Service.order).all()
    languages     = Language.query.filter_by(is_active=True).order_by(Language.order).all()
    project_count = Project.query.count()
    certification_count = Certification.query.count()
    technology_count = Skill.query.count()

    # Group skills by category
    skill_categories = {}
    for skill in skills:
        skill_categories.setdefault(skill.category, []).append(skill)

    # Group certifications by category
    cert_categories = {}
    for cert in certifications:
        cert_categories.setdefault(cert.category, []).append(cert)

    return render_template('index.html',
        profile=profile,
        social_links=social_links,
        projects=projects,
        skill_categories=skill_categories,
        experiences=experiences,
        education=education,
        certifications=certifications,
        cert_categories=cert_categories,
        achievements=achievements,
        research=research,
        services=services,
        languages=languages,
        project_count=project_count,
        certification_count=certification_count,
        technology_count=technology_count,
        current_year=datetime.utcnow().year,
    )


@app.route('/contact', methods=['POST'])
def contact():
    name    = request.form.get('name', '').strip()
    email   = request.form.get('email', '').strip()
    subject = request.form.get('subject', '').strip()
    message = request.form.get('message', '').strip()

    if not all([name, email, message]):
        return jsonify({'success': False, 'message': 'Please fill in all required fields.'}), 400

    if not re.fullmatch(r'[^@\s]+@[^@\s]+\.[^@\s]+', email):
        return jsonify({'success': False, 'message': 'Please enter a valid email address.'}), 400

    msg = Contact(name=name, email=email, subject=subject, message=message)
    db.session.add(msg)
    db.session.commit()
    return jsonify({'success': True, 'message': 'Thank you! Your message has been sent successfully.'})


# ─── Admin Auth ───────────────────────────────────────────────────────────────

@app.route('/admin/login', methods=['GET', 'POST'])
def admin_login():
    if current_user.is_authenticated:
        return redirect(url_for('admin_dashboard'))
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        user = AdminUser.query.filter_by(username=username).first()
        if user and user.check_password(password):
            login_user(user)
            return redirect(url_for('admin_dashboard'))
        flash('Invalid username or password.', 'danger')
    return render_template('auth/login.html')


@app.route('/admin/logout', methods=['POST'])
@login_required
def admin_logout():
    logout_user()
    flash('Logged out successfully.', 'success')
    return redirect(url_for('index'))


# ─── Admin Dashboard ──────────────────────────────────────────────────────────

@app.route('/admin')
@login_required
def admin_dashboard():
    stats = {
        'projects':       Project.query.count(),
        'skills':         Skill.query.count(),
        'certifications': Certification.query.count(),
        'achievements':   Achievement.query.count(),
        'education':      Education.query.count(),
        'experience':     Experience.query.count(),
        'research':       Research.query.count(),
        'services':       Service.query.count(),
        'messages':       Contact.query.count(),
        'unread':         Contact.query.filter_by(is_read=False).count(),
    }
    recent_messages = Contact.query.order_by(Contact.created_at.desc()).limit(5).all()
    return render_template('admin/dashboard.html', stats=stats, recent_messages=recent_messages)


# ── Admin: Profile ────────────────────────────────────────────────────────────

@app.route('/admin/profile', methods=['GET', 'POST'])
@login_required
def admin_profile():
    profile = Profile.query.first()
    if request.method == 'POST':
        counters = {}
        for field, label in (
            ('projects_count', 'Projects count'),
            ('certifications_count', 'Certifications count'),
            ('technologies_count', 'Technologies count'),
            ('experience_months', 'Experience'),
        ):
            counters[field], error = parse_integer_field(
                request.form.get(field), label, getattr(profile, field), min_value=0
            )
            if error:
                flash(error, 'danger')
                return render_template('admin/profile.html', profile=profile, form_data=request.form), 400

        full_name = request.form.get('full_name', profile.full_name)
        tagline = request.form.get('tagline', profile.tagline)
        location = request.form.get('location', profile.location)
        email = request.form.get('email', profile.email)
        phone = request.form.get('phone', profile.phone)
        resume_url, url_error = validate_http_url(
            request.form.get('resume_url', profile.resume_url), 'Resume URL'
        )
        length_error = validate_field_lengths((
            ('Full name', full_name, 120),
            ('Tagline', tagline, 300),
            ('Location', location, 200),
            ('Email address', email, 120),
            ('Phone number', phone, 20),
        ))
        if url_error or length_error:
            flash(url_error or length_error, 'danger')
            return render_template('admin/profile.html', profile=profile, form_data=request.form), 400

        new_image_path = None
        uploaded_image = request.files.get('profile_image')
        if uploaded_image and uploaded_image.filename:
            new_image_path, error = save_image_file(uploaded_image, 'profile')
            if error:
                flash(error, 'danger')
                return render_template('admin/profile.html', profile=profile, form_data=request.form), 400

        old_image_path = profile.profile_image
        profile.full_name   = full_name
        profile.tagline     = tagline
        profile.bio         = request.form.get('bio', profile.bio)
        profile.career_obj  = request.form.get('career_obj', profile.career_obj)
        profile.location    = location
        profile.email       = email
        profile.phone       = phone
        profile.resume_url  = resume_url
        profile.projects_count       = counters['projects_count']
        profile.certifications_count = counters['certifications_count']
        profile.technologies_count   = counters['technologies_count']
        profile.experience_months    = counters['experience_months']
        if new_image_path:
            profile.profile_image = new_image_path

        try:
            db.session.commit()
        except Exception:
            db.session.rollback()
            if new_image_path:
                remove_uploaded_file(new_image_path, 'profile')
            flash('Profile could not be updated. Please try again.', 'danger')
            return render_template('admin/profile.html', profile=profile, form_data=request.form), 500
        if new_image_path and old_image_path != new_image_path:
            remove_uploaded_file(old_image_path, 'profile')
        flash('Profile updated successfully!', 'success')
        return redirect(url_for('admin_profile'))
    return render_template('admin/profile.html', profile=profile)


# ── Admin: Services ───────────────────────────────────────────────────────────

@app.route('/admin/services')
@login_required
def admin_services():
    services = Service.query.order_by(Service.order).all()
    return render_template('admin/services.html', services=services, form_data={})


@app.route('/admin/services/add', methods=['POST'])
@login_required
def admin_add_service():
    title = request.form.get('title', '').strip()
    description = request.form.get('description', '').strip()
    icon = request.form.get('icon', '').strip()
    order_raw = request.form.get('order', '').strip()
    services = Service.query.order_by(Service.order).all()

    if not title or not description or not icon:
        flash('Title, description, and icon are required.', 'danger')
        return render_template('admin/services.html', services=services, form_data=request.form)

    length_error = validate_field_lengths((
        ('Service title', title, 300),
        ('Service icon', icon, 100),
    ))
    order, order_error = parse_order_field(order_raw)
    if length_error or order_error:
        flash(length_error or order_error, 'danger')
        return render_template('admin/services.html', services=services, form_data=request.form)
    if order is None:
        max_order = db.session.query(db.func.max(Service.order)).scalar()
        order = (max_order if max_order is not None else 0) + 1

    service = Service(
        title=title,
        description=description,
        icon=icon,
        order=order,
        is_active=request.form.get('is_active', '1') == '1',
    )
    db.session.add(service)
    db.session.commit()
    flash('Service added!', 'success')
    return redirect(url_for('admin_services'))


@app.route('/admin/services/edit/<int:sid>', methods=['GET', 'POST'])
@login_required
def admin_edit_service(sid):
    service = Service.query.get_or_404(sid)
    form_data = request.form if request.method == 'POST' else {}

    if request.method == 'POST':
        title = request.form.get('title', '').strip()
        description = request.form.get('description', '').strip()
        icon = request.form.get('icon', '').strip()
        order_raw = request.form.get('order', '').strip()

        if not title or not description or not icon:
            flash('Title, description, and icon are required.', 'danger')
            return render_template('admin/service_form.html', service=service, form_data=form_data)

        length_error = validate_field_lengths((
            ('Service title', title, 300),
            ('Service icon', icon, 100),
        ))
        order, order_error = parse_order_field(order_raw, service.order)
        if length_error or order_error:
            flash(length_error or order_error, 'danger')
            return render_template('admin/service_form.html', service=service, form_data=form_data)

        service.title = title
        service.description = description
        service.icon = icon
        service.order = order
        service.is_active = request.form.get('is_active') == '1'
        db.session.commit()
        flash('Service updated!', 'success')
        return redirect(url_for('admin_services'))

    return render_template('admin/service_form.html', service=service, form_data=form_data)


@app.route('/admin/services/delete/<int:sid>', methods=['POST'])
@login_required
def admin_delete_service(sid):
    service = Service.query.get_or_404(sid)
    db.session.delete(service)
    db.session.commit()
    flash('Service deleted.', 'success')
    return redirect(url_for('admin_services'))


# ── Admin: Languages ──────────────────────────────────────────────────────────

@app.route('/admin/languages')
@login_required
def admin_languages():
    languages = Language.query.order_by(Language.order).all()
    return render_template('admin/languages.html', languages=languages, form_data={})


@app.route('/admin/languages/add', methods=['POST'])
@login_required
def admin_add_language():
    name = request.form.get('name', '').strip()
    proficiency = request.form.get('proficiency', '').strip()
    order_raw = request.form.get('order', '').strip()
    languages = Language.query.order_by(Language.order).all()

    if not name or not proficiency:
        flash('Language name and proficiency are required.', 'danger')
        return render_template('admin/languages.html', languages=languages, form_data=request.form)

    length_error = validate_field_lengths((
        ('Language name', name, 100),
        ('Language proficiency', proficiency, 100),
    ))
    order, order_error = parse_order_field(order_raw)
    if length_error or order_error:
        flash(length_error or order_error, 'danger')
        return render_template('admin/languages.html', languages=languages, form_data=request.form)
    if order is None:
        max_order = db.session.query(db.func.max(Language.order)).scalar()
        order = (max_order if max_order is not None else 0) + 1

    language = Language(
        name=name,
        proficiency=proficiency,
        order=order,
        is_active=request.form.get('is_active', '1') == '1',
    )
    db.session.add(language)
    db.session.commit()
    flash('Language added!', 'success')
    return redirect(url_for('admin_languages'))


@app.route('/admin/languages/edit/<int:lid>', methods=['GET', 'POST'])
@login_required
def admin_edit_language(lid):
    language = Language.query.get_or_404(lid)
    form_data = request.form if request.method == 'POST' else {}

    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        proficiency = request.form.get('proficiency', '').strip()
        order_raw = request.form.get('order', '').strip()

        if not name or not proficiency:
            flash('Language name and proficiency are required.', 'danger')
            return render_template('admin/language_form.html', language=language, form_data=form_data)

        length_error = validate_field_lengths((
            ('Language name', name, 100),
            ('Language proficiency', proficiency, 100),
        ))
        order, order_error = parse_order_field(order_raw, language.order)
        if length_error or order_error:
            flash(length_error or order_error, 'danger')
            return render_template('admin/language_form.html', language=language, form_data=form_data)

        language.name = name
        language.proficiency = proficiency
        language.order = order
        language.is_active = request.form.get('is_active') == '1'
        db.session.commit()
        flash('Language updated!', 'success')
        return redirect(url_for('admin_languages'))

    return render_template('admin/language_form.html', language=language, form_data=form_data)


@app.route('/admin/languages/delete/<int:lid>', methods=['POST'])
@login_required
def admin_delete_language(lid):
    language = Language.query.get_or_404(lid)
    db.session.delete(language)
    db.session.commit()
    flash('Language deleted.', 'success')
    return redirect(url_for('admin_languages'))


# ── Admin: Education ──────────────────────────────────────────────────────────

@app.route('/admin/education')
@login_required
def admin_education():
    education = Education.query.order_by(Education.order).all()
    return render_template('admin/education.html', education=education)


@app.route('/admin/education/add', methods=['GET', 'POST'])
@login_required
def admin_add_education():
    form_data = request.form if request.method == 'POST' else {}
    if request.method == 'POST':
        degree = request.form.get('degree', '').strip()
        institution = request.form.get('institution', '').strip()
        order_raw = request.form.get('order', '').strip()

        if not degree or not institution:
            flash('Degree and institution are required.', 'danger')
            return render_template('admin/education_form.html', education=None, form_data=form_data)

        length_error = validate_field_lengths((
            ('Degree', degree, 200),
            ('Institution', institution, 300),
            ('Start year', request.form.get('year_start', ''), 10),
            ('End year', request.form.get('year_end', ''), 10),
            ('Grade', request.form.get('grade', ''), 50),
            ('Grade type', request.form.get('grade_type', ''), 20),
        ))
        order, order_error = parse_order_field(order_raw)
        if length_error or order_error:
            flash(length_error or order_error, 'danger')
            return render_template('admin/education_form.html', education=None, form_data=form_data)
        if order is None:
            max_order = db.session.query(db.func.max(Education.order)).scalar()
            order = (max_order if max_order is not None else 0) + 1

        education = Education(
            degree=degree,
            institution=institution,
            year_start=request.form.get('year_start', '').strip(),
            year_end=request.form.get('year_end', '').strip(),
            grade=request.form.get('grade', '').strip(),
            grade_type=request.form.get('grade_type', '').strip() or 'CGPA',
            description=request.form.get('description', '').strip(),
            order=order,
        )
        db.session.add(education)
        db.session.commit()
        flash('Education added!', 'success')
        return redirect(url_for('admin_education'))
    return render_template('admin/education_form.html', education=None, form_data=form_data)


@app.route('/admin/education/edit/<int:eid>', methods=['GET', 'POST'])
@login_required
def admin_edit_education(eid):
    education = Education.query.get_or_404(eid)
    form_data = request.form if request.method == 'POST' else {}
    if request.method == 'POST':
        degree = request.form.get('degree', '').strip()
        institution = request.form.get('institution', '').strip()
        order_raw = request.form.get('order', '').strip()

        if not degree or not institution:
            flash('Degree and institution are required.', 'danger')
            return render_template('admin/education_form.html', education=education, form_data=form_data)

        length_error = validate_field_lengths((
            ('Degree', degree, 200),
            ('Institution', institution, 300),
            ('Start year', request.form.get('year_start', ''), 10),
            ('End year', request.form.get('year_end', ''), 10),
            ('Grade', request.form.get('grade', ''), 50),
            ('Grade type', request.form.get('grade_type', ''), 20),
        ))
        order, order_error = parse_order_field(order_raw, education.order)
        if length_error or order_error:
            flash(length_error or order_error, 'danger')
            return render_template('admin/education_form.html', education=education, form_data=form_data)

        education.degree = degree
        education.institution = institution
        education.year_start = request.form.get('year_start', '').strip()
        education.year_end = request.form.get('year_end', '').strip()
        education.grade = request.form.get('grade', '').strip()
        education.grade_type = request.form.get('grade_type', '').strip()
        education.description = request.form.get('description', '').strip()
        education.order = order
        db.session.commit()
        flash('Education updated!', 'success')
        return redirect(url_for('admin_education'))
    return render_template('admin/education_form.html', education=education, form_data=form_data)


@app.route('/admin/education/delete/<int:eid>', methods=['POST'])
@login_required
def admin_delete_education(eid):
    education = Education.query.get_or_404(eid)
    db.session.delete(education)
    db.session.commit()
    flash('Education deleted.', 'success')
    return redirect(url_for('admin_education'))


# ── Admin: Projects ───────────────────────────────────────────────────────────

@app.route('/admin/projects')
@login_required
def admin_projects():
    projects = Project.query.order_by(Project.order).all()
    return render_template('admin/projects.html', projects=projects)


@app.route('/admin/projects/add', methods=['GET', 'POST'])
@login_required
def admin_add_project():
    if request.method == 'POST':
        order, error = parse_order_field(request.form.get('order'), 0)
        if error:
            flash(error, 'danger')
            return render_template('admin/project_form.html', project=None, form_data=request.form), 400

        title = request.form.get('title')
        tech_stack = request.form.get('tech_stack')
        category = request.form.get('category', 'AI/ML')
        github_url, github_error = validate_http_url(
            request.form.get('github_url'), 'GitHub URL'
        )
        live_url, live_error = validate_http_url(
            request.form.get('live_url'), 'Live demo URL'
        )
        length_error = validate_field_lengths((
            ('Project title', title, 200),
            ('Tech stack', tech_stack, 500),
            ('Category', category, 100),
        ))
        if github_error or live_error or length_error:
            flash(github_error or live_error or length_error, 'danger')
            return render_template('admin/project_form.html', project=None, form_data=request.form), 400

        image_path = None
        uploaded_image = request.files.get('image')
        if uploaded_image and uploaded_image.filename:
            image_path, error = save_image_file(uploaded_image, 'projects')
            if error:
                flash(error, 'danger')
                return render_template('admin/project_form.html', project=None, form_data=request.form), 400
        features_raw = request.form.get('features', '')
        features_list = [f.strip() for f in features_raw.split('\n') if f.strip()]
        p = Project(
            title=title,
            description=request.form.get('description'),
            tech_stack=tech_stack,
            features=json.dumps(features_list),
            github_url=github_url,
            live_url=live_url,
            category=category,
            is_featured=bool(request.form.get('is_featured')),
            order=order,
        )
        if image_path:
            p.image = image_path
        db.session.add(p)
        try:
            db.session.commit()
        except Exception:
            db.session.rollback()
            if image_path:
                remove_uploaded_file(image_path, 'projects')
            flash('Project could not be added. Please try again.', 'danger')
            return render_template('admin/project_form.html', project=None, form_data=request.form), 500
        flash('Project added!', 'success')
        return redirect(url_for('admin_projects'))
    return render_template('admin/project_form.html', project=None)


@app.route('/admin/projects/edit/<int:pid>', methods=['GET', 'POST'])
@login_required
def admin_edit_project(pid):
    p = Project.query.get_or_404(pid)
    if request.method == 'POST':
        order, error = parse_order_field(request.form.get('order'), p.order)
        if error:
            flash(error, 'danger')
            return render_template('admin/project_form.html', project=p, form_data=request.form), 400

        title = request.form.get('title', p.title)
        tech_stack = request.form.get('tech_stack', p.tech_stack)
        category = request.form.get('category', p.category)
        github_url, github_error = validate_http_url(
            request.form.get('github_url', p.github_url), 'GitHub URL'
        )
        live_url, live_error = validate_http_url(
            request.form.get('live_url', p.live_url), 'Live demo URL'
        )
        length_error = validate_field_lengths((
            ('Project title', title, 200),
            ('Tech stack', tech_stack, 500),
            ('Category', category, 100),
        ))
        if github_error or live_error or length_error:
            flash(github_error or live_error or length_error, 'danger')
            return render_template('admin/project_form.html', project=p, form_data=request.form), 400

        new_image_path = None
        uploaded_image = request.files.get('image')
        if uploaded_image and uploaded_image.filename:
            new_image_path, error = save_image_file(uploaded_image, 'projects')
            if error:
                flash(error, 'danger')
                return render_template('admin/project_form.html', project=p, form_data=request.form), 400
        old_image_path = p.image
        p.title       = title
        p.description = request.form.get('description', p.description)
        p.tech_stack  = tech_stack
        features_raw  = request.form.get('features', '')
        features_list = [f.strip() for f in features_raw.split('\n') if f.strip()]
        p.features    = json.dumps(features_list)
        p.github_url  = github_url
        p.live_url    = live_url
        p.category    = category
        p.is_featured = bool(request.form.get('is_featured'))
        p.order       = order
        if new_image_path:
            p.image = new_image_path
        try:
            db.session.commit()
        except Exception:
            db.session.rollback()
            if new_image_path:
                remove_uploaded_file(new_image_path, 'projects')
            flash('Project could not be updated. Please try again.', 'danger')
            return render_template('admin/project_form.html', project=p, form_data=request.form), 500
        if new_image_path and old_image_path != new_image_path:
            remove_uploaded_file(old_image_path, 'projects')
        flash('Project updated!', 'success')
        return redirect(url_for('admin_projects'))
    return render_template('admin/project_form.html', project=p)


@app.route('/admin/projects/delete/<int:pid>', methods=['POST'])
@login_required
def admin_delete_project(pid):
    p = Project.query.get_or_404(pid)
    image_path = p.image
    db.session.delete(p)
    try:
        db.session.commit()
    except Exception:
        db.session.rollback()
        flash('Project could not be deleted. Please try again.', 'danger')
        return redirect(url_for('admin_projects')), 500
    if image_path:
        remove_uploaded_file(image_path, 'projects')
    flash('Project deleted.', 'success')
    return redirect(url_for('admin_projects'))


# ── Admin: Skills ─────────────────────────────────────────────────────────────

@app.route('/admin/skills')
@login_required
def admin_skills():
    skills = Skill.query.order_by(Skill.category, Skill.order).all()
    return render_template('admin/skills.html', skills=skills)


@app.route('/admin/skills/add', methods=['POST'])
@login_required
def admin_add_skill():
    name = request.form.get('name', '')
    category = request.form.get('category', '')
    proficiency, error = parse_integer_field(
        request.form.get('proficiency'), 'Proficiency', 80, min_value=0, max_value=100
    )
    order, order_error = parse_order_field(request.form.get('order'), 0)
    length_error = validate_field_lengths((
        ('Skill name', name, 100),
        ('Skill category', category, 100),
    ))
    if error or order_error or length_error:
        flash(error or order_error or length_error, 'danger')
        return render_template(
            'admin/skills.html',
            skills=Skill.query.order_by(Skill.category, Skill.order).all(),
            form_data=request.form,
        ), 400
    s = Skill(
        name=name,
        category=category,
        proficiency=proficiency,
        order=order,
    )
    db.session.add(s)
    db.session.commit()
    flash('Skill added!', 'success')
    return redirect(url_for('admin_skills'))


@app.route('/admin/skills/edit/<int:sid>', methods=['POST'])
@login_required
def admin_edit_skill(sid):
    s = Skill.query.get_or_404(sid)
    name = request.form.get('name', s.name)
    category = request.form.get('category', s.category)
    proficiency, error = parse_integer_field(
        request.form.get('proficiency'), 'Proficiency', s.proficiency, min_value=0, max_value=100
    )
    order, order_error = parse_order_field(request.form.get('order'), s.order)
    length_error = validate_field_lengths((
        ('Skill name', name, 100),
        ('Skill category', category, 100),
    ))
    if error or order_error or length_error:
        flash(error or order_error or length_error, 'danger')
        return render_template(
            'admin/skills.html',
            skills=Skill.query.order_by(Skill.category, Skill.order).all(),
            form_data={},
            edit_skill=s,
            edit_form_data=request.form,
        ), 400
    s.name       = name
    s.category   = category
    s.proficiency = proficiency
    s.order      = order
    db.session.commit()
    flash('Skill updated!', 'success')
    return redirect(url_for('admin_skills'))


@app.route('/admin/skills/delete/<int:sid>', methods=['POST'])
@login_required
def admin_delete_skill(sid):
    s = Skill.query.get_or_404(sid)
    db.session.delete(s)
    db.session.commit()
    flash('Skill deleted.', 'success')
    return redirect(url_for('admin_skills'))


# ── Admin: Certifications ─────────────────────────────────────────────────────

@app.route('/admin/certifications')
@login_required
def admin_certifications():
    certs = Certification.query.order_by(Certification.order).all()
    return render_template('admin/certifications.html', certs=certs, form_data={})


@app.route('/admin/certifications/add', methods=['POST'])
@login_required
def admin_add_certification():
    title = request.form.get('title', '').strip()
    issuer = request.form.get('issuer', '').strip()
    order_raw = request.form.get('order', '').strip()
    certs = Certification.query.order_by(Certification.order).all()

    if not title or not issuer:
        flash('Certificate title and issuer are required.', 'danger')
        return render_template('admin/certifications.html', certs=certs, form_data=request.form)

    category = request.form.get('category', 'Technical').strip() or 'Technical'
    cert_url, url_error = validate_http_url(
        request.form.get('cert_url', '').strip(), 'Certificate URL'
    )
    issue_date = request.form.get('issue_date', '').strip()
    credential_id = request.form.get('credential_id', '').strip()
    length_error = validate_field_lengths((
        ('Certificate title', title, 300),
        ('Issuing organisation', issuer, 200),
        ('Category', category, 100),
        ('Issue date', issue_date, 50),
        ('Credential ID', credential_id, 200),
    ))
    order, order_error = parse_order_field(order_raw)
    if url_error or length_error or order_error:
        flash(url_error or length_error or order_error, 'danger')
        return render_template('admin/certifications.html', certs=certs, form_data=request.form)
    if order is None:
        max_order = db.session.query(db.func.max(Certification.order)).scalar()
        order = (max_order if max_order is not None else 0) + 1

    c = Certification(
        title=title,
        issuer=issuer,
        category=category,
        cert_url=cert_url,
        issue_date=issue_date,
        credential_id=credential_id,
        order=order,
    )
    db.session.add(c)
    db.session.commit()
    flash('Certification added!', 'success')
    return redirect(url_for('admin_certifications'))


@app.route('/admin/certifications/edit/<int:cid>', methods=['GET', 'POST'])
@login_required
def admin_edit_certification(cid):
    certification = Certification.query.get_or_404(cid)
    form_data = request.form if request.method == 'POST' else {}

    if request.method == 'POST':
        title = request.form.get('title', '').strip()
        issuer = request.form.get('issuer', '').strip()
        order_raw = request.form.get('order', '').strip()

        if not title or not issuer:
            flash('Certificate title and issuer are required.', 'danger')
            return render_template('admin/certification_form.html', certification=certification, form_data=form_data)

        category = request.form.get('category', 'Technical').strip() or 'Technical'
        cert_url, url_error = validate_http_url(
            request.form.get('cert_url', '').strip(), 'Certificate URL'
        )
        issue_date = request.form.get('issue_date', '').strip()
        credential_id = request.form.get('credential_id', '').strip()
        length_error = validate_field_lengths((
            ('Certificate title', title, 300),
            ('Issuing organisation', issuer, 200),
            ('Category', category, 100),
            ('Issue date', issue_date, 50),
            ('Credential ID', credential_id, 200),
        ))
        order, order_error = parse_order_field(order_raw, certification.order)
        if url_error or length_error or order_error:
            flash(url_error or length_error or order_error, 'danger')
            return render_template('admin/certification_form.html', certification=certification, form_data=form_data)

        certification.title = title
        certification.issuer = issuer
        certification.category = category
        certification.cert_url = cert_url
        certification.issue_date = issue_date
        certification.credential_id = credential_id
        certification.order = order
        db.session.commit()
        flash('Certification updated!', 'success')
        return redirect(url_for('admin_certifications'))

    return render_template('admin/certification_form.html', certification=certification, form_data=form_data)


@app.route('/admin/certifications/delete/<int:cid>', methods=['POST'])
@login_required
def admin_delete_certification(cid):
    c = Certification.query.get_or_404(cid)
    db.session.delete(c)
    db.session.commit()
    flash('Certification deleted.', 'success')
    return redirect(url_for('admin_certifications'))


# ── Admin: Achievements ───────────────────────────────────────────────────────

@app.route('/admin/achievements')
@login_required
def admin_achievements():
    achievements = Achievement.query.order_by(Achievement.order).all()
    return render_template('admin/achievements.html', achievements=achievements, form_data={})


@app.route('/admin/achievements/add', methods=['POST'])
@login_required
def admin_add_achievement():
    title = request.form.get('title', '').strip()
    order_raw = request.form.get('order', '').strip()
    achievements = Achievement.query.order_by(Achievement.order).all()

    if not title:
        flash('Achievement title is required.', 'danger')
        return render_template('admin/achievements.html', achievements=achievements, form_data=request.form)

    date = request.form.get('date', '').strip()
    icon = request.form.get('icon', '').strip() or 'fas fa-trophy'
    category = request.form.get('category', 'Leadership').strip() or 'Leadership'
    length_error = validate_field_lengths((
        ('Achievement title', title, 300),
        ('Achievement date', date, 50),
        ('Achievement icon', icon, 100),
        ('Achievement category', category, 100),
    ))
    order, order_error = parse_order_field(order_raw)
    if length_error or order_error:
        flash(length_error or order_error, 'danger')
        return render_template('admin/achievements.html', achievements=achievements, form_data=request.form)
    if order is None:
        max_order = db.session.query(db.func.max(Achievement.order)).scalar()
        order = (max_order if max_order is not None else 0) + 1

    a = Achievement(
        title=title,
        description=request.form.get('description', '').strip(),
        date=date,
        icon=icon,
        category=category,
        order=order,
    )
    db.session.add(a)
    db.session.commit()
    flash('Achievement added!', 'success')
    return redirect(url_for('admin_achievements'))


@app.route('/admin/achievements/edit/<int:aid>', methods=['GET', 'POST'])
@login_required
def admin_edit_achievement(aid):
    achievement = Achievement.query.get_or_404(aid)
    form_data = request.form if request.method == 'POST' else {}

    if request.method == 'POST':
        title = request.form.get('title', '').strip()
        order_raw = request.form.get('order', '').strip()

        if not title:
            flash('Achievement title is required.', 'danger')
            return render_template('admin/achievement_form.html', achievement=achievement, form_data=form_data)

        date = request.form.get('date', '').strip()
        icon = request.form.get('icon', '').strip() or 'fas fa-trophy'
        category = request.form.get('category', 'Leadership').strip() or 'Leadership'
        length_error = validate_field_lengths((
            ('Achievement title', title, 300),
            ('Achievement date', date, 50),
            ('Achievement icon', icon, 100),
            ('Achievement category', category, 100),
        ))
        order, order_error = parse_order_field(order_raw, achievement.order)
        if length_error or order_error:
            flash(length_error or order_error, 'danger')
            return render_template('admin/achievement_form.html', achievement=achievement, form_data=form_data)

        achievement.title = title
        achievement.description = request.form.get('description', '').strip()
        achievement.date = date
        achievement.icon = icon
        achievement.category = category
        achievement.order = order
        db.session.commit()
        flash('Achievement updated!', 'success')
        return redirect(url_for('admin_achievements'))

    return render_template('admin/achievement_form.html', achievement=achievement, form_data=form_data)


@app.route('/admin/achievements/delete/<int:aid>', methods=['POST'])
@login_required
def admin_delete_achievement(aid):
    a = Achievement.query.get_or_404(aid)
    db.session.delete(a)
    db.session.commit()
    flash('Achievement deleted.', 'success')
    return redirect(url_for('admin_achievements'))


# ── Admin: Research ───────────────────────────────────────────────────────────

@app.route('/admin/research')
@login_required
def admin_research():
    papers = Research.query.order_by(Research.order).all()
    return render_template('admin/research.html', papers=papers, form_data={})


@app.route('/admin/research/add', methods=['POST'])
@login_required
def admin_add_research():
    title = request.form.get('title', '').strip()
    journal = request.form.get('journal', '').strip()
    paper_url = request.form.get('paper_url', '').strip()
    order_raw = request.form.get('order', '').strip()
    papers = Research.query.order_by(Research.order).all()

    if not title or not journal:
        flash('Paper title and journal/conference are required.', 'danger')
        return render_template('admin/research.html', papers=papers, form_data=request.form)

    paper_url, url_error = validate_http_url(paper_url, 'Paper URL')
    pub_date = request.form.get('pub_date', '').strip()
    authors = request.form.get('authors', '').strip()
    keywords = request.form.get('keywords', '').strip()
    length_error = validate_field_lengths((
        ('Paper title', title, 500),
        ('Journal or conference', journal, 300),
        ('Publication date', pub_date, 50),
        ('Authors', authors, 500),
        ('Keywords', keywords, 300),
    ))
    order, order_error = parse_order_field(order_raw)
    if url_error or length_error or order_error:
        flash(url_error or length_error or order_error, 'danger')
        return render_template('admin/research.html', papers=papers, form_data=request.form)
    if order is None:
        max_order = db.session.query(db.func.max(Research.order)).scalar()
        order = (max_order if max_order is not None else 0) + 1

    r = Research(
        title=title,
        journal=journal,
        abstract=request.form.get('abstract', '').strip(),
        paper_url=paper_url,
        pub_date=pub_date,
        authors=authors,
        keywords=keywords,
        order=order,
    )
    db.session.add(r)
    db.session.commit()
    flash('Research paper added!', 'success')
    return redirect(url_for('admin_research'))


@app.route('/admin/research/edit/<int:rid>', methods=['GET', 'POST'])
@login_required
def admin_edit_research(rid):
    r = Research.query.get_or_404(rid)
    form_data = request.form if request.method == 'POST' else {}
    if request.method == 'POST':
        title = request.form.get('title', '').strip()
        journal = request.form.get('journal', '').strip()
        paper_url = request.form.get('paper_url', '').strip()
        order_raw = request.form.get('order', '').strip()

        if not title or not journal:
            flash('Paper title and journal/conference are required.', 'danger')
            return render_template('admin/research_form.html', paper=r, form_data=form_data)

        paper_url, url_error = validate_http_url(paper_url, 'Paper URL')
        pub_date = request.form.get('pub_date', '').strip()
        authors = request.form.get('authors', '').strip()
        keywords = request.form.get('keywords', '').strip()
        length_error = validate_field_lengths((
            ('Paper title', title, 500),
            ('Journal or conference', journal, 300),
            ('Publication date', pub_date, 50),
            ('Authors', authors, 500),
            ('Keywords', keywords, 300),
        ))
        order, order_error = parse_order_field(order_raw, r.order)
        if url_error or length_error or order_error:
            flash(url_error or length_error or order_error, 'danger')
            return render_template('admin/research_form.html', paper=r, form_data=form_data)

        r.title     = title
        r.journal   = journal
        r.abstract  = request.form.get('abstract', '').strip()
        r.paper_url = paper_url
        r.pub_date  = pub_date
        r.authors   = authors
        r.keywords  = keywords
        r.order     = order
        db.session.commit()
        flash('Research paper updated!', 'success')
        return redirect(url_for('admin_research'))
    return render_template('admin/research_form.html', paper=r, form_data=form_data)


@app.route('/admin/research/delete/<int:rid>', methods=['POST'])
@login_required
def admin_delete_research(rid):
    r = Research.query.get_or_404(rid)
    db.session.delete(r)
    db.session.commit()
    flash('Research paper deleted.', 'success')
    return redirect(url_for('admin_research'))


# ── Admin: Messages ───────────────────────────────────────────────────────────

@app.route('/admin/messages')
@login_required
def admin_messages():
    messages = Contact.query.order_by(Contact.created_at.desc()).all()
    return render_template('admin/messages.html', messages=messages)


@app.route('/admin/messages/<int:mid>/read', methods=['POST'])
@login_required
def admin_mark_message_read(mid):
    message = Contact.query.get_or_404(mid)
    message.is_read = True
    db.session.commit()
    flash('Message marked as read.', 'success')
    return redirect(url_for('admin_messages'))


@app.route('/admin/messages/<int:mid>/unread', methods=['POST'])
@login_required
def admin_mark_message_unread(mid):
    message = Contact.query.get_or_404(mid)
    message.is_read = False
    db.session.commit()
    flash('Message marked as unread.', 'success')
    return redirect(url_for('admin_messages'))


@app.route('/admin/messages/delete/<int:mid>', methods=['POST'])
@login_required
def admin_delete_message(mid):
    m = Contact.query.get_or_404(mid)
    db.session.delete(m)
    db.session.commit()
    flash('Message deleted.', 'success')
    return redirect(url_for('admin_messages'))


# ── Admin: Social Links ───────────────────────────────────────────────────────

@app.route('/admin/social', methods=['GET', 'POST'])
@login_required
def admin_social():
    if request.method == 'POST':
        action = request.form.get('action')
        if action == 'add':
            platform = request.form.get('platform', '').strip()
            url = request.form.get('url', '').strip()
            order_raw = request.form.get('order', '').strip()
            icon = request.form.get('icon', '').strip() or 'fab fa-link'
            links = SocialLink.query.order_by(SocialLink.order).all()

            if not platform:
                flash('Platform name is required.', 'danger')
                return render_template('admin/social.html', links=links, form_data=request.form)

            url, url_error = validate_http_url(url, 'Social URL')
            length_error = validate_field_lengths((
                ('Platform name', platform, 50),
                ('Social icon', icon, 100),
            ))
            order, order_error = parse_order_field(order_raw)
            if not url or url_error or length_error or order_error:
                flash(url_error or length_error or order_error or 'Please enter a valid HTTP or HTTPS URL.', 'danger')
                return render_template('admin/social.html', links=links, form_data=request.form)

            if order is None:
                max_order = db.session.query(db.func.max(SocialLink.order)).scalar()
                order = (max_order if max_order is not None else 0) + 1

            s = SocialLink(
                platform=platform,
                url=url,
                icon=icon,
                order=order,
                is_active=request.form.get('is_active', '1') == '1',
            )
            db.session.add(s)
            flash('Social link added!', 'success')
        elif action == 'delete':
            sid, error = parse_integer_field(request.form.get('id'), 'Social link ID', min_value=1)
            if error or sid is None:
                flash(error or 'A valid social link ID is required.', 'danger')
                return redirect(url_for('admin_social'))
            s = SocialLink.query.get_or_404(sid)
            db.session.delete(s)
            flash('Social link deleted.', 'success')
        db.session.commit()
        return redirect(url_for('admin_social'))
    links = SocialLink.query.order_by(SocialLink.order).all()
    return render_template('admin/social.html', links=links, form_data={})


@app.route('/admin/social/edit/<int:sid>', methods=['GET', 'POST'])
@login_required
def admin_edit_social(sid):
    social_link = SocialLink.query.get_or_404(sid)
    form_data = request.form if request.method == 'POST' else {}

    if request.method == 'POST':
        platform = request.form.get('platform', '').strip()
        url = request.form.get('url', '').strip()
        order_raw = request.form.get('order', '').strip()
        icon = request.form.get('icon', '').strip() or 'fab fa-link'

        if not platform:
            flash('Platform name is required.', 'danger')
            return render_template('admin/social_form.html', social_link=social_link, form_data=form_data)

        url, url_error = validate_http_url(url, 'Social URL')
        length_error = validate_field_lengths((
            ('Platform name', platform, 50),
            ('Social icon', icon, 100),
        ))
        order, order_error = parse_order_field(order_raw, social_link.order)
        if not url or url_error or length_error or order_error:
            flash(url_error or length_error or order_error or 'Please enter a valid HTTP or HTTPS URL.', 'danger')
            return render_template('admin/social_form.html', social_link=social_link, form_data=form_data)

        social_link.platform = platform
        social_link.url = url
        social_link.icon = icon
        social_link.order = order
        social_link.is_active = request.form.get('is_active') == '1'
        db.session.commit()
        flash('Social link updated!', 'success')
        return redirect(url_for('admin_social'))

    return render_template('admin/social_form.html', social_link=social_link, form_data=form_data)


# ── Admin: Experience ─────────────────────────────────────────────────────────

@app.route('/admin/experience')
@login_required
def admin_experience():
    experiences = Experience.query.order_by(Experience.order).all()
    return render_template('admin/experience.html', experiences=experiences, form_data={})


@app.route('/admin/experience/add', methods=['POST'])
@login_required
def admin_add_experience():
    title = request.form.get('title', '').strip()
    company = request.form.get('company', '').strip()
    location = request.form.get('location', '').strip()
    start_date = request.form.get('start_date', '').strip()
    end_date = request.form.get('end_date', '').strip()
    emp_type = request.form.get('emp_type', '').strip()
    technologies = request.form.get('technologies', '').strip()
    order_raw = request.form.get('order', '').strip()
    experiences = Experience.query.order_by(Experience.order).all()

    if not title or not company:
        flash('Job title and company are required.', 'danger')
        return render_template('admin/experience.html', experiences=experiences, form_data=request.form)

    length_error = validate_field_lengths((
        ('Job title', title, 200),
        ('Company', company, 200),
        ('Location', location, 200),
        ('Start date', start_date, 50),
        ('End date', end_date, 50),
        ('Employment type', emp_type, 100),
        ('Technologies', technologies, 500),
    ))
    order, order_error = parse_order_field(order_raw)
    if length_error or order_error:
        flash(length_error or order_error, 'danger')
        return render_template('admin/experience.html', experiences=experiences, form_data=request.form)

    if order is None:
        max_order = db.session.query(db.func.max(Experience.order)).scalar()
        order = (max_order if max_order is not None else 0) + 1

    resp_raw = request.form.get('responsibilities', '')
    resp_list = [r.strip() for r in resp_raw.split('\n') if r.strip()]
    e = Experience(
        title=title,
        company=company,
        location=location,
        start_date=start_date,
        end_date=end_date,
        emp_type=emp_type,
        technologies=technologies,
        responsibilities=json.dumps(resp_list),
        order=order,
        is_current=bool(request.form.get('is_current')),
    )
    db.session.add(e)
    db.session.commit()
    flash('Experience added!', 'success')
    return redirect(url_for('admin_experience'))


@app.route('/admin/experience/edit/<int:eid>', methods=['GET', 'POST'])
@login_required
def admin_edit_experience(eid):
    experience = Experience.query.get_or_404(eid)
    form_data = request.form if request.method == 'POST' else {}

    if request.method == 'POST':
        title = request.form.get('title', '').strip()
        company = request.form.get('company', '').strip()
        location = request.form.get('location', '').strip()
        start_date = request.form.get('start_date', '').strip()
        end_date = request.form.get('end_date', '').strip()
        emp_type = request.form.get('emp_type', '').strip()
        technologies = request.form.get('technologies', '').strip()
        order_raw = request.form.get('order', '').strip()

        if not title or not company:
            flash('Job title and company are required.', 'danger')
            return render_template('admin/experience_form.html', experience=experience, form_data=form_data)

        length_error = validate_field_lengths((
            ('Job title', title, 200),
            ('Company', company, 200),
            ('Location', location, 200),
            ('Start date', start_date, 50),
            ('End date', end_date, 50),
            ('Employment type', emp_type, 100),
            ('Technologies', technologies, 500),
        ))
        order, order_error = parse_order_field(order_raw, experience.order)
        if length_error or order_error:
            flash(length_error or order_error, 'danger')
            return render_template('admin/experience_form.html', experience=experience, form_data=form_data)

        resp_raw = request.form.get('responsibilities', '')
        resp_list = [r.strip() for r in resp_raw.split('\n') if r.strip()]
        experience.title = title
        experience.company = company
        experience.location = location
        experience.start_date = start_date
        experience.end_date = end_date
        experience.emp_type = emp_type
        experience.technologies = technologies
        experience.responsibilities = json.dumps(resp_list)
        experience.order = order
        experience.is_current = bool(request.form.get('is_current'))
        db.session.commit()
        flash('Experience updated!', 'success')
        return redirect(url_for('admin_experience'))

    return render_template('admin/experience_form.html', experience=experience, form_data=form_data)


@app.route('/admin/experience/delete/<int:eid>', methods=['POST'])
@login_required
def admin_delete_experience(eid):
    e = Experience.query.get_or_404(eid)
    db.session.delete(e)
    db.session.commit()
    flash('Experience deleted.', 'success')
    return redirect(url_for('admin_experience'))


# ─── Error Handlers ───────────────────────────────────────────────────────────

@app.errorhandler(404)
def page_not_found(e):
    return render_template('404.html'), 404


@app.errorhandler(500)
def server_error(e):
    return render_template('500.html'), 500


@app.errorhandler(CSRFError)
def handle_csrf_error(e):
    if request.path == '/contact':
        return jsonify({'success': False, 'message': 'Invalid or missing CSRF token.'}), 400
    return 'Invalid or missing CSRF token.', 400


# ─── App Initialization ───────────────────────────────────────────────────────

with app.app_context():
    initialize_database()

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=os.environ.get('FLASK_DEBUG', '0') == '1')
