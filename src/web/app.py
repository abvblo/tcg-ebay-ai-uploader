"""Flask web app for Pokemon card search with filtering"""

from flask import Flask, render_template, request, jsonify, send_from_directory
from flask_cors import CORS
from sqlalchemy import create_engine, func, and_, or_, Integer
from sqlalchemy.orm import sessionmaker, joinedload
from datetime import datetime
import os
import logging
import json

# Import database models
import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database.models import (
    PokemonCard, PokemonSet, Type, Subtype, CardVariation,
    DatabaseConfig, get_session
)

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize Flask app
app = Flask(__name__, static_folder='static')
CORS(app)

# Database configuration
DB_CONFIG = {
    'host': os.getenv('DB_HOST', 'localhost'),
    'port': int(os.getenv('DB_PORT', 5432)),
    'database': os.getenv('DB_NAME', 'pokemon_tcg'),
    'username': os.getenv('DB_USER', 'mateoallen'),
    'password': os.getenv('DB_PASSWORD', '')
}

# Create database engine
connection_string = DatabaseConfig.get_connection_string(**DB_CONFIG)
engine = DatabaseConfig.get_engine(connection_string)
Session = sessionmaker(bind=engine)


@app.route('/')
def index():
    """Main search page"""
    return render_template('index.html')


@app.route('/static/<path:path>')
def serve_static(path):
    """Serve static files"""
    return send_from_directory('static', path)


@app.route('/api/search', methods=['GET'])
def search_cards():
    """Search cards with filters"""
    session = Session()
    
    try:
        # Get search parameters
        query = request.args.get('q', '').strip()
        set_filter = request.args.get('set', '')
        type_filter = request.args.get('type', '')
        rarity_filter = request.args.get('rarity', '')
        edition_filter = request.args.get('edition', '')
        characteristics_filter = request.args.get('characteristics', '')
        page = request.args.get('page', 1, type=int)
        per_page = request.args.get('per_page', 20, type=int)
        sort_by = request.args.get('sort', 'name')
        
        # Build base query
        base_query = session.query(PokemonCard).options(
            joinedload(PokemonCard.set),
            joinedload(PokemonCard.types),
            joinedload(PokemonCard.subtypes)
        )
        
        # Apply search query
        if query:
            # Use PostgreSQL full-text search if available
            search_terms = query.lower().split()
            search_conditions = []
            
            for term in search_terms:
                search_conditions.append(
                    or_(
                        PokemonCard.name.ilike(f'%{term}%'),
                        PokemonCard.number.ilike(f'%{term}%'),
                        PokemonCard.artist.ilike(f'%{term}%')
                    )
                )
            
            base_query = base_query.filter(and_(*search_conditions))
        
        # Apply filters
        if set_filter:
            base_query = base_query.join(PokemonSet).filter(
                PokemonSet.name == set_filter
            )
        
        if type_filter:
            base_query = base_query.join(PokemonCard.types).filter(
                Type.name == type_filter
            )
        
        if rarity_filter:
            base_query = base_query.filter(
                PokemonCard.rarity == rarity_filter
            )
        
        # Apply characteristics filter
        if characteristics_filter:
            if characteristics_filter == 'holo':
                # Match cards with Holo in rarity
                base_query = base_query.filter(
                    or_(
                        PokemonCard.rarity.ilike('%holo%'),
                        PokemonCard.rarity.ilike('%rare%')
                    )
                )
            elif characteristics_filter == 'reverse':
                base_query = base_query.filter(
                    PokemonCard.rarity.ilike('%reverse%')
                )
            elif characteristics_filter == 'full-art':
                base_query = base_query.join(PokemonCard.subtypes).filter(
                    or_(
                        Subtype.name.ilike('%full art%'),
                        Subtype.name.ilike('%fullart%')
                    )
                )
            elif characteristics_filter == 'secret':
                base_query = base_query.filter(
                    PokemonCard.rarity.ilike('%secret%')
                )
            elif characteristics_filter == 'rainbow':
                base_query = base_query.filter(
                    or_(
                        PokemonCard.rarity.ilike('%rainbow%'),
                        PokemonCard.name.ilike('%rainbow%')
                    )
                )
            elif characteristics_filter == 'gold':
                base_query = base_query.filter(
                    or_(
                        PokemonCard.rarity.ilike('%gold%'),
                        PokemonCard.name.ilike('%gold%')
                    )
                )
            elif characteristics_filter == 'shining':
                base_query = base_query.filter(
                    PokemonCard.name.ilike('%shining%')
                )
            elif characteristics_filter == 'stamped':
                # Check for stamped indicators in card name (avoid extra join)
                base_query = base_query.filter(
                    or_(
                        PokemonCard.name.ilike('%staff%'),
                        PokemonCard.name.ilike('%prerelease%'),
                        PokemonCard.name.ilike('%league%'),
                        PokemonCard.name.ilike('%championship%')
                    )
                )
            elif characteristics_filter == 'prerelease':
                base_query = base_query.filter(
                    PokemonCard.name.ilike('%prerelease%')
                )
            elif characteristics_filter == 'staff':
                base_query = base_query.filter(
                    PokemonCard.name.ilike('%staff%')
                )
        
        # Apply sorting
        if sort_by == 'name':
            base_query = base_query.order_by(PokemonCard.name.asc())
        elif sort_by == 'name_desc':
            base_query = base_query.order_by(PokemonCard.name.desc())
        elif sort_by == 'number':
            # Convert number to integer for proper sorting if possible
            base_query = base_query.order_by(
                func.cast(func.split_part(PokemonCard.number, '/', 1), Integer).asc(),
                PokemonCard.number.asc()
            )
        elif sort_by == 'number_desc':
            base_query = base_query.order_by(
                func.cast(func.split_part(PokemonCard.number, '/', 1), Integer).desc(),
                PokemonCard.number.desc()
            )
        elif sort_by == 'hp':
            base_query = base_query.order_by(PokemonCard.hp.asc().nullsfirst())
        elif sort_by == 'hp_desc':
            base_query = base_query.order_by(PokemonCard.hp.desc().nullslast())
        elif sort_by == 'set':
            # Always use outerjoin to avoid duplicate join issues
            base_query = base_query.outerjoin(PokemonSet).order_by(
                PokemonSet.release_date.desc().nullslast(), 
                func.cast(func.split_part(PokemonCard.number, '/', 1), Integer).asc()
            )
        elif sort_by == 'set_old':
            base_query = base_query.outerjoin(PokemonSet).order_by(
                PokemonSet.release_date.asc().nullsfirst(), 
                func.cast(func.split_part(PokemonCard.number, '/', 1), Integer).asc()
            )
        
        # Count total results
        total = base_query.count()
        
        # Apply pagination
        cards = base_query.offset((page - 1) * per_page).limit(per_page).all()
        
        # Format results
        results = []
        for card in cards:
            # Get images based on edition filter
            images = json.loads(card.images) if isinstance(card.images, str) else (card.images or {})
            
            # Handle Base Set edition-specific images
            if card.set.id == 'base1' and edition_filter and isinstance(images, dict):
                if edition_filter == 'unlimited' and ('unlimited_small' in images or 'unlimited' in images):
                    # Use the stamp-removed unlimited images
                    display_images = {
                        'small': images.get('unlimited_small', images.get('unlimited', '')),
                        'large': images.get('unlimited_large', images.get('unlimited_small', images.get('unlimited', '')))
                    }
                elif edition_filter == '1st':
                    # Use original 1st edition images
                    display_images = {
                        'small': images.get('small', ''),
                        'large': images.get('large', '')
                    }
                elif edition_filter == 'shadowless':
                    # For shadowless, modify the URL (base5)
                    display_images = {
                        'small': images.get('small', '').replace('base1', 'base5'),
                        'large': images.get('large', '').replace('base1', 'base5')
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
                    'Rare Holo': 25.00,
                    'Rare': 5.00,
                    'Uncommon': 2.00,
                    'Common': 1.00,
                    'Rare Holo EX': 45.00,
                    'Rare Holo GX': 35.00,
                    'Rare Holo V': 15.00,
                    'Rare Holo VMAX': 25.00,
                    'Rare Secret': 75.00,
                    'Rare Ultra': 50.00
                }
                current_price = rarity_prices.get(card.rarity, 3.00)
            
            card_data = {
                'id': str(card.id),
                'api_id': card.api_id,
                'name': card.name,
                'number': card.number,
                'set': {
                    'id': card.set.id,
                    'name': card.set.name,
                    'series': card.set.series,
                    'release_date': card.set.release_date.isoformat() if card.set.release_date else None,
                    'images': json.loads(card.set.images) if isinstance(card.set.images, str) else (card.set.images or {})
                },
                'supertype': card.supertype,
                'types': [t.name for t in card.types],
                'subtypes': [s.name for s in card.subtypes],
                'hp': card.hp,
                'rarity': card.rarity,
                'artist': card.artist,
                'images': display_images,
                'evolves_from': card.evolves_from,
                'evolves_to': json.loads(card.evolves_to) if isinstance(card.evolves_to, str) else (card.evolves_to or []),
                'attacks': json.loads(card.attacks) if isinstance(card.attacks, str) else (card.attacks or []),
                'abilities': json.loads(card.abilities) if isinstance(card.abilities, str) else (card.abilities or []),
                'weaknesses': json.loads(card.weaknesses) if isinstance(card.weaknesses, str) else (card.weaknesses or []),
                'resistances': json.loads(card.resistances) if isinstance(card.resistances, str) else (card.resistances or []),
                'retreat_cost': json.loads(card.retreat_cost) if isinstance(card.retreat_cost, str) else (card.retreat_cost or []),
                'tcgplayer_url': tcgplayer_url,
                'current_price': current_price
            }
            results.append(card_data)
        
        return jsonify({
            'results': results,
            'total': total,
            'page': page,
            'per_page': per_page,
            'total_pages': (total + per_page - 1) // per_page
        })
        
    except Exception as e:
        logger.error(f"Search error: {e}")
        return jsonify({'error': str(e)}), 500
        
    finally:
        session.close()


@app.route('/api/filters', methods=['GET'])
def get_filters():
    """Get available filter options"""
    session = Session()
    
    try:
        # Get all sets
        sets = session.query(
            PokemonSet.name, 
            func.count(PokemonCard.id).label('count')
        ).join(PokemonCard).group_by(PokemonSet.name).order_by(
            PokemonSet.name
        ).all()
        
        # Get all types
        types = session.query(
            Type.name,
            func.count(PokemonCard.id).label('count')
        ).join(PokemonCard.types).group_by(Type.name).order_by(
            Type.name
        ).all()
        
        # Get all rarities
        rarities = session.query(
            PokemonCard.rarity,
            func.count(PokemonCard.id).label('count')
        ).filter(
            PokemonCard.rarity.isnot(None)
        ).group_by(PokemonCard.rarity).order_by(
            PokemonCard.rarity
        ).all()
        
        return jsonify({
            'sets': [{'name': s[0], 'count': s[1]} for s in sets],
            'types': [{'name': t[0], 'count': t[1]} for t in types],
            'rarities': [{'name': r[0], 'count': r[1]} for r in rarities]
        })
        
    except Exception as e:
        logger.error(f"Filter error: {e}")
        return jsonify({'error': str(e)}), 500
        
    finally:
        session.close()


@app.route('/api/card/<card_id>', methods=['GET'])
def get_card_details(card_id):
    """Get detailed card information"""
    session = Session()
    
    try:
        card = session.query(PokemonCard).options(
            joinedload(PokemonCard.set),
            joinedload(PokemonCard.types),
            joinedload(PokemonCard.subtypes),
            joinedload(PokemonCard.variations)
        ).filter(PokemonCard.id == card_id).first()
        
        if not card:
            return jsonify({'error': 'Card not found'}), 404
        
        # Format detailed response
        card_data = {
            'id': str(card.id),
            'api_id': card.api_id,
            'name': card.name,
            'number': card.number,
            'set': {
                'id': card.set.id,
                'name': card.set.name,
                'series': card.set.series,
                'printed_total': card.set.printed_total,
                'total': card.set.total,
                'release_date': card.set.release_date.isoformat() if card.set.release_date else None,
                'images': json.loads(card.set.images) if isinstance(card.set.images, str) else (card.set.images or {})
            },
            'supertype': card.supertype,
            'types': [t.name for t in card.types],
            'subtypes': [s.name for s in card.subtypes],
            'hp': card.hp,
            'rarity': card.rarity,
            'artist': card.artist,
            'images': json.loads(card.images) if isinstance(card.images, str) else (card.images or {}),
            'evolves_from': card.evolves_from,
            'evolves_to': json.loads(card.evolves_to) if isinstance(card.evolves_to, str) else (card.evolves_to or []),
            'attacks': json.loads(card.attacks) if isinstance(card.attacks, str) else (card.attacks or []),
            'abilities': json.loads(card.abilities) if isinstance(card.abilities, str) else (card.abilities or []),
            'weaknesses': json.loads(card.weaknesses) if isinstance(card.weaknesses, str) else (card.weaknesses or []),
            'resistances': json.loads(card.resistances) if isinstance(card.resistances, str) else (card.resistances or []),
            'retreat_cost': json.loads(card.retreat_cost) if isinstance(card.retreat_cost, str) else (card.retreat_cost or []),
            'rules': json.loads(card.rules) if isinstance(card.rules, str) else (card.rules or []),
            'regulation_mark': card.regulation_mark,
            'variations': [
                {
                    'id': str(v.id),
                    'type': v.variation_type,
                    'finish': v.finish,
                    'is_reverse_holo': v.is_reverse_holo,
                    'is_first_edition': v.is_first_edition,
                    'is_stamped': v.is_stamped,
                    'stamp_type': v.stamp_type
                }
                for v in card.variations
            ]
        }
        
        return jsonify(card_data)
        
    except Exception as e:
        logger.error(f"Card detail error: {e}")
        return jsonify({'error': str(e)}), 500
        
    finally:
        session.close()


@app.route('/api/autocomplete', methods=['GET'])
def autocomplete():
    """Autocomplete suggestions for card names"""
    session = Session()
    
    try:
        query = request.args.get('q', '').strip()
        if len(query) < 2:
            return jsonify([])
        
        # Get matching card names
        suggestions = session.query(
            PokemonCard.name
        ).filter(
            PokemonCard.name.ilike(f'{query}%')
        ).distinct().order_by(
            PokemonCard.name
        ).limit(10).all()
        
        return jsonify([s[0] for s in suggestions])
        
    except Exception as e:
        logger.error(f"Autocomplete error: {e}")
        return jsonify([])
        
    finally:
        session.close()


if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)