"""
AI Flight Search Agent
Finds best value flights by analyzing price patterns and demand pricing
Creates itineraries based on keywords
"""

import os
from datetime import datetime, timedelta
import json
from anthropic import Anthropic
import requests
from flask import Flask, request, jsonify, send_from_directory

app = Flask(__name__, static_folder='.')

# Initialize Anthropic client
client = Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY"))

class FlightSearchAgent:
    def __init__(self):
        self.serpapi_key = os.environ.get("SERPAPI_KEY")
        
    def search_flights(self, origin, destination, date_from, date_to=None, max_price=None):
        """Search for flights using SerpAPI Google Flights"""
        if not date_to:
            date_to = date_from
            
        params = {
            "engine": "google_flights",
            "departure_id": origin,
            "arrival_id": destination,
            "outbound_date": date_from,
            "return_date": date_to,
            "currency": "GBP",
            "hl": "en",
            "api_key": self.serpapi_key
        }
        
        try:
            response = requests.get("https://serpapi.com/search", params=params)
            return response.json()
        except Exception as e:
            return {"error": str(e)}
    
    def analyze_flexible_dates(self, origin, destination, start_date, days_range=14):
        """Search across multiple dates to find best value"""
        results = []
        base_date = datetime.strptime(start_date, "%Y-%m-%d")
        
        for i in range(days_range):
            search_date = (base_date + timedelta(days=i)).strftime("%Y-%m-%d")
            flight_data = self.search_flights(origin, destination, search_date)
            
            if "best_flights" in flight_data:
                for flight in flight_data.get("best_flights", []):
                    results.append({
                        "date": search_date,
                        "price": flight.get("price"),
                        "duration": flight.get("total_duration"),
                        "flights": flight.get("flights", []),
                        "airline": flight.get("flights", [{}])[0].get("airline") if flight.get("flights") else None
                    })
        
        return results
    
    def create_itinerary_with_ai(self, destination, keywords, budget, duration_days):
        """Use Claude to create a personalized itinerary based on keywords"""
        
        prompt = f"""You are a travel planning expert. Create a detailed {duration_days}-day itinerary for {destination}.

Keywords/Interests: {', '.join(keywords)}
Budget: £{budget} total
Duration: {duration_days} days

Please provide:
1. Daily breakdown of activities aligned with the keywords
2. Estimated costs for each activity
3. Best neighborhoods to stay in
4. Local transportation tips
5. Money-saving recommendations
6. Must-see attractions matching the interests

Format as a structured day-by-day plan with budget tracking."""

        message = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=2000,
            messages=[{
                "role": "user",
                "content": prompt
            }]
        )
        
        return message.content[0].text
    
    def find_best_value_flights(self, flight_results):
        """Analyze flights to remove demand pricing influence and find best value"""
        
        if not flight_results:
            return []
        
        # Sort by price
        sorted_flights = sorted(flight_results, key=lambda x: x.get("price", float('inf')))
        
        # Calculate average price
        prices = [f.get("price", 0) for f in flight_results if f.get("price")]
        avg_price = sum(prices) / len(prices) if prices else 0
        
        # Find flights below average (avoiding demand pricing)
        best_value = [
            f for f in sorted_flights 
            if f.get("price", float('inf')) <= avg_price * 1.1  # Within 10% of average
        ]
        
        return best_value[:5]  # Return top 5 best value options

# Initialize agent
agent = FlightSearchAgent()

@app.route('/')
def home():
    """Serve the HTML frontend"""
    try:
        return send_from_directory('.', 'index.html')
    except Exception as e:
        return jsonify({
            "message": "Flight Search AI Agent",
            "status": "HTML file not found",
            "error": str(e),
            "endpoints": {
                "/search": "POST - Search for best value flights",
                "/itinerary": "POST - Create AI-powered itinerary"
            }
        })

@app.route('/search', methods=['POST'])
def search_flights():
    data = request.json
    
    origin = data.get('origin')
    destination = data.get('destination')
    start_date = data.get('start_date')
    flexible_days = data.get('flexible_days', 14)
    max_price = data.get('max_price')
    
    if not all([origin, destination, start_date]):
        return jsonify({"error": "Missing required fields"}), 400
    
    all_flights = agent.analyze_flexible_dates(origin, destination, start_date, flexible_days)
    
    if max_price:
        all_flights = [f for f in all_flights if f.get('price', float('inf')) <= max_price]
    
    best_value = agent.find_best_value_flights(all_flights)
    
    return jsonify({
        "origin": origin,
        "destination": destination,
        "total_options_found": len(all_flights),
        "best_value_flights": best_value,
        "average_price": sum(f.get('price', 0) for f in all_flights) / len(all_flights) if all_flights else 0,
        "price_range": {
            "min": min(f.get('price', 0) for f in all_flights) if all_flights else 0,
            "max": max(f.get('price', 0) for f in all_flights) if all_flights else 0
        }
    })

@app.route('/itinerary', methods=['POST'])
def create_itinerary():
    data = request.json
    
    destination = data.get('destination')
    keywords = data.get('keywords', [])
    budget = data.get('budget', 1000)
    duration_days = data.get('duration_days', 5)
    origin = data.get('origin')
    start_date = data.get('start_date')
    
    if not all([destination, origin, start_date]):
        return jsonify({"error": "Missing required fields"}), 400
    
    all_flights = agent.analyze_flexible_dates(origin, destination, start_date, 7)
    best_flights = agent.find_best_value_flights(all_flights)
    
    flight_cost = best_flights[0].get('price', 0) if best_flights else 0
    remaining_budget = budget - flight_cost
    
    itinerary = agent.create_itinerary_with_ai(
        destination, 
        keywords, 
        remaining_budget,
        duration_days
    )
    
    return jsonify({
        "destination": destination,
        "keywords": keywords,
        "total_budget": budget,
        "flight_options": best_flights[:3],
        "recommended_flight_cost": flight_cost,
        "remaining_budget": remaining_budget,
        "itinerary": itinerary
    })

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 8080))
    app.run(host='0.0.0.0', port=port)
