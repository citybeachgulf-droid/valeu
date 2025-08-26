from app import app

with app.app_context():
    print(app.url_map)
