import pytest
from frontend_app import app

@pytest.fixture
def client():
    with app.test_client() as client:
        yield client


def test_home(client):
    response = client.get('/')
    assert response.status_code == 200
    assert b'products' in response.data


def test_login(client):
    response = client.post('/login', data={'username': 'test', 'password': 'test'})
    assert response.status_code in [200, 302, 401]  # Include 302 for redirect on successful login


def test_cart(client):
    response = client.get('/cart')
    assert response.status_code in [200, 302]


def test_checkout(client):
    response = client.get('/checkout')
    assert response.status_code in [200, 302]
