import os
from hashvera import create_app

app = create_app()

if __name__ == "__main__":
    from hashvera.config import Config
    app.run(
        host=os.environ.get("FLASK_RUN_HOST", "0.0.0.0"),
        port=int(os.environ.get("PORT", "5000")),
        debug=Config.env_flag("FLASK_DEBUG", True),
        use_reloader=Config.env_flag("FLASK_USE_RELOADER", True),
    )
