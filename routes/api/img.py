import os
import mimetypes
from flask import Blueprint, send_from_directory, abort

bp = Blueprint('img', __name__, url_prefix='/img')

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
IMG_DIR = os.path.join(BASE_DIR, 'img')
ONE_YEAR = 60 * 60 * 24 * 365
CONVERTIBLE = ('.png', '.jpg', '.jpeg')

mimetypes.add_type('image/webp', '.webp')

MIME_BY_EXT = {
    '.webp': 'image/webp',
    '.png': 'image/png',
    '.jpg': 'image/jpeg',
    '.jpeg': 'image/jpeg',
    '.svg': 'image/svg+xml',
    '.gif': 'image/gif',
}


def _inside_img_dir(filename: str):
    full = os.path.normpath(os.path.join(IMG_DIR, filename))
    if not full.startswith(IMG_DIR + os.sep):
        return None
    return full


@bp.route('/<path:filename>')
def serve_img(filename):
    full = _inside_img_dir(filename)
    if full is None:
        abort(404)
    if not os.path.isfile(full):
        base, ext = os.path.splitext(filename)
        if ext.lower() in CONVERTIBLE:
            candidate = base + '.webp'
            if (path := _inside_img_dir(candidate)) and os.path.isfile(path):
                filename = candidate
            else:
                abort(404)
        else:
            abort(404)
    mimetype = MIME_BY_EXT.get(os.path.splitext(filename)[1].lower())
    response = send_from_directory(
        IMG_DIR, filename, max_age=ONE_YEAR, mimetype=mimetype
    )
    response.headers['Cache-Control'] = 'public, max-age=31536000, immutable'
    response.headers['Access-Control-Allow-Origin'] = '*'
    return response
