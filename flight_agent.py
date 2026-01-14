"""
AI Flight Search Agent - Enhanced Version
"""

import os
from datetime import datetime, timedelta
import json
from anthropic import Anthropic
import requests
from flask import Flask, request, jsonify, send_from_directory

app = Flask(__name__, static_folder='.')
client = Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY"))

class FlightSearchAgent:
    def __init__(self):
        self.serpapi_key = os.environ.get("SERPAPI_KEY")
        
    def search_flights(self, origin, destination, outbound_date, return_date=None):
        params = {
            "engine": "google_flights",
            "departure_id": origin,
            "arrival_id": destination,
            "outbound_date": outbound_date,
            "currency": "GBP",
            "hl": "en",
            "api_key": self.serpapi_key
        }
        
        if return_date:
            params["return_date"] = return_date
            params["type"] = "1"
        
        try:
            response = requests.get("https://serpapi.com/search", params=params)
            return response.json()
        except Exception as e:
            return {"error": str(e)}
    
    def search_hotels(self, destination, check_in, check_out):
        params = {
            "engine": "google_hotels",
            "q": destination,
            "check_in_date": check_in,
            "check_out_date": check_out,
            "currency": "GBP",
            "gl": "uk",
            "hl": "en",
            "api_key": self.serpapi_key
        }
        
        try:
            response = requests.get("https://serpapi.com/search", params=params)
            return response.json()
        except Exception as e:
            return {"error": str(e)}
    
    def analyze_flexible_dates(self, origin, destination, start_date, return_date, days_range=7):
        results = []
        base_date = datetime.strptime(start_date, "%Y-%m-%d")
        
        if return_date:
            return_date_obj = datetime.strptime(return_date, "%Y-%m-%d")
        
        for i in range(days_range):
            search_date = (base_date + timedelta(days=i)).strftime("%Y-%m-%d")
            search_return = (return_date_obj + timedelta(days=i)).strftime("%Y-%m-%d") if return_date else None
            
            flight_data = self.search_flights(origin, destination, search_date, search_return)
            
            if "best_flights" in flight_data:
                for flight in flight_data.get("best_flights", []):
                    results.append({
                        "outbound_date": search_date,
                        "return_date": search_return,
                        "price": flight.get("price"),
                        "duration": flight.get("total_duration"),
                        "airline": flight.get("flights", [{}])[0].get("airline") if flight.get("flights") else None,
                        "booking_link": f"https://www.google.com/travel/flights?q={origin}+to+{destination}+on+{search_date}"
                    })
        
        return results
    
    def create_enhanced_itinerary(self, destination, keywords, budget, duration_days, hotels):
        hotel_info = ""
        if hotels and "properties" in hotels:
            top_hotels = hotels["properties"][:3]
            hotel_info = "\n\nRecommended Hotels:\n"
            for hotel in top_hotels:
                hotel_info += f"- {hotel.get('name', 'N/A')}: £{hotel.get('rate_per_night', {}).get('lowest', 'N/A')} per night\n"
        
        prompt = f"""You are a travel planning expert. Create a detailed {duration_days}-day itinerary for {destination}.

Keywords/Interests: {', '.join(keywords)}
Budget: £{budget} (excluding flights)
Duration: {duration_days} days
{hotel_info}

Provide:
1. Daily Breakdown - Activities for each day
2. Cost Estimates - Specific prices
3. Accommodation - Hotel recommendations
4. Transportation - Getting around
5. Money-Saving Tips - Free activities
6. Must-See Attractions
7. Food Recommendations - By price range (£, ££, £££)
8. Alternative Options - Weather backups

Format as a detailed day-by-day plan."""

        message = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=3000,
            messages=[{"role": "user", "content": prompt}]
        )
        
        return message.content[0].text
    
    def find_best_value_flights(self, flight_results):
        if not flight_results:
            return []
        
        sorted_flights = sorted(flight_results, key=lambda x: x.get("price", float('inf')))
        prices = [f.get("price", 0) for f in flight_results if f.get("price")]
        avg_price = sum(prices) / len(prices) if prices else 0
        
        best_value = [f for f in sorted_flights if f.get("price", float('inf')) <= avg_price * 1.1]
        return best_value[:5]

agent = FlightSearchAgent()

@app.route('/')
def home():
    try:
        return send_from_directory('.', 'index.html')
    except Exception as e:
        return jsonify({"message": "Flight Search AI Agent - Enhanced", "error": str(e)})

@app.route('/itinerary', methods=['POST'])
def create_itinerary():
    data = request.json
    
    destination = data.get('destination')
    keywords = data.get('keywords', [])
    budget = data.get('budget', 1000)
    origin = data.get('origin')
    outbound_date = data.get('outbound_date')
    return_date = data.get('return_date')
    
    if not all([destination, origin, outbound_date]):
        return jsonify({"error": "Missing required fields"}), 400
    
    if return_date:
        start = datetime.strptime(outbound_date, "%Y-%m-%d")
        end = datetime.strptime(return_date, "%Y-%m-%d")
        duration_days = (end - start).days
    else:
        duration_days = data.get('duration_days', 5)
        return_date = (datetime.strptime(outbound_date, "%Y-%m-%d") + timedelta(days=duration_days)).strftime("%Y-%m-%d")
    
    all_flights = agent.analyze_flexible_dates(origin, destination, outbound_date, return_date, 7)
    best_flights = agent.find_best_value_flights(all_flights)
    
    hotels = agent.search_hotels(destination, outbound_date, return_date)
    
    flight_cost = best_flights[0].get('price', 0) if best_flights else 0
    remaining_budget = budget - flight_cost
    
    itinerary = agent.create_enhanced_itinerary(destination, keywords, remaining_budget, duration_days, hotels)
    
    hotel_options = []
    if hotels and "properties" in hotels:
        for hotel in hotels.get("properties", [])[:8]:
            hotel_options.append({
                "name": hotel.get("name", "N/A"),
                "price_per_night": hotel.get("rate_per_night", {}).get("lowest", "N/A"),
                "rating": hotel.get("overall_rating", "N/A"),
                "reviews": hotel.get("reviews", 0),
                "link": hotel.get("link", "#"),
                "description": hotel.get("description", "")[:150]
            })
    
    return jsonify({
        "destination": destination,
        "keywords": keywords,
        "total_budget": budget,
        "trip_duration": duration_days,
        "outbound_date": outbound_date,
        "return_date": return_date,
        "flight_options": best_flights[:5],
        "recommended_flight_cost": flight_cost,
        "hotel_options": hotel_options,
        "remaining_budget": remaining_budget,
        "itinerary": itinerary
    })

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 8080))
    app.run(host='0.0.0.0', port=port)
