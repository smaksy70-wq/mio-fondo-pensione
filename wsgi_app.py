
from main import app
from a2wsgi import ASGIMiddleware

# This is the entry point for PythonAnywhere's WSGI setup
application = ASGIMiddleware(app)
