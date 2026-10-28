# Kasi2Kasi

**Version:** v0.5 development
**Status:** Automated test suite passing; production release gates remain.

Kasi2Kasi is a community-focused transport and delivery platform being developed to support communities where conventional ride-hailing services may be unavailable.

The project is designed around customer ride requests, approved drivers, dispatch, journey tracking, transparent fares and driver sustainability.

## Current capabilities

The current implementation includes:

- Customer and driver accounts with role-based access.
- Driver approval and vehicle management.
- Driver availability and ride assignment.
- Ride requests, booking status management and pickup confirmation.
- GPS location updates and customer tracking.
- Driver navigation and journey estimates.
- Pickup and destination address lookup where the service is available.
- Configurable fare estimates, driver fare proposals and customer fare confirmation.
- Driver operating-cost and sustainability calculations.
- Administrative tools and automated tests.

These features have been implemented in the development codebase. Their presence does not, by itself, establish production readiness or guarantee availability in every deployment environment.

## Technology

- Python
- Django 6.1.2
- SQLite for local development
- Pillow
- HTML, CSS and JavaScript
- OpenStreetMap map tiles and OSRM routing integration

Pinned Python dependencies are listed in `requirements.txt`.

## Windows development setup

Run these commands in PowerShell from the project directory.

### 1. Create and activate the virtual environment

If the project virtual environment already exists, skip creation.

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
2. Install dependencies
python -m pip install -r requirements.txt
3. Configure environment variables

Review .env.example and configure the required environment variables for your chosen environment.

Important:

DJANGO_SECRET_KEY must be a unique, strong secret.
DJANGO_DEBUG should be enabled only for local development.
DJANGO_ALLOWED_HOSTS must match the hosts used by the environment.
The project settings read environment variables. Creating a .env file alone does not guarantee that Django loads it; use an explicitly configured environment-loading method or set the variables in the process environment.
Never commit secrets or real credentials.

The example template uses local-development defaults. Do not copy those defaults into a production deployment without reviewing them.

4. Apply database migrations
python manage.py migrate
5. Run Django's configuration check
python manage.py check
6. Start the development server
python manage.py runserver

The default local address is http://127.0.0.1:8000/.

Use the Django development server only for local development, not as the production hosting solution.

Automated tests

Run the complete test suite with:

python manage.py test --verbosity 1

At the time this README was prepared, the developer reported that 272 tests passed. This is a recorded development result, not a guarantee that all future revisions will pass.

Run the tests again after relevant code changes.

Fare configuration

The fare engine supports configurable components:

Base fare
Rate per kilometre
Rate per minute

The corresponding environment variables are:

KASI2KASI_BASE_FARE
KASI2KASI_RATE_PER_KM
KASI2KASI_RATE_PER_MINUTE

Actual fare amounts have not yet been approved. Keep these values unset until operating costs and local market prices have been assessed.

Do not invent rates or present test fixtures as real prices.

The intended pricing approach is transparent and cost-aware, with community-friendly rates where sustainable. Any after-hours adjustments must follow explicit rules and be disclosed before confirmation.

Estimated, driver-proposed and customer-agreed fares must remain distinct.

Payment processing is outside the current v0.5 scope.

Maps and external services

Map tiles, routing and address lookup depend on external services and network connectivity. Availability, accuracy and service limits may vary.

Review the applicable service terms and operational requirements before public deployment. Do not assume that a successful local map test guarantees uninterrupted service.

Production security checklist

Before an internet-facing deployment:

Set DJANGO_DEBUG=False.
Set DJANGO_ALLOWED_HOSTS to the actual deployment hosts.
Generate and protect a unique production DJANGO_SECRET_KEY.
Configure HTTPS at the application server or trusted reverse proxy.
Enable secure session and CSRF cookies for HTTPS.
Configure HSTS deliberately after HTTPS has been verified.
Configure trusted origins and proxy-related settings where required by the deployment.
Run python manage.py check --deploy and address applicable warnings.
Configure production static-file serving, database operations, backups, logging and error monitoring.
Review account security, permissions, privacy and handling of location data.
Verify the customer-to-driver journey in a controlled acceptance environment.

Do not enable HTTPS redirection or HSTS blindly in a local HTTP development environment.

Current release limitations
Actual fare rates remain undecided.
Production hosting and its security configuration must be completed and verified.
Automated tests do not replace real-world acceptance testing.
Payment processing is not included in v0.5.
External mapping and routing services may be unavailable or return imperfect estimates.
Project structure
accounts/ — accounts, driver-related functionality and account views.
bookings/ — ride booking, fare calculation, dispatch, tracking and journey-related functionality.
config/ — Django project configuration.
templates/ — HTML templates.
static/ — static assets such as CSS.
media/ — local media uploads.
manage.py — Django management entry point.
requirements.txt — pinned Python dependencies.
.env.example — example environment-variable template.
Development principle

Kasi2Kasi prioritizes safety, transparent fares, reliable ride workflows and sustainable driver earnings. Production readiness must be established through configuration review, controlled acceptance testing and operational planning—not inferred from automated test results alone.