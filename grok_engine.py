"""
Grok Rule Engine - The Brain of Polydictor

Responsible for:
- Generating monitoring rules (accounts, keywords, filters)
- Analyzing tweets when requested by agent
- Refining rules based on performance metrics
- Making all strategic decisions
"""

import os
import json
import asyncio
import logging
from typing import Dict, List, Optional, Tuple
from datetime import datetime
from pathlib import Path
import aiohttp

logger = logging.getLogger(__name__)

GROK_API_KEY = os.getenv("GROK_API_KEY")
GROK_API_URL = "https://api.x.ai/v1/chat/completions"


class GrokEngine:
    """
    The strategic brain that makes all decisions.
    Agent simply executes these decisions.
    """
    
    def __init__(self):
        self.api_key = GROK_API_KEY
        
    async def _call_grok(self, prompt: str, max_tokens: int = 2000) -> Optional[str]:
        """Make API call to Grok"""
        if not self.api_key:
            logger.error("GROK_API_KEY not configured")
            return None
            
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        
        payload = {
            "model": "grok-3",
            "messages": [
                {
                    "role": "system",
                    "content": "You are a strategic intelligence analyst for prediction markets. You provide actionable intelligence by monitoring Twitter and analyzing relevant information."
                },
                {
                    "role": "user",
                    "content": prompt
                }
            ],
            "max_tokens": max_tokens,
            "temperature": 0.7
        }
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    GROK_API_URL,
                    headers=headers,
                    json=payload,
                    timeout=aiohttp.ClientTimeout(total=60)
                ) as response:
                    if response.status == 200:
                        data = await response.json()
                        return data['choices'][0]['message']['content']
                    else:
                        error_text = await response.text()
                        logger.error(f"Grok API error {response.status}: {error_text}")
                        return None
        except Exception as e:
            logger.error(f"Error calling Grok API: {e}")
            return None
    
    async def generate_initial_ruleset(
        self,
        event_slug: str,
        event_question: str,
        event_description: str,
        category: str,
        historical_context: str = None,
        recent_tweets: str = None
    ) -> Optional[Dict]:
        """
        Generate initial monitoring ruleset for an event.
        
        Returns:
        {
            "accounts": ["@account1", "@account2"],
            "keywords": ["keyword1", "keyword2"],
            "filters": {
                "relevance_threshold": 0.7,
                "credibility_threshold": 0.6,
                "exclude_patterns": ["spam", "bot"]
            },
            "priority_rules": {
                "high": ["conditions"],
                "medium": ["conditions"],
                "low": ["conditions"]
            },
            "budget_allocation": {
                "account_monitoring": 0.6,
                "keyword_search": 0.3,
                "analysis": 0.1
            }
        }
        """
        
        historical_section = ""
        if historical_context:
            historical_section = f"""

HISTORICAL MARKET CONTEXT (from Polymarket):
{historical_context[:2000]}"""
        
        recent_tweets_section = ""
        if recent_tweets:
            recent_tweets_section = f"""

RECENT TWITTER ACTIVITY (Last 48 hours):
{recent_tweets[:3000]}

This historical context provides baseline understanding. Your job is to set up FORWARD monitoring from this point going forward using Twitter intelligence.
"""
        
        prompt = f"""You are analyzing a Polymarket prediction market event to set up intelligent Twitter monitoring.

EVENT DETAILS:
Question: {event_question}
Description: {event_description}
Category: {category}
Slug: {event_slug}{historical_section}{recent_tweets_section}

TASK: Generate a monitoring ruleset in JSON format for FORWARD-LOOKING Twitter intelligence.

If RECENT TWITTER ACTIVITY is provided, use it to:
- Identify which accounts are most active/influential
- Validate keyword choices against real conversation
- Detect current narratives and sentiment trends

Your ruleset should include:

1. **accounts**: Top 5-10 Twitter accounts most likely to tweet relevant information about this event
   - Consider: experts, news sources, involved parties, analysts
   - Use real Twitter handles that exist
   - Format: ["@account", "@account"]

2. **keywords**: 10-15 essential keywords/phrases to monitor
   - Include variations, abbreviations, hashtags
   - Mix broad and specific terms
   - Format: ["keyword", "phrase"]

3. **priority_nodes**: CRITICAL - Define high-weight developments that bypass normal filters
   These are momentous developments that MUST be reported immediately:
   - Format: [
       {
         "type": "account_specific",  // Specific account tweeting specific topics
         "account": "@elonmusk",
         "keywords": ["bitcoin", "BTC"],
         "reason": "Elon's crypto tweets move markets instantly"
       },
       {
         "type": "account_any",  // Any tweet from this critical account
         "account": "@federalreserve",
         "reason": "Every Fed statement is market-moving"
       },
       {
         "type": "keyword_critical",  // Critical event keywords
         "keywords": ["SEC approval", "regulatory decision"],
         "min_followers": 10000,
         "reason": "Regulatory news is always high-priority"
       },
       {
         "type": "breaking_news",  // Breaking news from verified sources
         "keywords": ["BREAKING", "URGENT"],
         "verified_only": true,
         "reason": "Breaking news requires immediate attention"
       }
     ]
   Priority nodes SKIP pre-filtering and get immediate Grok analysis + user delivery

4. **filters**:
   - relevance_threshold: 0-1 (how relevant must tweet be)
   - credibility_threshold: 0-1 (minimum credibility score)
   - exclude_patterns: ["spam indicators", "bot patterns"]

5. **priority_rules**: Define what makes a tweet high/medium/low priority
   - high: ["from key account", "breaking news", "verified information"]
   - medium: ["relevant analysis", "community discussion"]
   - low: ["tangential mention", "speculation"]

6. **budget_allocation**: Distribute 1.0 across monitoring types
   - account_monitoring: % of effort
   - keyword_search: % of effort
   - analysis: % of effort

Return ONLY valid JSON, no markdown, no explanation.
"""
        
        response = await self._call_grok(prompt, max_tokens=2500)
        if not response:
            return None
            
        try:
            # Clean markdown if present
            if response.startswith("```"):
                response = response.split("```")[1]
                if response.startswith("json"):
                    response = response[4:]
            
            ruleset = json.loads(response.strip())
            logger.info(f"Generated initial ruleset for {event_slug}")
            return ruleset
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse Grok ruleset response: {e}")
            logger.error(f"Response: {response}")
            return None
    
    async def search_twitter_accounts(
        self,
        event_question: str,
        category: str
    ) -> List[str]:
        """
        Use Grok to search Twitter for relevant accounts.
        
        Returns list of Twitter handles.
        """
        prompt = f"""You are helping set up Twitter monitoring for a prediction market event.

EVENT: {event_question}
CATEGORY: {category}

Search your knowledge of Twitter and identify 10-15 real, active Twitter accounts that would most likely tweet relevant information about this event.

Consider:
- Subject matter experts
- News organizations covering this topic
- Key figures involved
- Influential analysts/commentators
- Official accounts

Return ONLY a JSON array of Twitter handles:
["@account1", "@account2", "@account3"]

Use real accounts that exist and are active. No markdown, just the JSON array.
"""
        
        response = await self._call_grok(prompt, max_tokens=1000)
        if not response:
            return []
            
        try:
            # Clean response
            response = response.strip()
            if response.startswith("```"):
                response = response.split("```")[1]
                if response.startswith("json"):
                    response = response[4:]
            
            accounts = json.loads(response.strip())
            return accounts if isinstance(accounts, list) else []
        except Exception as e:
            logger.error(f"Failed to parse Twitter accounts: {e}")
            return []
    
    async def analyze_tweet(
        self,
        tweet_text: str,
        tweet_author: str,
        event_question: str,
        ruleset: Dict
    ) -> Optional[Dict]:
        """
        Analyze a single tweet for relevance and intelligence value.
        
        Returns:
        {
            "relevant": true/false,
            "relevance_score": 0-1,
            "sentiment": "bullish"/"bearish"/"neutral",
            "credibility_score": 0-1,
            "insights": "Key insights extracted",
            "priority": "high"/"medium"/"low",
            "confidence": 0-1
        }
        """
        prompt = f"""Analyze this tweet for a Polymarket prediction market event.

EVENT: {event_question}

TWEET:
From: {tweet_author}
Text: {tweet_text}

MONITORING RULES:
Relevance Threshold: {ruleset.get('filters', {}).get('relevance_threshold', 0.7)}
Credibility Threshold: {ruleset.get('filters', {}).get('credibility_threshold', 0.6)}

TASK: Analyze this tweet and return JSON:

{{
    "relevant": true/false (does it relate to the event?),
    "relevance_score": 0-1 (how relevant?),
    "sentiment": "bullish"/"bearish"/"neutral" (for the event outcome),
    "credibility_score": 0-1 (how credible is this information?),
    "insights": "1-2 sentences of key insights",
    "priority": "high"/"medium"/"low",
    "confidence": 0-1 (your confidence in this analysis)
}}

Consider:
- Does this tweet provide actionable intelligence?
- Is the author credible on this topic?
- Is this news, analysis, or speculation?
- Does it move the probability needle?

Return ONLY valid JSON.
"""
        
        response = await self._call_grok(prompt, max_tokens=500)
        if not response:
            return None
            
        try:
            if response.startswith("```"):
                response = response.split("```")[1]
                if response.startswith("json"):
                    response = response[4:]
            
            analysis = json.loads(response.strip())
            return analysis
        except Exception as e:
            logger.error(f"Failed to parse tweet analysis: {e}")
            return None
    
    async def synthesize_hourly_digest(
        self,
        event_question: str,
        analyzed_tweets: List[Dict]
    ) -> Optional[str]:
        """
        Synthesize past hour's intelligence into a digest.
        
        Returns formatted digest text for delivery to users.
        """
        if not analyzed_tweets:
            return None
            
        # Prepare tweet summaries
        tweet_summaries = []
        for i, tweet in enumerate(analyzed_tweets[:20], 1):  # Max 20 tweets
            summary = f"{i}. @{tweet['author']}: {tweet['insights']} (Priority: {tweet['priority']}, Sentiment: {tweet['sentiment']})"
            tweet_summaries.append(summary)
        
        prompt = f"""Synthesize the past hour's Twitter intelligence for this Polymarket event.

EVENT: {event_question}

ANALYZED TWEETS ({len(analyzed_tweets)} total):
{chr(10).join(tweet_summaries)}

Create a concise digest (300-400 words) that includes:

1. **Summary**: What happened this hour?
2. **Sentiment Distribution**: Overall bullish/bearish/neutral breakdown
3. **Key Signals**: Top 3-5 most important pieces of information
4. **Market Impact**: How might this affect the prediction market?
5. **Confidence Level**: High/Medium/Low for the intelligence quality

Write in clear, professional style suitable for Telegram delivery.
"""
        
        response = await self._call_grok(prompt, max_tokens=1000)
        return response
    
    async def refine_ruleset(
        self,
        event_slug: str,
        current_ruleset: Dict,
        performance_metrics: Dict
    ) -> Optional[Dict]:
        """
        Refine monitoring rules based on 6-hour performance.
        
        Performance metrics should include:
        {
            "total_tweets": int,
            "relevant_tweets": int,
            "high_priority_tweets": int,
            "avg_relevance_score": float,
            "avg_credibility_score": float,
            "account_performance": {
                "@account": {"tweets": int, "avg_relevance": float}
            },
            "keyword_performance": {
                "keyword": {"matches": int, "avg_relevance": float}
            },
            "user_engagement": {"delivered": int, "clicks": int},
            "budget_used": {"account_monitoring": float, "keyword_search": float}
        }
        
        Returns updated ruleset.
        """
        prompt = f"""You are refining Twitter monitoring rules for a Polymarket event based on performance data.

CURRENT RULESET:
{json.dumps(current_ruleset, indent=2)}

PERFORMANCE METRICS (past 6 hours):
{json.dumps(performance_metrics, indent=2)}

ANALYSIS NEEDED:
1. Are we monitoring the right accounts? (Add/remove based on performance)
2. Are keywords effective? (Refine based on match quality)
3. Are filters too strict or too loose? (Adjust thresholds)
4. Is budget allocation optimal? (Shift resources to what works)
5. Are priority rules accurate? (Improve classification)

GOAL: Maximize relevant, high-quality intelligence while minimizing noise.

Return an UPDATED ruleset in the same JSON format as current ruleset.
Include all fields, even if unchanged.
Only JSON, no markdown or explanation.
"""
        
        response = await self._call_grok(prompt, max_tokens=2500)
        if not response:
            return current_ruleset  # Return unchanged if refinement fails
            
        try:
            if response.startswith("```"):
                response = response.split("```")[1]
                if response.startswith("json"):
                    response = response[4:]
            
            refined_ruleset = json.loads(response.strip())
            logger.info(f"Refined ruleset for {event_slug}")
            return refined_ruleset
        except Exception as e:
            logger.error(f"Failed to parse refined ruleset: {e}")
            return current_ruleset


# Singleton instance
grok_engine = GrokEngine()
