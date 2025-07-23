import google.generativeai as genai
from typing import Dict, Any, List
from app.core.config import settings
from app.schemas.responses import KeyMetric, Anomaly, BehavioralAnalyticsResult, RuleBreakdown

# Configure Google Gemini API
genai.configure(api_key=settings.GEMINI_API_KEY)

async def generate_behavioral_summary(
    customer_id: str,
    key_metrics: List[KeyMetric],
    anomalies: List[Anomaly],
    rules_breakdown: List[RuleBreakdown],
    overall_score: float,
    score_explanation: Dict[str, Any],
    tenant_config: Dict[str, Any]
) -> str:
    """
    Generates a human-readable narrative summary of financial behavior using Gemini LLM.
    """
    try:
        model = genai.GenerativeModel('gemini-pro')

        # Prepare context for the LLM
        metrics_text = "\n".join([f"- {m.name}: {m.value} {m.unit if m.unit else ''} ({m.description})" for m in key_metrics])
        anomalies_text = "\n".join([f"- {a.type}: {a.description} (Transaction: {a.transaction['description'] if a.transaction else 'N/A'})" for a in anomalies]) if anomalies else "No significant anomalies detected."
        rules_text = "\n".join([f"- {r.rule_name}: {r.condition_met} (Adjustment: {r.adjustment})" for r in rules_breakdown]) if rules_breakdown else "No specific tenant rules applied."

        llm_tone_guidelines = tenant_config.get("llm_tone_guidelines", {})
        tone_description = []
        if llm_tone_guidelines.get("professional"): tone_description.append("professional")
        if llm_tone_guidelines.get("concise"): tone_description.append("concise")
        if llm_tone_guidelines.get("avoid_jargon"): tone_description.append("avoid jargon")
        if llm_tone_guidelines.get("include_disclaimers"): tone_description.append("include clear disclaimers")
        
        tone_instruction = f"The tone should be {', '.join(tone_description) if tone_description else 'neutral and informative'}."

        prompt = f"""
        Analyze the following financial behavior data for customer {customer_id} and provide a concise, human-readable narrative summary.
        Focus on key financial health indicators, spending patterns, income stability, and any detected anomalies.
        Explain how these factors contribute to the overall behavioral score of {overall_score:.2f}.
        {tone_instruction}

        Financial Metrics:
        {metrics_text}

        Detected Anomalies:
        {anomalies_text}

        Tenant-Specific Rules Applied (if any):
        {rules_text}

        Score Explanation Factors (Key Drivers):
        {score_explanation}

        Based on this data, provide a comprehensive summary suitable for a financial analyst or a customer.
        Start with an overall assessment, then elaborate on positive and negative aspects, and conclude with key takeaways.
        """
        
        # Use asyncio.to_thread for blocking LLM API calls
        response = await asyncio.to_thread(model.generate_content, prompt)
        return response.text

    except Exception as e:
        print(f"Error generating LLM insights: {e}")
        return f"Could not generate detailed insights due to an internal error. Please review financial data directly. Error: {e}"