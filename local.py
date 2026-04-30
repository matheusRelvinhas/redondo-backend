#!/usr/bin/env python
import os
import logging
from dotenv import load_dotenv
from loguru import logger
from app import create_app

load_dotenv()

os.environ['ENVIRONMENT'] = 'development'

if os.environ.get('WERKZEUG_RUN_MAIN') != 'true':
    logger.remove()

if __name__ == '__main__':
    log = logging.getLogger('werkzeug')
    log.setLevel(logging.ERROR)
    app = create_app()
    
    port = int(os.getenv('FLASK_RUN_PORT', 3001))
    debug = os.getenv('FLASK_DEBUG') == 'True'
    
    if os.environ.get('WERKZEUG_RUN_MAIN') == 'true':
        logger.info(f"Innit development server")
    
    app.run(
        debug=debug,
        host='localhost',
        port=port,
        threaded=True,
        use_reloader=True
    )
