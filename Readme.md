# News Site – A Blogging Platform With Subscription Monetization

A full-featured blogging and content-publishing platform that supports monetization through premium subscriptions.
The system is built with Django REST Framework on the backend and Vue.js 3 on the frontend, with seamless Stripe integration for handling payments.

## 🚀 Key Features
### For Regular Users

User registration & JWT authentication
Profile management (update details, password change)
Create and edit blog posts using a rich text editor, image uploads
Nested comment threads with reply support
Categories & topic-based browsing
Advanced search & filtering across posts and comments

### Premium (Subscription) Features

Pinning important posts to keep them on top of the feed
Priority ranking for premium user content
Content analytics dashboard for authors

### Admin Tools

Content moderation (posts, comments)
User management with permission levels
Payment analytics and subscription insights
Stripe webhook processing for automated billing updates

## 🛠 Technology Stack

### Backend

Django 5.2 – main backend framework
Django REST Framework – API layer
PostgreSQL – primary relational database
Redis – caching + task queues
Celery – background tasks
Stripe API – subscription billing

### Frontend

Vue.js 3 – frontend application
Pinia – state management
Vue Router – routing
Tailwind CSS – UI styling
Axios – REST API client

### DevOps

Docker / Docker Compose – containerized environment
Nginx – reverse proxy & static file delivery
Gunicorn – WSGI server for Django
Let's Encrypt SSL – HTTPS certificates

## 📁 Project Structure
```
news-site/
├── backend/                  # Django backend
│   ├── apps/
│   │   ├── accounts/         # Auth & user profiles
│   │   ├── main/             # Posts, categories
│   │   ├── comments/         # Nested commenting system
│   │   ├── subscribe/        # Subscription & premium logic
│   │   └── payment/          # Stripe billing
│   ├── config/               # Django settings
│   └── manage.py
├── frontend/                 # Vue.js SPA
│   ├── src/
│   │   ├── components/
│   │   ├── views/
│   │   ├── stores/
│   │   ├── router/
│   │   └── services/
├── docker-compose.yml
├── nginx.conf
└── .env
```
## 🎯 Core Data Models
### User

Custom Django user model
Avatar, bio, extended profile settings
JWT-based authentication

### Post

Title, content, images, status (draft/published)
View and comment counters
SEO-friendly slugs

### Comment

Multi-level threaded comments
Soft deletion
Moderation tools
### Subscription

Pricing plans with different privileges
Automatic renewals
Stripe billing integration

### Payment

Complete transaction history
Real-time webhook syncing
Refunds and payment error handling

## 🔧 API Endpoints
### Authentication

```
POST /api/v1/auth/register/
POST /api/v1/auth/login/
POST /api/v1/auth/logout/
GET  /api/v1/auth/profile/
PUT  /api/v1/auth/profile/
POST /api/v1/auth/token/refresh/
```

### Posts & Categories
GET  /api/v1/posts/
POST /api/v1/posts/
GET  /api/v1/posts/{slug}/
PUT  /api/v1/posts/{slug}/
GET  /api/v1/posts/popular/
GET  /api/v1/posts/categories/

### Comments
GET  /api/v1/comments/
POST /api/v1/comments/
GET  /api/v1/comments/post/{id}/
GET  /api/v1/comments/{id}/replies/

### Subscriptions & Payments
GET  /api/v1/subscribe/plans/
GET  /api/v1/subscribe/status/
POST /api/v1/subscribe/pin-post/
POST /api/v1/payment/create-checkout-session/

## 🌟 Architecture Highlights
### Pinned Posts System

Available only to active subscribers
Real-time subscription validation
Smart sorting that prioritizes pinned items

### Payment Flow

Stripe Checkout for secure payments
Webhook listeners for subscription updates
Automatic retries for failed charges

### Performance

Heavy use of caching (Redis)
SQL optimization via select_related & prefetch_related
Pagination for all list endpoints

### Security

Short-lived JWT access tokens + refresh tokens
CORS protections for frontend consumption
Input sanitization
API rate limiting

### 💾 Database Overview

Key PostgreSQL tables include:

users
posts
categories
comments
subscriptions
subscription_plans
payments
pinned_posts

### 🔄 Background Tasks (Celery)

- Subscription expiration checks (hourly)
- Renewal reminders (daily)
- Cleanup of outdated payment logs (weekly)
- Stripe webhook processing
- Auto-generation of analytical reports

## 🚀 Deployment Guide
### Requirements

Docker & Docker Compose
Domain + SSL
Active Stripe account
Quick Start
Clone the repository
Create .env based on .env.example
Add Stripe API keys & webhook secret
Run: docker-compose up -d
App auto-applies migrations and builds static files
Nginx Setup
HTTP → HTTPS redirection
Gzip compression for faster delivery
Caching for media & static assets
API request rate limiting
Proxy to Django + Vue services

### 📊 Monitoring & Logging

Nginx access/error logs
Django application logs
Celery worker logs
Stripe webhook logs for billing debugging

### 🧪 API Testing

Included Postman collection with:
All endpoints covered
Auth token auto-handling
Validation of payloads and responses
Testing of edge cases and error scenarios
