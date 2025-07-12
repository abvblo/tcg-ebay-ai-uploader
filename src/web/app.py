"""Flask web app for Pokemon card search with filtering"""

import json
import logging
import os
import secrets

# Import database models
import sys
from datetime import datetime
from functools import wraps

from flask import (
    Flask,
    flash,
    jsonify,
    redirect,
    render_template,
    request,
    send_from_directory,
    session,
    url_for,
)
from flask_cors import CORS
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from flask_login import (
    LoginManager,
    UserMixin,
    current_user,
    login_required,
    login_user,
    logout_user,
)
from flask_talisman import Talisman

from sqlalchemy import Integer, and_, create_engine, func, or_
from sqlalchemy.orm import joinedload, sessionmaker

# Add the src directory to the path for imports
src_path = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, src_path)

# Import security utilities
from web.security_utils import (
    log_security_event,
    secure_like_query,
    validate_autocomplete_query,
    validate_filter_value,
    validate_pagination_params,
    validate_query_params,
    validate_request_size,
    validate_search_query,
    validate_sort_parameter,
)

from config import Config

# Import database models directly from the file to avoid conflicts
import importlib.util
db_models_path = os.path.join(src_path, "database", "models.py")
spec = importlib.util.spec_from_file_location("db_models", db_models_path)
db_models = importlib.util.module_from_spec(spec)
spec.loader.exec_module(db_models)

# Extract the models we need
CardVariation = db_models.CardVariation
DatabaseConfig = db_models.DatabaseConfig
PokemonCard = db_models.PokemonCard
PokemonSet = db_models.PokemonSet
Subtype = db_models.Subtype
Type = db_models.Type
get_session = db_models.get_session

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize Flask app
app = Flask(__name__, static_folder="static")

# Load configuration
config = Config()

# Generate secret key for sessions
app.config["SECRET_KEY"] = config.secret_key

# Environment configuration
FLASK_ENV = os.getenv("FLASK_ENV", "development")
IS_PRODUCTION = FLASK_ENV == "production"


# Health check route for Docker - moved to end of file


# Security configuration
if IS_PRODUCTION:
    app.config["DEBUG"] = False
    app.config["TESTING"] = False
    app.config["PREFERRED_URL_SCHEME"] = "https"
    # Production host binding
    HOST = os.getenv("FLASK_HOST", "127.0.0.1")
    PORT = int(os.getenv("FLASK_PORT", 5001))
else:
    app.config["DEBUG"] = True
    app.config["TESTING"] = False
    # Development host binding
    HOST = os.getenv("FLASK_HOST", "127.0.0.1")
    PORT = int(os.getenv("FLASK_PORT", 5001))

# CORS configuration
CORS(
    app,
    origins=[
        "http://localhost:3000",
        "http://localhost:5001",
        "https://yourdomain.com" if IS_PRODUCTION else "http://localhost:5001",
    ],
)

# Security headers with Talisman
if IS_PRODUCTION:
    # Production security headers
    csp = {
        "default-src": "'self'",
        "script-src": "'self' 'unsafe-inline' 'unsafe-eval' https://cdnjs.cloudflare.com",
        "style-src": "'self' 'unsafe-inline' https://fonts.googleapis.com https://cdnjs.cloudflare.com",
        "font-src": "'self' https://fonts.gstatic.com",
        "img-src": "'self' data: https: http:",
        "connect-src": "'self' https://api.pokemontcg.io https://www.tcgplayer.com",
        "frame-ancestors": "'none'",
        "base-uri": "'self'",
        "object-src": "'none'",
    }

    Talisman(
        app,
        force_https=True,
        strict_transport_security=True,
        strict_transport_security_max_age=31536000,
        content_security_policy=csp,
        content_security_policy_nonce_in=["script-src", "style-src"],
        referrer_policy="strict-origin-when-cross-origin",
        feature_policy={"geolocation": "'none'", "microphone": "'none'", "camera": "'none'"},
    )
else:
    # Development security headers (relaxed)
    csp = {
        "default-src": "'self'",
        "script-src": "'self' 'unsafe-inline' 'unsafe-eval' https://cdnjs.cloudflare.com",
        "style-src": "'self' 'unsafe-inline' https://fonts.googleapis.com https://cdnjs.cloudflare.com",
        "font-src": "'self' https://fonts.gstatic.com",
        "img-src": "'self' data: https: http:",
        "connect-src": "'self' https://api.pokemontcg.io https://www.tcgplayer.com",
        "frame-ancestors": "'none'",
        "base-uri": "'self'",
        "object-src": "'none'",
    }

    Talisman(
        app,
        force_https=False,
        strict_transport_security=False,
        content_security_policy=csp,
        content_security_policy_nonce_in=["script-src", "style-src"],
    )

# Rate limiting
limiter = Limiter(
    key_func=get_remote_address,
    default_limits=["1000 per hour", "100 per minute"],
    storage_uri=os.getenv("REDIS_URL", "memory://"),
    strategy="fixed-window",
)

# Initialize Flask-Login
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = "login"
login_manager.login_message = "Please log in to access this page."
login_manager.login_message_category = "info"


# Simple User class for authentication
class User(UserMixin):
    def __init__(self, user_id):
        self.id = user_id


@login_manager.user_loader
def load_user(user_id):
    if user_id == "admin":
        return User(user_id)
    return None


# Login route
@app.route("/login", methods=["GET", "POST"])
def login():
    """Login route for user authentication"""
    if current_user.is_authenticated:
        return redirect(url_for("index"))
    
    if request.method == "POST":
        username = request.form.get("username")
        password = request.form.get("password")
        
        # Simple authentication - in production, use proper password hashing
        if username == "admin" and password == "admin123":
            user = User("admin")
            login_user(user)
            next_page = request.args.get("next")
            return redirect(next_page) if next_page else redirect(url_for("index"))
        else:
            flash("Invalid username or password", "error")
    
    return render_template("login.html")


@app.route("/logout")
@login_required
def logout():
    """Logout route"""
    logout_user()
    flash("You have been logged out successfully", "info")
    return redirect(url_for("login"))


# Authentication decorators
def api_key_required(f):
    """Decorator to require API key authentication for API endpoints"""

    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not config.auth_enabled:
            return f(*args, **kwargs)

        # Check for API key in headers
        api_key = request.headers.get("X-API-Key")
        if api_key and api_key == config.api_key:
            return f(*args, **kwargs)

        # Check if user is logged in via session
        if current_user.is_authenticated:
            return f(*args, **kwargs)

        return jsonify({"error": "API key required"}), 401

    return decorated_function


def auth_required(f):
    """Decorator to require authentication for web pages"""

    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not config.auth_enabled:
            return f(*args, **kwargs)
        return login_required(f)(*args, **kwargs)

    return decorated_function


# Database configuration
DB_CONFIG = {
    "host": os.getenv("DB_HOST", "localhost"),
    "port": int(os.getenv("DB_PORT", 5432)),
    "database": os.getenv("DB_NAME", "pokemon_tcg"),
    "username": os.getenv("DB_USER", "mateoallen"),
    "password": os.getenv("DB_PASSWORD", ""),
}

# Create database engine
connection_string = DatabaseConfig.get_connection_string(**DB_CONFIG)
engine = DatabaseConfig.get_engine(connection_string)
Session = sessionmaker(bind=engine)


@app.route("/")
@auth_required
def index():
    """Main search page"""
    return render_template("index.html")


@app.route("/static/<path:path>")
def serve_static(path):
    """Serve static files"""
    return send_from_directory("static", path)


@app.route("/assets/<path:path>")
def serve_assets(path):
    """Serve asset files (images, etc.)"""
    assets_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "assets")
    return send_from_directory(assets_dir, path)


@app.route("/api/search", methods=["GET"])
@limiter.limit("30 per minute")
@api_key_required
@validate_request_size(max_size=4096)  # 4KB limit for search requests
@validate_query_params()
def search_cards():
    """Search cards with filters"""
    session = Session()

    try:
        # Get and validate search parameters
        query = validate_search_query(request.args.get("q", "").strip())
        set_filter = validate_filter_value(request.args.get("set", ""), "set")
        type_filter = validate_filter_value(request.args.get("type", ""), "type")
        rarity_filter = validate_filter_value(request.args.get("rarity", ""), "rarity")
        edition_filter = validate_filter_value(request.args.get("edition", ""), "edition")
        characteristics_filter = validate_filter_value(
            request.args.get("characteristics", ""), "characteristics"
        )
        page, per_page = validate_pagination_params(
            request.args.get("page", 1), request.args.get("per_page", 20)
        )
        sort_by = validate_sort_parameter(request.args.get("sort", "name"))

        # Build base query
        base_query = session.query(PokemonCard).options(
            joinedload(PokemonCard.set),
            joinedload(PokemonCard.types),
            joinedload(PokemonCard.subtypes),
        )

        # Apply search query
        if query:
            # Use PostgreSQL full-text search if available
            search_terms = query.lower().split()
            search_conditions = []

            for term in search_terms:
                search_conditions.append(
                    or_(
                        secure_like_query(PokemonCard.name, term),
                        secure_like_query(PokemonCard.number, term),
                        secure_like_query(PokemonCard.artist, term),
                    )
                )

            base_query = base_query.filter(and_(*search_conditions))

        # Apply filters
        if set_filter:
            base_query = base_query.join(PokemonSet).filter(PokemonSet.name == set_filter)

        if type_filter:
            base_query = base_query.join(PokemonCard.types).filter(Type.name == type_filter)

        if rarity_filter:
            base_query = base_query.filter(PokemonCard.rarity == rarity_filter)

        # Apply characteristics filter
        if characteristics_filter:
            if characteristics_filter == "holo":
                # Match cards with Holo in rarity
                base_query = base_query.filter(
                    or_(PokemonCard.rarity.ilike("%holo%"), PokemonCard.rarity.ilike("%rare%"))
                )
            elif characteristics_filter == "reverse":
                base_query = base_query.filter(PokemonCard.rarity.ilike("%reverse%"))
            elif characteristics_filter == "full-art":
                base_query = base_query.join(PokemonCard.subtypes).filter(
                    or_(Subtype.name.ilike("%full art%"), Subtype.name.ilike("%fullart%"))
                )
            elif characteristics_filter == "secret":
                base_query = base_query.filter(PokemonCard.rarity.ilike("%secret%"))
            elif characteristics_filter == "rainbow":
                base_query = base_query.filter(
                    or_(PokemonCard.rarity.ilike("%rainbow%"), PokemonCard.name.ilike("%rainbow%"))
                )
            elif characteristics_filter == "gold":
                base_query = base_query.filter(
                    or_(PokemonCard.rarity.ilike("%gold%"), PokemonCard.name.ilike("%gold%"))
                )
            elif characteristics_filter == "shining":
                base_query = base_query.filter(PokemonCard.name.ilike("%shining%"))
            elif characteristics_filter == "stamped":
                # Check for stamped indicators in card name (avoid extra join)
                base_query = base_query.filter(
                    or_(
                        PokemonCard.name.ilike("%staff%"),
                        PokemonCard.name.ilike("%prerelease%"),
                        PokemonCard.name.ilike("%league%"),
                        PokemonCard.name.ilike("%championship%"),
                    )
                )
            elif characteristics_filter == "prerelease":
                base_query = base_query.filter(PokemonCard.name.ilike("%prerelease%"))
            elif characteristics_filter == "staff":
                base_query = base_query.filter(PokemonCard.name.ilike("%staff%"))

        # Apply sorting
        if sort_by == "name":
            base_query = base_query.order_by(PokemonCard.name.asc())
        elif sort_by == "name_desc":
            base_query = base_query.order_by(PokemonCard.name.desc())
        elif sort_by == "number":
            # Convert number to integer for proper sorting if possible
            base_query = base_query.order_by(
                func.cast(func.split_part(PokemonCard.number, "/", 1), Integer).asc(),
                PokemonCard.number.asc(),
            )
        elif sort_by == "number_desc":
            base_query = base_query.order_by(
                func.cast(func.split_part(PokemonCard.number, "/", 1), Integer).desc(),
                PokemonCard.number.desc(),
            )
        elif sort_by == "hp":
            base_query = base_query.order_by(PokemonCard.hp.asc().nullsfirst())
        elif sort_by == "hp_desc":
            base_query = base_query.order_by(PokemonCard.hp.desc().nullslast())
        elif sort_by == "set":
            # Always use outerjoin to avoid duplicate join issues
            base_query = base_query.outerjoin(PokemonSet).order_by(
                PokemonSet.release_date.desc().nullslast(),
                func.cast(func.split_part(PokemonCard.number, "/", 1), Integer).asc(),
            )
        elif sort_by == "set_old":
            base_query = base_query.outerjoin(PokemonSet).order_by(
                PokemonSet.release_date.asc().nullsfirst(),
                func.cast(func.split_part(PokemonCard.number, "/", 1), Integer).asc(),
            )

        # Count total results
        total = base_query.count()

        # Apply pagination
        cards = base_query.offset((page - 1) * per_page).limit(per_page).all()

        # Format results
        results = []
        for card in cards:
            # Get images based on edition filter
            images = (
                json.loads(card.images) if isinstance(card.images, str) else (card.images or {})
            )

            # Handle Base Set edition-specific images
            if card.set.id == "base1" and edition_filter and isinstance(images, dict):
                if edition_filter == "unlimited" and (
                    "unlimited_small" in images or "unlimited" in images
                ):
                    # Use the stamp-removed unlimited images
                    display_images = {
                        "small": images.get("unlimited_small", images.get("unlimited", "")),
                        "large": images.get(
                            "unlimited_large",
                            images.get("unlimited_small", images.get("unlimited", "")),
                        ),
                    }
                elif edition_filter == "1st":
                    # Use original 1st edition images
                    display_images = {
                        "small": images.get("small", ""),
                        "large": images.get("large", ""),
                    }
                elif edition_filter == "shadowless":
                    # For shadowless, modify the URL (base5)
                    display_images = {
                        "small": images.get("small", "").replace("base1", "base5"),
                        "large": images.get("large", "").replace("base1", "base5"),
                    }
                else:
                    display_images = images
            else:
                display_images = images

            # Generate TCGPlayer URL
            tcgplayer_url = None
            if card.tcgplayer_id:
                # Base TCGPlayer product URL format
                tcgplayer_url = f"https://www.tcgplayer.com/product/{card.tcgplayer_id}"

            # Mock current price (in production, this would come from price tracking)
            current_price = None
            if card.tcgplayer_id:
                # In production, query latest price from PriceSnapshot table
                # For now, use a mock price based on rarity
                rarity_prices = {
                    "Rare Holo": 25.00,
                    "Rare": 5.00,
                    "Uncommon": 2.00,
                    "Common": 1.00,
                    "Rare Holo EX": 45.00,
                    "Rare Holo GX": 35.00,
                    "Rare Holo V": 15.00,
                    "Rare Holo VMAX": 25.00,
                    "Rare Secret": 75.00,
                    "Rare Ultra": 50.00,
                }
                current_price = rarity_prices.get(card.rarity, 3.00)

            card_data = {
                "id": str(card.id),
                "api_id": card.api_id,
                "name": card.name,
                "number": card.number,
                "set": {
                    "id": card.set.id,
                    "name": card.set.name,
                    "series": card.set.series,
                    "release_date": (
                        card.set.release_date.isoformat() if card.set.release_date else None
                    ),
                    "images": (
                        json.loads(card.set.images)
                        if isinstance(card.set.images, str)
                        else (card.set.images or {})
                    ),
                },
                "supertype": card.supertype,
                "types": [t.name for t in card.types],
                "subtypes": [s.name for s in card.subtypes],
                "hp": card.hp,
                "rarity": card.rarity,
                "artist": card.artist,
                "images": display_images,
                "evolves_from": card.evolves_from,
                "evolves_to": (
                    json.loads(card.evolves_to)
                    if isinstance(card.evolves_to, str)
                    else (card.evolves_to or [])
                ),
                "attacks": (
                    json.loads(card.attacks)
                    if isinstance(card.attacks, str)
                    else (card.attacks or [])
                ),
                "abilities": (
                    json.loads(card.abilities)
                    if isinstance(card.abilities, str)
                    else (card.abilities or [])
                ),
                "weaknesses": (
                    json.loads(card.weaknesses)
                    if isinstance(card.weaknesses, str)
                    else (card.weaknesses or [])
                ),
                "resistances": (
                    json.loads(card.resistances)
                    if isinstance(card.resistances, str)
                    else (card.resistances or [])
                ),
                "retreat_cost": (
                    json.loads(card.retreat_cost)
                    if isinstance(card.retreat_cost, str)
                    else (card.retreat_cost or [])
                ),
                "tcgplayer_url": tcgplayer_url,
                "current_price": current_price,
            }
            results.append(card_data)

        return jsonify(
            {
                "results": results,
                "total": total,
                "page": page,
                "per_page": per_page,
                "total_pages": (total + per_page - 1) // per_page,
            }
        )

    except ValueError as e:
        # Input validation error
        log_security_event(
            "invalid_search_input",
            {
                "error": str(e),
                "ip": request.remote_addr,
                "user_agent": request.headers.get("User-Agent"),
            },
        )
        return jsonify({"error": "Invalid search parameters"}), 400
    except Exception as e:
        logger.error(f"Search error: {e}")
        return jsonify({"error": "Internal server error"}), 500

    finally:
        session.close()


@app.route("/api/filters", methods=["GET"])
@limiter.limit("10 per minute")
@api_key_required
@validate_request_size(max_size=1024)  # 1KB limit for filters
def get_filters():
    """Get available filter options"""
    session = Session()

    try:
        # Get all sets
        sets = (
            session.query(PokemonSet.name, func.count(PokemonCard.id).label("count"))
            .join(PokemonCard)
            .group_by(PokemonSet.name)
            .order_by(PokemonSet.name)
            .all()
        )

        # Get all types
        types = (
            session.query(Type.name, func.count(PokemonCard.id).label("count"))
            .join(PokemonCard.types)
            .group_by(Type.name)
            .order_by(Type.name)
            .all()
        )

        # Get all rarities
        rarities = (
            session.query(PokemonCard.rarity, func.count(PokemonCard.id).label("count"))
            .filter(PokemonCard.rarity.isnot(None))
            .group_by(PokemonCard.rarity)
            .order_by(PokemonCard.rarity)
            .all()
        )

        return jsonify(
            {
                "sets": [{"name": s[0], "count": s[1]} for s in sets],
                "types": [{"name": t[0], "count": t[1]} for t in types],
                "rarities": [{"name": r[0], "count": r[1]} for r in rarities],
            }
        )

    except Exception as e:
        logger.error(f"Filter error: {e}")
        return jsonify({"error": str(e)}), 500

    finally:
        session.close()


@app.route("/api/card/<card_id>", methods=["GET"])
@limiter.limit("60 per minute")
@api_key_required
@validate_request_size(max_size=1024)  # 1KB limit for card details
def get_card_details(card_id):
    """Get detailed card information"""
    session = Session()

    try:
        # Validate card_id is a valid UUID/integer
        if not card_id or len(card_id) > 50:
            return jsonify({"error": "Invalid card ID"}), 400

        # Use parameterized query - card_id is already sanitized by Flask route
        card = (
            session.query(PokemonCard)
            .options(
                joinedload(PokemonCard.set),
                joinedload(PokemonCard.types),
                joinedload(PokemonCard.subtypes),
                joinedload(PokemonCard.variations),
            )
            .filter(PokemonCard.id == card_id)
            .first()
        )

        if not card:
            return jsonify({"error": "Card not found"}), 404

        # Format detailed response
        card_data = {
            "id": str(card.id),
            "api_id": card.api_id,
            "name": card.name,
            "number": card.number,
            "set": {
                "id": card.set.id,
                "name": card.set.name,
                "series": card.set.series,
                "printed_total": card.set.printed_total,
                "total": card.set.total,
                "release_date": (
                    card.set.release_date.isoformat() if card.set.release_date else None
                ),
                "images": (
                    json.loads(card.set.images)
                    if isinstance(card.set.images, str)
                    else (card.set.images or {})
                ),
            },
            "supertype": card.supertype,
            "types": [t.name for t in card.types],
            "subtypes": [s.name for s in card.subtypes],
            "hp": card.hp,
            "rarity": card.rarity,
            "artist": card.artist,
            "images": (
                json.loads(card.images) if isinstance(card.images, str) else (card.images or {})
            ),
            "evolves_from": card.evolves_from,
            "evolves_to": (
                json.loads(card.evolves_to)
                if isinstance(card.evolves_to, str)
                else (card.evolves_to or [])
            ),
            "attacks": (
                json.loads(card.attacks) if isinstance(card.attacks, str) else (card.attacks or [])
            ),
            "abilities": (
                json.loads(card.abilities)
                if isinstance(card.abilities, str)
                else (card.abilities or [])
            ),
            "weaknesses": (
                json.loads(card.weaknesses)
                if isinstance(card.weaknesses, str)
                else (card.weaknesses or [])
            ),
            "resistances": (
                json.loads(card.resistances)
                if isinstance(card.resistances, str)
                else (card.resistances or [])
            ),
            "retreat_cost": (
                json.loads(card.retreat_cost)
                if isinstance(card.retreat_cost, str)
                else (card.retreat_cost or [])
            ),
            "rules": json.loads(card.rules) if isinstance(card.rules, str) else (card.rules or []),
            "regulation_mark": card.regulation_mark,
            "variations": [
                {
                    "id": str(v.id),
                    "type": v.variation_type,
                    "finish": v.finish,
                    "is_reverse_holo": v.is_reverse_holo,
                    "is_first_edition": v.is_first_edition,
                    "is_stamped": v.is_stamped,
                    "stamp_type": v.stamp_type,
                }
                for v in card.variations
            ],
        }

        return jsonify(card_data)

    except Exception as e:
        logger.error(f"Card detail error: {e}")
        return jsonify({"error": str(e)}), 500

    finally:
        session.close()


@app.route("/api/autocomplete_old", methods=["GET"])
@limiter.limit("120 per minute")
@api_key_required
@validate_request_size(max_size=1024)  # 1KB limit for autocomplete
def autocomplete_old():
    """Autocomplete suggestions for card names"""
    session = Session()

    try:
        query = validate_autocomplete_query(request.args.get("q", "").strip())
        if not query:
            return jsonify([])

        # Get matching card names
        suggestions = (
            session.query(PokemonCard.name)
            .filter(secure_like_query(PokemonCard.name, query, prefix_only=True))
            .distinct()
            .order_by(PokemonCard.name)
            .limit(10)
            .all()
        )

        return jsonify([s[0] for s in suggestions])

    except ValueError as e:
        # Input validation error
        log_security_event(
            "invalid_autocomplete_input",
            {
                "error": str(e),
                "ip": request.remote_addr,
                "user_agent": request.headers.get("User-Agent"),
            },
        )
        return jsonify([])
    except Exception as e:
        logger.error(f"Autocomplete error: {e}")
        return jsonify([])

    finally:
        session.close()


# Security middleware for request logging
@app.before_request
def log_request_info():
    """Log request information for security monitoring"""
    if IS_PRODUCTION:
        logger.info(f"Request: {request.method} {request.url} from {request.remote_addr}")
        # Log suspicious activity
        if request.method not in ["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS"]:
            logger.warning(
                f"Suspicious request method: {request.method} from {request.remote_addr}"
            )


# Error handlers
@app.errorhandler(429)
def ratelimit_handler(e):
    """Rate limit exceeded handler"""
    return (
        jsonify(
            {
                "error": "Rate limit exceeded",
                "message": "Too many requests. Please try again later.",
                "retry_after": str(e.retry_after),
            }
        ),
        429,
    )


@app.errorhandler(500)
def internal_error(error):
    """Internal server error handler"""
    if IS_PRODUCTION:
        # Don't expose stack traces in production
        return (
            jsonify(
                {
                    "error": "Internal server error",
                    "message": "An unexpected error occurred. Please try again later.",
                }
            ),
            500,
        )
    else:
        # Show detailed errors in development
        return jsonify({"error": "Internal server error", "message": str(error)}), 500


@app.errorhandler(404)
def not_found(error):
    """Not found handler"""
    return jsonify({"error": "Not found", "message": "The requested resource was not found."}), 404


# Health check endpoint
@app.route("/health", methods=["GET"])
@limiter.limit("10 per minute")
def health_check():
    """Health check endpoint for monitoring"""
    return jsonify({"status": "healthy", "environment": FLASK_ENV, "version": "1.0.0"}), 200


if __name__ == "__main__":
    # Log security configuration on startup
    logger.info(f"Starting Flask application in {FLASK_ENV} mode")
    logger.info(f"Debug mode: {app.config['DEBUG']}")
    logger.info(f"Host: {HOST}, Port: {PORT}")
    logger.info(f"Security headers: {'Enabled' if IS_PRODUCTION else 'Development mode'}")
    logger.info(f"Rate limiting: {'Enabled' if limiter else 'Disabled'}")

    # Start the application
    app.run(debug=app.config["DEBUG"], host=HOST, port=PORT)
