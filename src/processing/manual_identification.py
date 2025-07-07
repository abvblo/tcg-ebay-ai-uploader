"""Manual identification system for low-confidence cards"""
import json
from pathlib import Path
from typing import Dict, List, Optional
import csv
from datetime import datetime

class ManualIdentificationSystem:
    """Handle manual identification workflow for misidentified cards"""
    
    def __init__(self, output_dir: Path = None):
        self.output_dir = output_dir or Path("output/manual_review")
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.review_file = self.output_dir / "cards_for_review.csv"
        self.corrections_file = self.output_dir / "manual_corrections.json"
        self.load_corrections()
        
    def load_corrections(self):
        """Load existing manual corrections"""
        self.corrections = {}
        if self.corrections_file.exists():
            with open(self.corrections_file, 'r') as f:
                self.corrections = json.load(f)
                
    def save_corrections(self):
        """Save manual corrections"""
        with open(self.corrections_file, 'w') as f:
            json.dump(self.corrections, f, indent=2)
            
    def add_for_review(self, image_path: str, ximilar_data: Dict, reason: str):
        """Add a card for manual review"""
        # Create CSV if doesn't exist
        write_header = not self.review_file.exists()
        
        with open(self.review_file, 'a', newline='') as f:
            writer = csv.writer(f)
            
            if write_header:
                writer.writerow([
                    'Timestamp', 'Image Path', 'Ximilar Name', 'Ximilar Set', 
                    'Ximilar Number', 'Confidence', 'Review Reason',
                    'Manual Name', 'Manual Set', 'Manual Number', 'Notes'
                ])
                
            writer.writerow([
                datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                image_path,
                ximilar_data.get('name', ''),
                ximilar_data.get('set_name', ''),
                ximilar_data.get('number', ''),
                f"{ximilar_data.get('confidence', 0):.2%}",
                reason,
                '',  # Manual name (to be filled)
                '',  # Manual set (to be filled)
                '',  # Manual number (to be filled)
                ''   # Notes (to be filled)
            ])
            
    def get_manual_correction(self, image_path: str) -> Optional[Dict]:
        """Get manual correction for an image if exists"""
        return self.corrections.get(image_path)
        
    def add_manual_correction(self, image_path: str, correction: Dict):
        """Add a manual correction"""
        self.corrections[image_path] = {
            **correction,
            'timestamp': datetime.now().isoformat()
        }
        self.save_corrections()
        
    def generate_review_html(self):
        """Generate HTML file for easy review"""
        html_path = self.output_dir / f"review_{datetime.now().strftime('%Y%m%d_%H%M%S')}.html"
        
        cards_to_review = []
        if self.review_file.exists():
            with open(self.review_file, 'r') as f:
                reader = csv.DictReader(f)
                cards_to_review = list(reader)
                
        html_content = """
<!DOCTYPE html>
<html>
<head>
    <title>Card Review - Manual Identification</title>
    <style>
        body { font-family: Arial, sans-serif; margin: 20px; }
        .card-review { 
            border: 2px solid #ddd; 
            padding: 15px; 
            margin: 20px 0;
            background: #f9f9f9;
        }
        .low-confidence { border-color: #ff6b6b; }
        .medium-confidence { border-color: #ffd93d; }
        .card-image { max-width: 300px; margin: 10px 0; }
        .info-grid { 
            display: grid; 
            grid-template-columns: repeat(2, 1fr); 
            gap: 10px;
            margin: 10px 0;
        }
        .correction-form {
            background: #e8f4e8;
            padding: 10px;
            margin-top: 10px;
            border-radius: 5px;
        }
        .correction-form input {
            margin: 5px;
            padding: 5px;
            width: 200px;
        }
        button {
            background: #4CAF50;
            color: white;
            padding: 10px 20px;
            border: none;
            border-radius: 4px;
            cursor: pointer;
        }
        button:hover { background: #45a049; }
        .reason {
            background: #fff3cd;
            padding: 8px;
            margin: 10px 0;
            border-radius: 4px;
            border-left: 4px solid #ffc107;
        }
    </style>
</head>
<body>
    <h1>Cards Requiring Manual Review</h1>
    <p>Total cards to review: <strong>""" + str(len(cards_to_review)) + """</strong></p>
    
    <div id="cards-container">
"""
        
        for card in cards_to_review:
            confidence = float(card['Confidence'].strip('%')) / 100
            confidence_class = 'low-confidence' if confidence < 0.5 else 'medium-confidence'
            
            html_content += f"""
        <div class="card-review {confidence_class}">
            <h3>Review Required: {card['Ximilar Name'] or 'Unknown'}</h3>
            
            <div class="reason">
                <strong>Reason:</strong> {card['Review Reason']}
            </div>
            
            <div class="info-grid">
                <div>
                    <strong>Ximilar Identification:</strong><br>
                    Name: {card['Ximilar Name']}<br>
                    Set: {card['Ximilar Set']}<br>
                    Number: {card['Ximilar Number']}<br>
                    Confidence: {card['Confidence']}
                </div>
                <div>
                    <strong>Image Path:</strong><br>
                    {card['Image Path']}<br>
                    <strong>Timestamp:</strong><br>
                    {card['Timestamp']}
                </div>
            </div>
            
            <div class="correction-form">
                <h4>Manual Correction:</h4>
                <input type="text" placeholder="Correct Name" id="name_{card['Image Path']}" 
                       value="{card['Manual Name']}">
                <input type="text" placeholder="Correct Set" id="set_{card['Image Path']}" 
                       value="{card['Manual Set']}">
                <input type="text" placeholder="Correct Number" id="number_{card['Image Path']}" 
                       value="{card['Manual Number']}">
                <input type="text" placeholder="Notes" id="notes_{card['Image Path']}" 
                       value="{card['Notes']}">
                <button onclick="saveCorrection('{card['Image Path']}')">Save Correction</button>
            </div>
        </div>
"""
        
        html_content += """
    </div>
    
    <script>
        function saveCorrection(imagePath) {
            const correction = {
                name: document.getElementById('name_' + imagePath).value,
                set_name: document.getElementById('set_' + imagePath).value,
                number: document.getElementById('number_' + imagePath).value,
                notes: document.getElementById('notes_' + imagePath).value
            };
            
            // In a real implementation, this would save to the server
            console.log('Saving correction for', imagePath, correction);
            alert('Correction saved! (In production, this would update the CSV/JSON files)');
        }
    </script>
</body>
</html>
"""
        
        with open(html_path, 'w') as f:
            f.write(html_content)
            
        return html_path