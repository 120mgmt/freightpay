# FreightPay

> Professional payroll and payout management system for trucking companies and small businesses

## Overview

FreightPay is a web-based SaaS application designed for trucking companies and owner-operators to manage payroll, calculate mileage-based pay, generate tax forms, and process payments seamlessly.

### Key Features

- **Multi-mode Pay Calculations**: Per-mile, hourly, flat-rate, stop pay, detention, and bonuses
- **Automated Payroll**: Weekly/bi-weekly cycles with deductions and advances
- **Tax Forms**: 1099-NEC, 1096, W-2 generation with per-form pricing
- **Payment Processing**: Stripe integration for billing and payouts
- **Notifications**: Email and SMS alerts for payroll events
- **Role-based Access**: Separate dashboards for admins and drivers

## Technology Stack

- **Backend**: Python 3.9+, Flask
- **Database**: PostgreSQL / SQLite
- **Payment**: Stripe API
- **Email**: SendGrid / SMTP
- **SMS**: Twilio
- **Frontend**: HTML, CSS, JavaScript (Jinja2 templates)

## Project Structure

```
FreightPay/
│
├── app.py                      # Main Flask application
├── config.py                   # Configuration settings
├── requirements.txt            # Python dependencies
├── README.md
│
├── billing/
│   ├── stripe_config.py        # Stripe API configuration
│   ├── invoices.py             # Invoice generation
│   └── subscription_plans.py   # Subscription tier management
│
├── payroll/
│   ├── payroll_engine.py       # Core payroll processing
│   ├── pay_calculations.py     # Pay calculation logic
│   ├── driver_miles_pay.py     # Mileage-based pay handler
│   ├── forms_1099.py           # 1099-NEC generation
│   ├── forms_w2.py             # W-2 generation
│   └── annual_1096.py          # 1096 summary form
│
├── notifications/
│   ├── email_service.py        # Email notification handler
│   └── sms_service.py          # SMS notification handler
│
├── templates/
│   ├── home.html               # Landing page
│   ├── dashboard.html          # Admin dashboard
│   ├── payroll_run.html        # Payroll processing interface
│   ├── billing.html            # Billing & subscription page
│   ├── login.html              # Login page
│   └── register.html           # Company registration
│
└── utils/
    ├── database.py             # Database connection & models
    ├── logger.py               # Application logging
    └── authentication.py       # User authentication & authorization
```

## Quick Start

### Prerequisites

- Python 3.9 or higher
- PostgreSQL (or SQLite for development)
- Stripe account
- SendGrid and Twilio accounts (for notifications)

### Installation

```bash
# Clone the repository
git clone https://github.com/yourusername/freightpay.git
cd freightpay

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Set up environment variables
cp .env.example .env
# Edit .env with your API keys and database credentials

# Initialize database
python -m utils.database init

# Run the application
python app.py
```

The application will be available at `http://localhost:5000`

## Configuration

Create a `.env` file in the root directory:

```env
# Flask
FLASK_ENV=development
SECRET_KEY=your-secret-key-here

# Database
DATABASE_URL=postgresql://user:password@localhost:5432/freightpay

# Stripe
STRIPE_SECRET_KEY=sk_test_your_stripe_secret_key
STRIPE_PUBLISHABLE_KEY=pk_test_your_stripe_publishable_key

# SendGrid
SENDGRID_API_KEY=your_sendgrid_api_key
FROM_EMAIL=noreply@freightpay.com

# Twilio
TWILIO_ACCOUNT_SID=your_twilio_account_sid
TWILIO_AUTH_TOKEN=your_twilio_auth_token
TWILIO_PHONE_NUMBER=+1234567890

# Tax Form Pricing (in cents)
PRICE_1099_FORM=2900
PRICE_1096_FORM=1500
PRICE_W2_FORM=2500
```

## Core Modules

### Payroll Engine (`payroll/payroll_engine.py`)

Handles complete payroll processing workflow:
- Driver pay calculation (mileage, hourly, flat-rate)
- Deductions and bonuses
- Payroll period management
- Pay stub generation

### Pay Calculations (`payroll/pay_calculations.py`)

Supports multiple pay structures:
- **Per-mile**: `miles × rate`
- **Hourly**: `hours × hourly_rate`
- **Stop pay**: `stops × stop_rate`
- **Detention**: `detention_hours × detention_rate`
- **Mixed compensation**: Combination of above

### Tax Forms (`payroll/forms_*.py`)

Automated IRS-compliant form generation:
- `forms_1099.py`: 1099-NEC for contractors ($29/form)
- `forms_w2.py`: W-2 for employees ($25/form)
- `annual_1096.py`: Annual summary transmittal ($15/form)

### Billing (`billing/`)

Stripe-powered subscription and payment processing:
- Tiered subscription plans
- Usage-based tax form billing
- Invoice generation and tracking

### Notifications (`notifications/`)

Multi-channel communication system:
- Email: Pay stubs, payroll confirmations, alerts
- SMS: Payment confirmations, critical updates

## Usage Example

```python
from payroll.payroll_engine import PayrollEngine
from payroll.pay_calculations import calculate_driver_pay

# Initialize payroll for a period
engine = PayrollEngine(company_id="abc-123")
period = engine.create_period(
    start_date="2025-01-01",
    end_date="2025-01-07",
    pay_date="2025-01-10"
)

# Calculate driver pay
pay_data = {
    "driver_id": "driver-456",
    "miles": 2500,
    "hours": 50,
    "stops": 12,
    "detention_hours": 3,
    "per_mile_rate": 0.55,
    "hourly_rate": 25.00,
    "stop_pay": 15.00,
    "detention_rate": 20.00
}

gross_pay = calculate_driver_pay(pay_data)
# Returns: 1940.00 (miles: $1375 + stops: $180 + detention: $60 + hours: $1250)

# Process payroll
engine.process_payroll(period_id=period.id)
```

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/api/auth/register` | Register new company |
| `POST` | `/api/auth/login` | User login |
| `GET` | `/api/drivers` | List all drivers |
| `POST` | `/api/drivers` | Add new driver |
| `POST` | `/api/payroll/periods` | Create payroll period |
| `POST` | `/api/payroll/entries` | Add driver pay entry |
| `POST` | `/api/payroll/process` | Process payroll |
| `POST` | `/api/tax-forms/1099` | Generate 1099 forms |
| `GET` | `/api/reports/payroll` | Payroll summary report |

## Database Schema

**Core Tables:**
- `companies`: Company profiles and settings
- `users`: Admin and driver accounts
- `drivers`: Driver details and pay rules
- `payroll_periods`: Pay period definitions
- `payroll_entries`: Individual pay calculations
- `tax_forms`: Generated tax documents
- `transactions`: Payment records

## Testing

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=. --cov-report=html

# Run specific test module
pytest tests/test_payroll_engine.py
```

## Deployment

### Docker

```bash
docker build -t freightpay:latest .
docker run -p 5000:5000 freightpay:latest
```

### Heroku

```bash
heroku create freightpay-app
heroku addons:create heroku-postgresql:standard-0
git push heroku main
heroku run python -m utils.database init
```

## Security

- JWT-based authentication
- Bcrypt password hashing
- AES-256 encryption for sensitive data (SSN, bank info)
- SQL injection protection via parameterized queries
- HTTPS required in production
- Rate limiting on API endpoints

## User Roles

**Admin/Owner**
- Manage company profile
- Add/edit drivers and contractors
- Configure pay rules
- Run payroll and generate reports
- Download tax forms

**Driver/Contractor**
- View pay statements
- Download pay stubs
- Track mileage and earnings

## License

MIT License - see [LICENSE](LICENSE) file

## Support

- **Documentation**: [docs.freightpay.com](https://docs.freightpay.com)
- **Email**: support@freightpay.com
- **Issues**: [GitHub Issues](https://github.com/yourusername/freightpay/issues)

## Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/new-feature`)
3. Commit changes (`git commit -m 'Add new feature'`)
4. Push to branch (`git push origin feature/new-feature`)
5. Open a Pull Request

---

Built with ❤️ for the trucking industry
