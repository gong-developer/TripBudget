"""Serve the production frontend from the API's origin when a build is present."""
import os
from pathlib import Path
from fastapi.staticfiles import StaticFiles


class WebFiles(StaticFiles):
    async def get_response(self, path, scope):
        response = await super().get_response(path, scope)
        response.headers['Cache-Control'] = ('public, max-age=31536000, immutable'
                                             if path.replace('\\', '/').lstrip('/').startswith('assets/') else 'no-cache')
        return response


def install_web(app):
    directory = Path(os.getenv('FRONTEND_DIST') or Path(__file__).resolve().parents[2] / 'frontend' / 'dist')
    if (directory / 'index.html').is_file():
        app.mount('/', WebFiles(directory=directory, html=True), name='web')
