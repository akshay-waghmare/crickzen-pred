from typing import List, Dict, Any
import structlog

logger = structlog.get_logger()

def select_champion(results: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Selects the champion model based on Brier score.
    
    Args:
        results: List of dictionaries containing model metrics and metadata.
                 Expected keys: 'model_name', 'brier_score', 'ece', ...
    
    Returns:
        The dictionary corresponding to the best model.
    """
    if not results:
        raise ValueError("No results provided for selection.")
    
    # Sort by Brier score (lower is better)
    # Ensure brier_score is present
    valid_results = [r for r in results if 'brier_score' in r]
    
    if not valid_results:
        raise ValueError("No results with 'brier_score' found.")
    
    sorted_results = sorted(valid_results, key=lambda x: x['brier_score'])
    
    champion = sorted_results[0]
    
    logger.info("Champion selected", 
                model=champion.get('model_name'), 
                brier_score=champion.get('brier_score'))
    
    return champion
