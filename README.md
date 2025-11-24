# Bookworm Library Management System

Bookworm is a modern, full-featured web application designed to streamline library operations. It provides a robust platform for librarians to manage their collection and patrons, while offering members a user-friendly dashboard to track their loans and fines.

## Features

### For Librarians (Command Center)
*   **Dashboard**: Real-time overview of library statistics, including total books, active loans, and outstanding fines.
*   **Book Management**: Add, edit, and organize books with details like ISBN, genre, and author.
*   **Member Management**: Register new members and view detailed borrowing history.
*   **Circulation**: Streamlined "Check-Out" and "Return" processes.
*   **Fine System**: Automatic calculation of late fees upon return.
*   **Debt Collection**: View top debtors and send professional HTML email reminders with a single click.

### For Members
*   **Personal Dashboard**: View current loans and due dates.
*   **Fine Status**: Check outstanding balances.
*   **Online Payments**: Securely pay fines using the integrated **Stripe** payment gateway.
*   **Catalog Search**: Search for books by title or author.

## Tech Stack

*   **Backend**: Django 5.2.8 (Python)
*   **Database**: MySQL
*   **Frontend**: HTML5, CSS3, Django Templates
*   **Payment Processing**: Stripe API
*   **Email Service**: SMTP (with HTML templates)
*   **Environment Management**: python-dotenv

## Installation & Setup

### Prerequisites
*   Python 3.10+
*   MySQL Server

### 1. Clone the Repository
```bash
git clone https://github.com/yourusername/bookworm-app.git
cd bookworm-app
```

### 2. Create and Activate Virtual Environment
```bash
# Windows
python -m venv .venv
.venv\Scripts\activate

# Mac/Linux
python3 -m venv .venv
source .venv/bin/activate
```

### 3. Install Dependencies
```bash
pip install -r requirements.txt
```

### 4. Configure Environment Variables
Create a `.env` file in the root directory and add the following configuration:

```ini
# Django Security
SECRET_KEY=your_django_secret_key
DEBUG=True

# Database Configuration
DB_NAME=bookworm_database
DB_USER=root
DB_PASSWORD=your_mysql_password
DB_HOST=localhost
DB_PORT=3306

# Email Configuration (SMTP)
EMAIL_HOST_USER=your_email@gmail.com
EMAIL_HOST_PASSWORD=your_app_password

# Stripe Configuration
STRIPE_PUBLISHABLE_KEY=your_stripe_publishable_key
STRIPE_SECRET_KEY=your_stripe_secret_key
```

### 5. Database Setup
Make sure your MySQL server is running and you have created a database named `bookworm_database`.

```bash
python manage.py migrate
```

### 6. Create a Librarian Account (Superuser)
```bash
python manage.py createsuperuser
```

### 7. Run the Server
```bash
python manage.py runserver
```

Visit `http://127.0.0.1:8000/` in your browser.

## Email Notifications
The application uses SMTP to send email reminders. For Gmail, ensure you have "2-Step Verification" enabled and generate an **App Password** to use as the `EMAIL_HOST_PASSWORD`.

## Stripe Integration
To test payments, use the Stripe Test Card numbers (e.g., `4242 4242 4242 4242`) with any future expiration date and any CVC.
