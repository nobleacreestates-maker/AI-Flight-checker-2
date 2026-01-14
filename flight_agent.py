"""
AI Flight Search Agent - Comprehensive Travel Planning Platform
With Airbnb, Hotels, Images, Flight Times, and Enhanced Restaurant Recommendations
"""

import os
from datetime import datetime, timedelta
import json
from anthropic import Anthropic
import requests
from flask import Flask, request, jsonify, send_from_directory

app = Flask(__name__, static_folder='.')
client = Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY"))

class TravelPlanningAgent:
    def __init__(self):
        self.serpapi_key = os.environ.get("SERPAPI_KEY")
        
    def search_flights(self, origin, destination, outbound_date, return_date=None):
        """Search flights with detailed times and prices"""
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
            response = requests.get("https://serpapi.com/search", params=params, timeout=30)
            return response.json()
        except Exception as e:
            print(f"Flight search error: {e}")
            return {"error": str(e)}
    
    def search_hotels(self, destination, check_in, check_out):
        """Search hotels with images and detailed info"""
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
            response = requests.get("https://serpapi.com/search", params=params, timeout=30)
            return response.json()
        except Exception as e:
            print(f"Hotel search error: {e}")
            return {"error": str(e)}
    
    def search_airbnb(self, destination, check_in, check_out):
        """Search Airbnb listings"""
        check_in_date = datetime.strptime(check_in, "%Y-%m-%d")
        check_out_date = datetime.strptime(check_out, "%Y-%m-%d")
        nights = (check_out_date - check_in_date).days
        
        params = {
            "engine": "google",
            "q": f"airbnb {destination}",
            "api_key": self.serpapi_key,
            "num": 10
        }
        
        try:
            response = requests.get("https://serpapi.com/search", params=params, timeout=30)
            results = response.json()
            
            airbnb_listings = []
            if "organic_results" in results:
                for result in results["organic_results"][:8]:
                    if "airbnb" in result.get("link", "").lower():
                        airbnb_listings.append({
                            "name": result.get("title", "Airbnb Listing"),
                            "description": result.get("snippet", ""),
                            "link": result.get("link", "#"),
                            "price_per_night": "50-150",
                            "total_price": f"{nights * 75}",
                            "type": "Entire home/Private room"
                        })
            
            return airbnb_listings
        except Exception as e:
            print(f"Airbnb search error: {e}")
            return []
    
    def analyze_flexible_dates(self, origin, destination, start_date, return_date, days_range=7):
        """Search flights across flexible dates with detailed flight info"""
        results = []
        base_date = datetime.strptime(start_date, "%Y-%m-%d")
        
        if return_date:
            return_date_obj = datetime.strptime(return_date, "%Y-%m-%d")
        
        for i in range(days_range):
            search_date = (base_date + timedelta(days=i)).strftime("%Y-%m-%d")
            search_return = (return_date_obj + timedelta(days=i)).strftime("%Y-%m-%d") if return_date else None
            
            flight_data = self.search_flights(origin, destination, search_date, search_return)
            
            if "best_flights" in flight_data:
                for flight in flight_data.get("best_flights", [])[:3]:
                    flights_info = flight.get("flights", [])
                    
                    outbound_flight = flights_info[0] if flights_info else {}
                    
                    return_flight = None
                    if len(flights_info) > 1:
                        return_flight = flights_info[1]
                    
                    flight_details = {
                        "outbound_date": search_date,
                        "return_date": search_return,
                        "price": flight.get("price"),
                        "total_duration": flight.get("total_duration"),
                        "airline": outbound_flight.get("airline", "Unknown"),
                        "airline_logo": outbound_flight.get("airline_logo", ""),
                        
                        "outbound_departure_time": outbound_flight.get("departure_airport", {}).get("time", ""),
                        "outbound_arrival_time": outbound_flight.get("arrival_airport", {}).get("time", ""),
                        "outbound_departure_airport": outbound_flight.get("departure_airport", {}).get("id", origin),
                        "outbound_arrival_airport": outbound_flight.get("arrival_airport", {}).get("id", destination),
                        "outbound_duration": outbound_flight.get("duration"),
                        
                        "return_departure_time": return_flight.get("departure_airport", {}).get("time", "") if return_flight else "",
                        "return_arrival_time": return_flight.get("arrival_airport", {}).get("time", "") if return_flight else "",
                        "return_duration": return_flight.get("duration") if return_flight else "",
                        
                        "booking_link": f"https://www.google.com/travel/flights?q={origin}+to+{destination}+on+{search_date}",
                        "layovers": outbound_flight.get("layovers", [])
                    }
                    
                    results.append(flight_details)
        
        return results
    
    def create_structured_itinerary(self, destination, keywords, budget, duration_days, hotels):
        """Create comprehensive structured itinerary with AI"""
        hotel_info = ""
        if hotels and "properties" in hotels:
            top_hotels = hotels["properties"][:3]
            hotel_info = "\n\nTop Hotels:\n"
            for hotel in top_hotels:
                hotel_info += f"- {hotel.get('name', 'N/A')}: £{hotel.get('rate_per_night', {}).get('lowest', 'N/A')}/night\n"
        
        prompt = f"""Create a detailed {duration_days}-day structured itinerary for {destination}.

IMPORTANT: Return ONLY valid JSON with this exact structure:
{{
  "overview": {{
    "destination": "{destination}",
    "best_time_to_visit": "description",
    "getting_around": "transport tips",
    "money_saving_tips": ["tip1", "tip2", "tip3"],
    "local_customs": "brief cultural tips"
  }},
  "daily_itinerary": [
    {{
      "day": 1,
      "theme": "Day theme",
      "morning": {{
        "time": "9:00 AM",
        "activity": "Activity name",
        "description": "What to do",
        "cost": 15,
        "duration": "2 hours",
        "location": "Specific area/neighborhood"
      }},
      "afternoon": {{
        "time": "2:00 PM",
        "activity": "Activity name",
        "description": "What to do",
        "cost": 25,
        "duration": "3 hours",
        "location": "Specific area/neighborhood"
      }},
      "evening": {{
        "time": "7:00 PM",
        "activity": "Activity name",
        "description": "What to do",
        "cost": 35,
        "duration": "2 hours",
        "location": "Specific area/neighborhood"
      }},
      "daily_total": 75
    }}
  ],
  "restaurants": {{
    "breakfast": [
      {{
        "name": "Restaurant name",
        "cuisine": "cuisine type",
        "price_per_person": 12,
        "rating": 4.5,
        "description": "Why to visit",
        "neighborhood": "Area name",
        "signature_dish": "Popular dish"
      }}
    ],
    "lunch": [
      {{
        "name": "Restaurant name",
        "cuisine": "cuisine type",
        "price_per_person": 18,
        "rating": 4.7,
        "description": "Why to visit",
        "neighborhood": "Area name",
        "signature_dish": "Popular dish"
      }}
    ],
    "dinner": [
      {{
        "name": "Restaurant name",
        "cuisine": "cuisine type",
        "price_per_person": 35,
        "rating": 4.8,
        "description": "Why to visit",
        "neighborhood": "Area name",
        "signature_dish": "Popular dish"
      }}
    ]
  }},
  "budget_summary": {{
    "activities": 200,
    "food": 300,
    "transport": 50,
    "accommodation_estimate": 400,
    "total_estimate": 950
  }}
}}

User interests: {', '.join(keywords)}
Budget available: £{budget}
{hotel_info}

Include 5-6 restaurants for each meal type (breakfast, lunch, dinner).
Provide realistic star ratings (out of 5) and accurate average prices per person in GBP.

Respond ONLY with valid JSON."""

        try:
            message = client.messages.create(
                model="claude-sonnet-4-20250514",
                max_tokens=4000,
                messages=[{"role": "user", "content": prompt}]
            )
            
            response_text = message.content[0].text
            
            # Clean and parse JSON
            if "```json" in response_text:
                response_text = response_text.split("```json")[1].split("```")[0].strip()
            elif "```" in response_text:
                response_text = response_text.split("```")[1].split("```")[0].strip()
            
            return json.loads(response_text)
        except Exception as e:
            print(f"Itinerary creation error: {e}")
            return {
                "overview": {"destination": destination},
                "daily_itinerary": [],
                "restaurants": {"breakfast": [], "lunch": [], "dinner": []},
                "budget_summary": {}
            }
    
    def find_best_value_flights(self, flight_results):
        """Sort and filter flights by value"""
        if not flight_results:
            return []
        
        sorted_flights = sorted(flight_results, key=lambda x: x.get("price", float('inf')))
        prices = [f.get("price", 0) for f in flight_results if f.get("price")]
        avg_price = sum(prices) / len(prices) if prices else 0
        
        best_value = [f for f in sorted_flights if f.get("price", float('inf')) <= avg_price * 1.2]
        return best_value[:8]

agent = TravelPlanningAgent()

@app.route('/')
def home():
    try:
        return send_from_directory('.', 'index.html')
    except Exception as e:
        return jsonify({"message": "Travel Planning AI Agent", "error": str(e)})

@app.route('/itinerary', methods=['POST'])
def create_itinerary():
    data = request.json
    
    destination = data.get('destination')
    keywords = data.get('keywords', [])
    budget = data.get('budget', 1000)
    origin = data.get('origin')
    outbound_date = data.get('outbound_date')
    return_date = data.get('return_date')
    accommodation_type = data.get('accommodation_type', 'hotel')
    
    if not all([destination, origin, outbound_date]):
        return jsonify({"error": "Missing required fields"}), 400
    
    # Calculate trip duration
    if return_date:
        start = datetime.strptime(outbound_date, "%Y-%m-%d")
        end = datetime.strptime(return_date, "%Y-%m-%d")
        duration_days = (end - start).days
    else:
        duration_days = data.get('duration_days', 5)
        return_date = (datetime.strptime(outbound_date, "%Y-%m-%d") + timedelta(days=duration_days)).strftime("%Y-%m-%d")
    
    # Search flights
    all_flights = agent.analyze_flexible_dates(origin, destination, outbound_date, return_date, 7)
    best_flights = agent.find_best_value_flights(all_flights)
    
    # Search accommodations
    hotel_options = []
    airbnb_options = []
    
    if accommodation_type in ['hotel', 'mixed']:
        hotels = agent.search_hotels(destination, outbound_date, return_date)
        if hotels and "properties" in hotels:
            for hotel in hotels.get("properties", [])[:10]:
                hotel_options.append({
                    "name": hotel.get("name", "N/A"),
                    "price_per_night": hotel.get("rate_per_night", {}).get("lowest", "N/A"),
                    "total_price": hotel.get("total_rate", {}).get("lowest", "N/A"),
                    "rating": hotel.get("overall_rating", "N/A"),
                    "reviews": hotel.get("reviews", 0),
                    "link": hotel.get("link", "#"),
                    "description": hotel.get("description", "")[:200],
                    "images": hotel.get("images", [])[:3],
                    "amenities": hotel.get("amenities", [])[:5],
                    "type": "hotel"
                })
    
    if accommodation_type in ['airbnb', 'mixed']:
        airbnb_listings = agent.search_airbnb(destination, outbound_date, return_date)
        for listing in airbnb_listings:
            airbnb_options.append({
                "name": listing.get("name"),
                "price_per_night": listing.get("price_per_night"),
                "total_price": listing.get("total_price"),
                "description": listing.get("description"),
                "link": listing.get("link"),
                "type": "airbnb",
                "property_type": listing.get("type")
            })
    
    # Calculate costs
    flight_cost = best_flights[0].get('price', 0) if best_flights else 0
    remaining_budget = budget - flight_cost
    
    # Create itinerary
    itinerary = agent.create_structured_itinerary(
        destination, 
        keywords, 
        remaining_budget, 
        duration_days, 
        hotels if accommodation_type in ['hotel', 'mixed'] else None
    )
    
    return jsonify({
        "destination": destination,
        "keywords": keywords,
        "total_budget": budget,
        "trip_duration": duration_days,
        "outbound_date": outbound_date,
        "return_date": return_date,
        "flight_options": best_flights,
        "recommended_flight_cost": flight_cost,
        "hotel_options": hotel_options,
        "airbnb_options": airbnb_options,
        "accommodation_type": accommodation_type,
        "remaining_budget": remaining_budget,
        "itinerary": itinerary
    })

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 8080))
    app.run(host='0.0.0.0', port=port)
