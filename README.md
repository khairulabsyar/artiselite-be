# Artiselite Backend

A production-grade Warehouse Management System (WMS) backend built with Django and PostgreSQL.

## Features

### 1. Inventory Management
- **Product Management**: CRUD operations for products with fields:
  - Name, SKU, tags, description, category, and quantity
- **Real-time Inventory Tracking**
  - Audit logs for all inventory changes
  - Low stock alerts with configurable thresholds
- **Advanced Search & Filtering**
  - Search by keyword, tag, category, or SKU
- **Bulk Operations**
  - Import/export inventory via CSV/XLSX

### 2. Inbound Management
- Track incoming stock with detailed information
- Associate with supplier records
- Support for file attachments (invoices, delivery orders)
- Bulk upload capability via CSV/XLSX
- Automatic inventory updates

### 3. Outbound Management
- Record outbound transactions
- Prevent negative stock dispatches
- Support for file attachments (signed DOs)
- Bulk operations via CSV/XLSX
- Real-time inventory deduction

### 4. User & Role Management
- **Authentication**: JWT-based authentication
- **Role-based Access Control**:
  - Admin: Full system access
  - Manager: Operational oversight
  - Operator: Basic transaction handling
- **Activity Logging**: Track all user actions
- **Granular Permissions**: Fine-grained access control

### 5. Dashboard & Analytics
- Real-time inventory metrics
- Transaction volume tracking
- Low stock alerts and reporting
- Activity monitoring

## Tech Stack

- **Backend**: Django REST Framework
- **Database**: PostgreSQL
- **Authentication**: JWT
- **Containerization**: Docker
- **Deployment**: AWS EC2
- **Frontend**: [artiselite-fe](https://github.com/khairulabsyar/artiselite-fe) (React + Tailwind CSS)

## Getting Started

### Prerequisites

- Python 3.9+
- PostgreSQL 13+
- pip

### Installation

1. Clone the repository:
   ```bash
   git clone https://github.com/khairulabsyar/artiselite-be.git
   cd artiselite-be
   ```

2. Create and activate a virtual environment:
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

4. Set up environment variables:
   ```bash
   cp .env.example .env
   # Edit .env with your configuration
   ```

5. Run migrations:
   ```bash
   python manage.py migrate
   ```

6. Create a superuser (for admin access):
   ```bash
   python manage.py createsuperuser
   ```

7. Start the development server:
   ```bash
   python manage.py runserver
   ```

## API Documentation

API documentation is available at `/api/docs/` when running the development server.

## Development

### Running Tests
```bash
python manage.py test
```

### Code Style
This project follows PEP 8 style guidelines. Before committing, please run:
```bash
black .
flake8
```

## Deployment

### Docker Setup
```bash
docker-compose up --build
```

### Production Deployment
1. Set up environment variables in production
2. Run migrations
3. Collect static files
4. Configure a production-ready WSGI server (e.g., Gunicorn with Nginx)

## Contributing

1. Fork the repository
2. Create your feature branch (`git checkout -b feature/AmazingFeature`)
3. Commit your changes (`git commit -m 'Add some AmazingFeature'`)
4. Push to the branch (`git push origin feature/AmazingFeature`)
5. Open a Pull Request

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.
