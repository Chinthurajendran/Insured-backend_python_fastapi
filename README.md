# Insured Pulse - Backend

This is the backend API for the Insured Pulse application, built with **Python FastAPI**. It provides RESTful endpoints to manage insurance policies, user authentication, and other business logic. The backend is Dockerized for easy deployment and development.

---

## 🚀 Getting Started

### Prerequisites

- Python 3.9+
- Docker & Docker Compose installed
- (Optional) Virtual environment tool like `venv` or `virtualenv`

### Installation

Clone the repository:

```bash
git clone https://github.com/Chinthurajendran/insured-pulse-backend.git
cd insured-pulse-backend
````

### Running Locally (without Docker)

(Optional) Create and activate a virtual environment:

```bash
python -m venv venv
source venv/bin/activate  # On Windows use `venv\Scripts\activate`
```

Install dependencies:

```bash
pip install -r requirements.txt
```

Run the FastAPI server:

```bash
uvicorn app.main:app --reload
```

The API will be available at [http://localhost:8000](http://localhost:8000).

---

### Running with Docker

Build and run the Docker container using Docker Compose:

```bash
docker-compose up --build
```

This will start the backend server at [http://localhost:8000](http://localhost:8000).

To stop the containers:

```bash
docker-compose down
```

---

## 🧩 Features

* User registration and authentication (JWT)
* Insurance policy management (CRUD operations)
* Secure API endpoints with OAuth2
* Database integration with PostgreSQL (or your choice)
* Swagger UI documentation at `/docs`
* Health check endpoints

---

## 🛠️ Technologies Used

* Python 3.9+
* FastAPI
* Pydantic for data validation
* SQLAlchemy or Tortoise ORM (whichever you use)
* PostgreSQL (or other relational DB)
* Docker & Docker Compose

---

## ⚙️ Environment Variables

Create a `.env` file in the root directory with the following variables:

```env
DATABASE_URL=postgresql://user:password@db:5432/insuredpulse
SECRET_KEY=your_secret_key_here
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=30
```

Adjust these according to your setup.

---

## 📄 API Documentation

Once the server is running, API docs are available at:

* Swagger UI: [http://localhost:8000/docs](http://localhost:8000/docs)
* ReDoc: [http://localhost:8000/redoc](http://localhost:8000/redoc)

---

## 📤 Deployment

You can deploy the Dockerized backend on platforms like:

* AWS ECS / EKS
* DigitalOcean Droplets with Docker
* Azure Container Instances
* Heroku (with Docker support)

---

## 🤝 Contributing

Contributions are welcome! Feel free to fork the repo, make changes, and open a pull request.

---

## 📄 License

This project is licensed under the MIT License.

---

## 📬 Contact

Chinthu Rajendran
🔗 [GitHub Profile](https://github.com/Chinthurajendran)

```

If you want, I can also generate a ready-to-use `README.md` file for you to upload directly. Just ask!
```
