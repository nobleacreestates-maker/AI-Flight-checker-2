"""
AI Flight Search Agent - Comprehensive Version
Includes Airbnb, hotel images, flight times, and smart sorting
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
        """Search flights with detailed timing information"""
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
        """Search hotels with images"""
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
    
    def search_airbnb(self, destination, check_in, check_out):
        """Search Airbnb listings"""
        params = {
            "engine": "airbnb",
            "location": destination,
            "check_in": check_in,
            "check_out": check_out,
            "currency": "GBP",
            "api_key": self.serpapi_key
        }
        
        try:
            response = requests.get("https://serpapi.com/search", params=params)
            return response.json()
        except Exception as e:
            return {"error": str(e)}
    
    def calculate_time_in_destination(self, outbound_departure, outbound_arrival, return_departure, return_arrival):
        """Calculate total time spent in destination"""
        try:
            # Parse times (format: "HH:MM" or "H:MM AM/PM")
            out_dep = self.parse_time(outbound_departure)
            out_arr = self.parse_time(outbound_arrival)
            ret_dep = self.parse_time(return_departure)
            ret_arr = self.parse_time(return_arrival)
            
            # Calculate hours in destination (simplified)
            # From arrival on day 1 to departure on last day
            return ret_dep - out_arr if ret_dep > out_arr else 24 + ret_dep - out_arr
        except:
            return 0
    
    def parse_time(self, time_str):
        """Parse time string to hours"""
        try:
            if 'AM' in time_str or 'PM' in time_str:
                time_obj = datetime.strptime(time_str.strip(), "%I:%M %p")
            else:
                time_obj = datetime.strptime(time_str.strip(), "%H:%M")
            return time_obj.hour + time_obj.minute / 60
        except:
            return 12  # Default noon
    
    def analyze_flexible_dates(self, origin, destination, start_date, return_date, days_range=7):
        """Search flights with detailed timing and smart sorting"""
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
                    outbound_flights = flight.get("flights", [])
                    
                    # Extract outbound flight details
                    outbound_info = {}
                    if outbound_flights and len(outbound_flights) > 0:
                        first_leg = outbound_flights[0]
                        last_leg = outbound_flights[-1]
                        outbound_info = {
                            "departure_time": first_leg.get("departure_airport", {}).get("time"),
                            "arrival_time": last_leg.get("arrival_airport", {}).get("time"),
                            "departure_airport": first_leg.get("departure_airport", {}).get("id"),
                            "arrival_airport": last_leg.get("arrival_airport", {}).get("id")
                        }
                    
                    # Extract return flight details if round trip
                    return_info = {}
                    if search_return and len(outbound_flights) > 1:
                        # SerpAPI structure varies, attempt to get return leg
                        return_info = {
                            "departure_time": "TBD",
                            "arrival_time": "TBD"
                        }
                    
                    results.append({
                        "outbound_date": search_date,
                        "return_date": search_return,
                        "price": flight.get("price"),
                        "duration": flight.get("total_duration"),
                        "airline": outbound_flights[0].get("airline") if outbound_flights else None,
                        "airline_logo": outbound_flights[0].get("airline_logo") if outbound_flights else None,
                        "outbound_departure_time": outbound_info.get("departure_time", "TBD"),
                        "outbound_arrival_time": outbound_info.get("arrival_time", "TBD"),
                        "return_departure_time": return_info.get("departure_time", "TBD"),
                        "return_arrival_time": return_info.get("arrival_time", "TBD"),
                        "layovers": len(outbound_flights) - 1 if outbound_flights else 0,
                        "booking_link": f"https://www.google.com/travel/flights?q={origin}+to+{destination}+on+{search_date}",
                        "time_in_destination": 0  # Will be calculated
                    })
        
        return results
    
    def sort_flights_by_value(self, flight_results):
        """Sort by best value: earliest departure + latest return + lowest price"""
        if not flight_results:
            return []
        
        def flight_score(flight):
            price = flight.get("price", 999999)
            
            # Earlier outbound departure is better (convert to hours, lower is better)
            out_dep = self.parse_time(flight.get("outbound_departure_time", "12:00"))
            out_score = out_dep  # Lower is better (earlier)
            
            # Later return departure is better (higher is better, so negate)
            ret_dep = self.parse_time(flight.get("return_departure_time", "12:00"))
            ret_score = -ret_dep  # Negative so higher time = lower score
            
            # Normalize price (assume average is around 150)
            price_score = price / 150
            
            # Combined score: 40% price, 30% early departure, 30% late return
            return (price_score * 0.4) + (out_score / 24 * 0.3) + (abs(ret_score) / 24 * 0.3)
        
        sorted_flights = sorted(flight_results, key=flight_score)
        return sorted_flights[:10]
    
    def create_structured_itinerary(self, destination, keywords, budget, duration_days, hotels_data, airbnb_data):
        """Create structured itinerary with accommodation options"""
        
        hotel_info = ""
        if hotels_data and "properties" in hotels_data:
            hotel_info = "\n\nTop Hotels:\n"
            for hotel in hotels_data["properties"][:3]:
                hotel_info += f"- {hotel.get('name', 'N/A')}: £{hotel.get('rate_per_night', {}).get('lowest', 'N/A')}/night\n"
        
        airbnb_info = ""
        if airbnb_data and "properties" in airbnb_data:
            airbnb_info = "\n\nTop Airbnbs:\n"
            for listing in airbnb_data.get("properties", [])[:3]:
                airbnb_info += f"- {listing.get('name', 'N/A')}: £{listing.get('rate', 'N/A')}/night\n"
        
        prompt = f"""Create a {duration_days}-day structured itinerary for {destination}.

IMPORTANT: Return ONLY valid JSON with this exact structure:
{{
  "overview": {{
    "destination": "{destination}",
    "best_time_to_visit": "season description",
    "getting_around": "transport tips",
    "money_saving_tips": ["tip1", "tip2", "tip3"]
  }},
  "daily_itinerary": [
    {{
      "day": 1,
      "theme": "Day theme",
      "morning": {{
        "time": "9:00 AM",
        "activity": "Activity name",
        "description": "Brief what to do",
        "cost": 15,
        "duration": "2 hours"
      }},
      "afternoon": {{
        "time": "2:00 PM",
        "activity": "Activity name",
        "description": "Brief what to do",
        "cost": 25,
        "duration": "3 hours"
      }},
      "evening": {{
        "time": "7:00 PM",
        "activity": "Activity name",
        "description": "Brief what to do",
        "cost": 35,
        "duration": "2 hours"
      }},
      "daily_total": 75
    }}
  ],
  "restaurants": [
    {{
      "name": "Restaurant name",
      "type": "cuisine",
      "price_range": "££",
      "average_cost": 25,
      "description": "Why visit",
      "best_for": "lunch"
    }}
  ],
  "budget_summary": {{
    "activities": 200,
    "food": 300,
    "transport": 50,
    "accommodation_estimate": 400,
    "total_estimate": 950
  }}
}}

Interests: {', '.join(keywords)}
Budget: £{budget}
{hotel_info}
{airbnb_info}

Respond ONLY with JSON, no other text."""

        message = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=4000,
            messages=[{"role": "user", "content": prompt}]
        )
        
        response_text = message.content[0].text
        
        try:
            if "```json" in response_text:
                response_text = response_text.split("```json")[1].split("```")[0].strip()
            elif "```" in response_text:
                response_text = response_text.split("```")[1].split("```")[0].strip()
            
            return json.loads(response_text)
        except:
            return {
                "overview": {"destination": destination, "description": response_text[:500]},
                "daily_itinerary": [],
                "restaurants": [],
                "budget_summary": {},
                "raw_text": response_text
            }

agent = FlightSearchAgent()

@app.route('/')
def home():
    try:
        return send_from_directory('.', 'index.html')
    except Exception as e:
        return jsonify({"message": "Flight Search AI Agent", "error": str(e)})

@app.route('/itinerary', methods=['POST'])
def create_itinerary():
    data = request.json
    
    destination = data.get('destination')
    keywords = data.get('keywords', [])
    budget = data.get('budget', 1000)
    origin = data.get('origin')
    outbound_date = data.get('outbound_date')
    return_date = data.get('return_date')
    accommodation_type = data.get('accommodation_type', 'hotels')  # 'hotels', 'airbnb', or 'both'
    
    if not all([destination, origin, outbound_date]):
        return jsonify({"error": "Missing required fields"}), 400
    
    if return_date:
        start = datetime.strptime(outbound_date, "%Y-%m-%d")
        end = datetime.strptime(return_date, "%Y-%m-%d")
        duration_days = (end - start).days
    else:
        duration_days = data.get('duration_days', 5)
        return_date = (datetime.strptime(outbound_date, "%Y-%m-%d") + timedelta(days=duration_days)).strftime("%Y-%m-%d")
    
    # Search flights with smart sorting
    all_flights = agent.analyze_flexible_dates(origin, destination, outbound_date, return_date, 7)
    best_flights = agent.sort_flights_by_value(all_flights)
    
    # Search accommodation based on preference
    hotels_data = None
    airbnb_data = None
    
    if accommodation_type in ['hotels', 'both']:
        hotels_data = agent.search_hotels(destination, outbound_date, return_date)
    
    if accommodation_type in ['airbnb', 'both']:
        airbnb_data = agent.search_airbnb(destination, outbound_date, return_date)
    
    flight_cost = best_flights[0].get('price', 0) if best_flights else 0
    remaining_budget = budget - flight_cost
    
    # Generate itinerary
    itinerary = agent.create_structured_itinerary(destination, keywords, remaining_budget, duration_days, hotels_data, airbnb_data)
    
    # Format hotel data with images
    hotel_options = []
    if hotels_data and "properties" in hotels_data:
        for hotel in hotels_data.get("properties", [])[:12]:
            hotel_options.append({
                "name": hotel.get("name", "N/A"),
                "price_per_night": hotel.get("rate_per_night", {}).get("lowest", "N/A"),
                "rating": hotel.get("overall_rating", "N/A"),
                "reviews": hotel.get("reviews", 0),
                "link": hotel.get("link", "#"),
                "description": hotel.get("description", "")[:200],
                "image": hotel.get("images", [{}])[0].get("thumbnail") if hotel.get("images") else None,
                "type": "hotel"
            })
    
    # Format Airbnb data with images
    airbnb_options = []
    if airbnb_data and "properties" in airbnb_data:
        for listing in airbnb_data.get("properties", [])[:12]:
            airbnb_options.append({
                "name": listing.get("name", "N/A"),
                "price_per_night": listing.get("rate", "N/A"),
                "rating": listing.get("rating", "N/A"),
                "reviews": listing.get("reviews", 0),
                "link": listing.get("link", "#"),
                "description": f"{listing.get('type', 'Property')} - {listing.get('bedrooms', 0)} bed",
                "image": listing.get("images", [{}])[0] if listing.get("images") else None,
                "type": "airbnb"
            })
    
    return jsonify({
        "destination": destination,
        "keywords": keywords,
        "total_budget": budget,
        "trip_duration": duration_days,
        "outbound_date": outbound_date,
        "return_date": return_date,
        "flight_options": best_flights[:8],
        "recommended_flight_cost": flight_cost,
        "hotel_options": hotel_options,
        "airbnb_options": airbnb_options,
        "remaining_budget": remaining_budget,
        "itinerary": itinerary,
        "accommodation_type": accommodation_type
    })

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 8080))
    app.run(host='0.0.0.0', port=port)
