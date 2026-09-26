import os
import logging
from contextlib import contextmanager
from sqlalchemy import create_engine, text
from sqlalchemy.orm import declarative_base, sessionmaker, scoped_session
from config import Config

logger = logging.getLogger(__name__)

Base = declarative_base()

def get_engine(db_uri=None):
    uri = db_uri or Config.SQLALCHEMY_DATABASE_URI
    is_sqlite = uri.startswith("sqlite")
    
    engine_kwargs = {
        'pool_pre_ping': True
    }
    
    if is_sqlite:
        # SQLite specific configuration
        engine_kwargs['connect_args'] = {'check_same_thread': False}
    else:
        # PostgreSQL specific pool settings
        engine_kwargs['pool_size'] = 10
        engine_kwargs['max_overflow'] = 20
        engine_kwargs['pool_recycle'] = 1800

    try:
        engine = create_engine(uri, **engine_kwargs)
        # Test connection
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        logger.info(f"Database connected successfully: {uri.split('@')[-1] if '@' in uri else 'local-db'}")
        return engine, uri
    except Exception as e:
        logger.warning(f"Failed to connect to primary database ({uri}): {e}")
        if not is_sqlite:
            # Fall back to SQLite for safe execution
            logger.info("Falling back to local persistent SQLite database...")
            base_dir = os.path.abspath(os.path.dirname(__file__))
            fallback_uri = f"sqlite:///{os.path.join(base_dir, 'emergency_command.db')}"
            fallback_engine = create_engine(fallback_uri, connect_args={'check_same_thread': False})
            return fallback_engine, fallback_uri
        raise

engine, active_db_uri = get_engine()
session_factory = sessionmaker(bind=engine, autoflush=False, autocommit=False)
db_session = scoped_session(session_factory)

@contextmanager
def get_db():
    """Transactional session context manager."""
    session = db_session()
    try:
        yield session
        session.commit()
    except Exception as e:
        session.rollback()
        logger.error(f"Database transaction error: {e}")
        raise
    finally:
        session.close()

def init_db():
    """Safely initialize database tables without dropping existing data."""
    import models  # Ensure all model classes are registered
    try:
        Base.metadata.create_all(bind=engine)
        logger.info("Database schema verified/created successfully.")
        return True
    except Exception as e:
        logger.error(f"Error creating database tables: {e}")
        return False

def get_db_info():
    """Returns human-readable database connection info for system monitoring."""
    is_postgres = "postgresql" in active_db_uri or "postgres" in active_db_uri
    return {
        'engine': 'PostgreSQL' if is_postgres else 'SQLite (Persistent Fallback)',
        'is_postgres': is_postgres,
        'status': 'Connected & Active'
    }
