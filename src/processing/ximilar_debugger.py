"""Enhanced Ximilar debugging and validation module"""
import json
import logging
from typing import Dict, List, Optional, Tuple
from pathlib import Path
from datetime import datetime

logger = logging.getLogger(__name__)

class XimilarDebugger:
    """Debug and validate Ximilar API responses"""
    
    def __init__(self, output_dir: Path = None):
        self.output_dir = output_dir or Path("output/ximilar_debug")
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.debug_log = []
        
    def save_api_response(self, image_url: str, response: Dict, card_name: str = "unknown"):
        """Save API response for debugging"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{timestamp}_{card_name.replace(' ', '_')}_response.json"
        filepath = self.output_dir / filename
        
        debug_data = {
            "timestamp": timestamp,
            "image_url": image_url,
            "response": response,
            "analysis": self.analyze_response(response)
        }
        
        with open(filepath, 'w') as f:
            json.dump(debug_data, f, indent=2)
            
        logger.info(f"   📝 Saved debug response to: {filepath}")
        
    def analyze_response(self, response: Dict) -> Dict:
        """Analyze Ximilar response for quality issues"""
        analysis = {
            "has_identification": False,
            "confidence_score": 0,
            "alternatives_count": 0,
            "best_match_name": None,
            "issues": [],
            "recommendations": []
        }
        
        # Extract identification data
        records = response.get("records", [])
        if not records:
            analysis["issues"].append("No records in response")
            return analysis
            
        objects = records[0].get("_objects", [])
        if not objects:
            analysis["issues"].append("No objects detected")
            return analysis
            
        identification = objects[0].get("_identification", {})
        if not identification:
            analysis["issues"].append("No identification data")
            return analysis
            
        analysis["has_identification"] = True
        
        # Check best match
        best_match = identification.get("best_match", {})
        if best_match:
            analysis["best_match_name"] = best_match.get("name")
            
        # Check distances
        distances = identification.get("distances", [])
        if distances:
            analysis["confidence_score"] = 1 - distances[0] if distances[0] else 0
            
            if analysis["confidence_score"] < 0.5:
                analysis["issues"].append(f"Very low confidence: {analysis['confidence_score']:.2%}")
                analysis["recommendations"].append("Consider manual identification")
            elif analysis["confidence_score"] < 0.7:
                analysis["issues"].append(f"Low confidence: {analysis['confidence_score']:.2%}")
                analysis["recommendations"].append("Check alternatives carefully")
                
        # Check alternatives
        alternatives = identification.get("alternatives", [])
        analysis["alternatives_count"] = len(alternatives)
        
        # Check for mismatches
        if alternatives and best_match:
            best_name = best_match.get("name", "").lower()
            alt_names = [alt.get("name", "").lower() for alt in alternatives[:3]]
            
            # Check if best match shares any words with alternatives
            best_words = set(best_name.split())
            shares_words = False
            for alt_name in alt_names:
                alt_words = set(alt_name.split())
                if best_words & alt_words:
                    shares_words = True
                    break
                    
            if not shares_words and analysis["confidence_score"] < 0.7:
                analysis["issues"].append("Best match shares no words with alternatives")
                analysis["recommendations"].append("Likely misidentification - review alternatives")
                
        # Check tags
        tags = objects[0].get("_tags", {})
        
        # Check rotation
        rotation = tags.get("Rotation", [{}])[0].get("name")
        if rotation != "rotation_ok":
            analysis["issues"].append(f"Image rotation issue: {rotation}")
            analysis["recommendations"].append("Consider rotating image")
            
        # Check if graded
        graded = tags.get("Graded", [{}])[0].get("name")
        if graded == "yes":
            analysis["issues"].append("Card appears to be graded")
            analysis["recommendations"].append("Graded cards may affect identification")
            
        return analysis
        
    def validate_and_suggest(self, identification: Dict, alternatives: List[Dict]) -> Tuple[bool, Optional[Dict], str]:
        """
        Validate identification and suggest better alternative if needed
        
        Returns:
            (is_valid, better_alternative, reason)
        """
        confidence = identification.get("confidence", 0)
        name = identification.get("name", "").lower()
        set_name = identification.get("set_name", "").lower()
        
        # Very low confidence - always invalid
        if confidence < 0.3:
            return False, None, f"Confidence too low: {confidence:.2%}"
            
        # Check for obvious mismatches
        issues = []
        
        # Era mismatches
        if self._check_era_mismatch(name, set_name):
            issues.append("Era mismatch detected")
            
        # Check alternatives for better matches
        if alternatives and (confidence < 0.7 or issues):
            better_alt = self._find_better_alternative(identification, alternatives)
            if better_alt:
                return False, better_alt, f"Better alternative found: {' + '.join(issues)}"
                
        return len(issues) == 0, None, " | ".join(issues) if issues else "Valid"
        
    def _check_era_mismatch(self, card_name: str, set_name: str) -> bool:
        """Check for obvious era mismatches"""
        # Modern card types
        modern_types = [' v', ' vmax', ' vstar', 'v-union']
        # Old sets
        old_sets = ['base', 'jungle', 'fossil', 'team rocket', 'gym', 'neo', 
                   'expedition', 'aquapolis', 'skyridge', 'ex ruby', 'ex sapphire',
                   'diamond', 'pearl', 'platinum', 'heartgold', 'soulsilver',
                   'black', 'white', 'xy', 'sun', 'moon']
        
        # Check if modern card in old set
        for modern in modern_types:
            if modern in card_name:
                for old_set in old_sets:
                    if old_set in set_name:
                        return True
                        
        # Old card types
        old_types = [' ex', ' gx', ' lv.x', ' prime', ' legend', ' break']
        # Modern sets
        modern_sets = ['sword', 'shield', 'scarlet', 'violet', 'silver tempest',
                      'crown zenith', 'paldea', 'obsidian', 'temporal', 'paradox']
        
        # Check if old card in modern set
        for old_type in old_types:
            if old_type in card_name:
                for modern_set in modern_sets:
                    if modern_set in set_name:
                        return True
                        
        return False
        
    def _find_better_alternative(self, current: Dict, alternatives: List[Dict]) -> Optional[Dict]:
        """Find a better alternative from the list"""
        current_confidence = current.get("confidence", 0)
        current_name = current.get("name", "").lower()
        
        best_alt = None
        best_score = 0
        
        for alt in alternatives[:5]:  # Check top 5
            alt_confidence = alt.get("confidence", 0)
            alt_name = alt.get("name", "").lower()
            
            score = 0
            
            # Higher confidence
            if alt_confidence > current_confidence + 0.2:
                score += 50
                
            # Same base Pokemon name
            if current_name and alt_name:
                current_base = current_name.split()[0]
                alt_base = alt_name.split()[0]
                if current_base == alt_base:
                    score += 30
                    
            # No era mismatch
            alt_set = alt.get("set_name", "").lower()
            if not self._check_era_mismatch(alt_name, alt_set):
                score += 20
                
            if score > best_score:
                best_score = score
                best_alt = alt
                
        return best_alt if best_score >= 50 else None
        
    def generate_report(self) -> str:
        """Generate a summary report of all debug sessions"""
        report_path = self.output_dir / f"debug_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
        
        # Analyze all debug files
        issues_summary = {}
        total_files = 0
        
        for filepath in self.output_dir.glob("*_response.json"):
            total_files += 1
            with open(filepath, 'r') as f:
                data = json.load(f)
                
            analysis = data.get("analysis", {})
            for issue in analysis.get("issues", []):
                issues_summary[issue] = issues_summary.get(issue, 0) + 1
                
        # Generate report
        report_lines = [
            "Ximilar API Debug Report",
            "=" * 50,
            f"Total API calls analyzed: {total_files}",
            "",
            "Common Issues:",
            "-" * 30
        ]
        
        for issue, count in sorted(issues_summary.items(), key=lambda x: x[1], reverse=True):
            report_lines.append(f"{count:3d} - {issue}")
            
        report_content = "\n".join(report_lines)
        
        with open(report_path, 'w') as f:
            f.write(report_content)
            
        logger.info(f"Debug report saved to: {report_path}")
        return report_content