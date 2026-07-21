from collections import defaultdict
import statistics
from .contracts import AgentStance, ConsensusResult, OptionResult

def aggregate_scores(
    all_stances: list[AgentStance],
    options: list[str],
    scoring_weights: dict[str, float] | None = None,
) -> ConsensusResult:
    """
    Deterministic math to calculate the winner, confidence, and agreement.
    No LLM calls are made in this function.
    """
    # 1. Group scores, weights and reasoning by option
    option_weighted_scores = defaultdict(list)  # list of (score, weight)
    option_scores = defaultdict(list)  # list of raw scores for agreement variance math
    option_reasoning = defaultdict(list)
    
    for stance in all_stances:
        weight = 1.0
        if scoring_weights and stance.agent_name in scoring_weights:
            weight = scoring_weights[stance.agent_name]
        option_weighted_scores[stance.option].append((stance.score, weight))
        option_scores[stance.option].append(stance.score)
        option_reasoning[stance.option].append(stance.reasoning)
        
    # 2. Calculate average scores and identify the winner
    breakdown = []
    winning_option = None
    highest_avg = -1.0
    
    for opt in options:
        weighted_data = option_weighted_scores.get(opt, [])
        if weighted_data:
            total_weighted_score = sum(score * w for score, w in weighted_data)
            total_weight = sum(w for _, w in weighted_data)
            avg_score = round(total_weighted_score / total_weight if total_weight > 0 else 5.0, 2)
        else:
            avg_score = 5.0
        
        if avg_score > highest_avg:
            highest_avg = avg_score
            winning_option = opt
            
        scores = option_scores.get(opt, [5.0])
        breakdown.append({
            "option": opt, 
            "average_score": avg_score, 
            "scores_list": scores,
            "reasons": option_reasoning.get(opt, [])
        })

    # 3. Format the OptionResult objects (and generate "why it lost" text)
    final_breakdown = []
    for data in breakdown:
        why_lost = None
        if data["option"] != winning_option:
            # Simply concatenate the critiques for the losing options
            why_lost = " | ".join(data["reasons"])
            
        final_breakdown.append(
            OptionResult(
                option=data["option"],
                average_score=data["average_score"],
                why_it_lost=why_lost
            )
        )

    # 4. Calculate Confidence and Agreement Metrics deterministically
    # Confidence: How close is the winning score to a perfect 10?
    confidence_pct = round((highest_avg / 10.0) * 100, 1)
    
    # Agreement: How tight was the variance among agents for the winning option?
    winning_scores = option_scores[winning_option]
    if len(winning_scores) > 1:
        variance = statistics.variance(winning_scores)
        # Assuming max variance for 1-10 scale is ~20, normalize it to a percentage
        agreement_pct = round(max(0, 100 - (variance * 5)), 1)
    else:
        agreement_pct = 100.0
        
    disagreement_pct = round(100.0 - agreement_pct, 1)

    # 5. Extract Risks (pulling reasoning from the lowest scores overall)
    risks = []
    for stance in all_stances:
        if stance.score <= 4.0:
            risks.append(f"[{stance.agent_name} on {stance.option}] {stance.reasoning}")

    return ConsensusResult(
        winning_option=winning_option,
        confidence_pct=confidence_pct,
        agreement_pct=agreement_pct,
        disagreement_pct=disagreement_pct,
        risks=risks,
        option_breakdown=final_breakdown,
        rationale=f"The moderator calculated {winning_option} as the winner with an average score of {highest_avg}/10."
    )
