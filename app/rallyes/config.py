import os


class Config:
    SQLALCHEMY_DATABASE_URI = os.environ.get(
        "DATABASE_URL", "postgresql+psycopg://rallye:rallye@localhost:5432/rallyes")
    SQLALCHEMY_ENGINE_OPTIONS = {"pool_pre_ping": True}
    SECRET_KEY = os.environ.get("SECRET_KEY", "dev")
    COMPTES_DEMO = os.environ.get("COMPTES_DEMO", "1") == "1"
    # Traductions intégrées à WTForms (Meta.locales) plutôt que Flask-Babel
    WTF_I18N_ENABLED = False
